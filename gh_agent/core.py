"""Deterministic repository, proposal, and filesystem policy boundaries."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import ast
import difflib
import hashlib
import json
import os
import re
import stat
import subprocess
from typing import Any


class AgentError(Exception):
    """Expected, non-secret-bearing agent error."""


REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_FILE = re.compile(r"^[a-zA-Z0-9_.@+/-]+$")
ALLOWED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".css", ".html", ".yml", ".yaml", ".toml", ".go", ".rs", ".java", ".sh"}
PROTECTED_PARTS = {".git", ".github", ".vscode", ".idea", "node_modules", "vendor", "dist", "build", "__pycache__", ".venv", "venv", "secrets", "credentials"}
PROTECTED_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock", ".env", ".gitignore", ".gitattributes", "dockerfile", "makefile", "license", "license.md", "catalog.yaml"}
MAX_FILES = 5
MAX_FILE_BYTES = 20_000
MAX_TOTAL_BYTES = 55_000
MAX_ISSUE_CHARS = 6_000
MAX_TREE_FILES = 1_000


def require_repo(repo: str) -> str:
    if not REPO_PATTERN.fullmatch(repo) or any(part.startswith(("-", ".")) or part.endswith(".") or part in {".", ".."} for part in repo.split("/")):
        raise AgentError("Expected repository identifier owner/name")
    return repo


def check_path(path: str) -> str:
    """Model paths are repository-relative POSIX paths, never URLs or glob patterns."""
    if not isinstance(path, str) or not path or len(path) > 180 or not SAFE_FILE.fullmatch(path):
        raise AgentError("Disallowed path syntax")
    p = PurePosixPath(path)
    if p.is_absolute() or str(p) != path or len(p.parts) > 12 or any(part in {".", "..", ""} or part.startswith(".") for part in p.parts):
        raise AgentError("Unsafe or hidden path")
    if any(part.lower() in PROTECTED_PARTS for part in p.parts):
        raise AgentError("Protected directory")
    if p.name.lower() in PROTECTED_NAMES or p.name.lower().endswith((".pem", ".key", ".p12", ".secret")):
        raise AgentError("Protected or secret-bearing file")
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise AgentError("Extension is not allowed")
    return path


def guarded_file(checkout: Path, rel: str, *, allow_new: bool) -> Path:
    check_path(rel)
    root = checkout.resolve(strict=True)
    path = root / rel
    if not path.resolve(strict=False).is_relative_to(root):
        raise AgentError("Path escapes checkout")
    current = root
    for part in PurePosixPath(rel).parts:
        current = current / part
        if current.is_symlink():
            raise AgentError("Symlink target not permitted")
    if not path.exists():
        if not allow_new or not path.parent.is_dir():
            raise AgentError("Untracked/new paths must reside in an existing directory")
    elif not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise AgentError("Not a regular file")
    return path


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def run_git(checkout: Path, *args: str, timeout: int = 25) -> str:
    env = os.environ.copy()
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
    try:
        result = subprocess.run(["git", "-C", str(checkout), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args], capture_output=True, text=True, timeout=timeout, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AgentError("Git invocation failed or timed out") from exc
    if result.returncode:
        # Git stderr might contain private remote URLs: do not print it.
        raise AgentError(f"Git {args[0]} failed (exit {result.returncode})")
    return result.stdout.strip()


def remote_branch_sha(checkout: Path, branch: str) -> str | None:
    """Return only an exact origin branch ref, never an ambiguous suffix match."""
    if (not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._/-]*", branch)
            or ".." in branch or "//" in branch or branch.endswith(("/", ".", ".lock"))):
        raise AgentError("Invalid remote branch name")
    ref = f"refs/heads/{branch}"
    raw = run_git(checkout, "ls-remote", "--heads", "origin", ref, timeout=40)
    if not raw:
        return None
    found = raw.splitlines()
    if len(found) != 1:
        raise AgentError("Ambiguous remote branch result")
    parts = found[0].split("\t")
    if len(parts) != 2 or parts[1] != ref or not re.fullmatch(r"[a-f0-9]{40,64}", parts[0]):
        raise AgentError("Unexpected remote branch response")
    return parts[0]


def committed_blob(checkout: Path, commit: str, path: str) -> bytes:
    """Read the exact Git object bytes; text-mode git output can drop trailing newlines."""
    check_path(path)
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise AgentError("Invalid commit identifier")
    try:
        proc = subprocess.run(
            ["git", "-C", str(checkout), "-c", "core.hooksPath=/dev/null",
             "-c", "core.fsmonitor=false", "show", f"{commit}:{path}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AgentError("Cannot inspect committed file") from exc
    if proc.returncode or len(proc.stdout) > MAX_FILE_BYTES:
        raise AgentError("Committed file unavailable or exceeds budget")
    return proc.stdout


def assert_checkout(checkout: Path, repo: str, base: str, *, require_base: bool) -> str:
    require_repo(repo)
    root = checkout.resolve(strict=True)
    if Path(run_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True) != root:
        raise AgentError("Checkout must be the Git worktree root")
    if run_git(root, "status", "--porcelain", "--untracked-files=all"):
        raise AgentError("Checkout must be completely clean")
    origin = run_git(root, "remote", "get-url", "origin")
    push_origins = run_git(root, "remote", "get-url", "--push", "--all", "origin").splitlines()
    valid = {f"https://github.com/{repo}", f"https://github.com/{repo}.git", f"git@github.com:{repo}", f"git@github.com:{repo}.git", f"ssh://git@github.com/{repo}", f"ssh://git@github.com/{repo}.git"}
    if origin.lower() not in {v.lower() for v in valid} or len(push_origins) != 1 or push_origins[0].lower() not in {v.lower() for v in valid}:
        raise AgentError("Origin does not match explicit GitHub repository")
    head = run_git(root, "rev-parse", "HEAD")
    if require_base:
        if run_git(root, "branch", "--show-current") != base:
            raise AgentError("Checkout is not on the required base branch")
        if head != run_git(root, "rev-parse", f"refs/remotes/origin/{base}"):
            raise AgentError("Local base is not at the known origin/base commit; fetch and inspect manually")
    return head


def tracked_sources(checkout: Path) -> list[str]:
    result = []
    for p in run_git(checkout, "ls-files", "--cached").splitlines():
        try:
            guarded_file(checkout, p, allow_new=False)
            if (checkout / p).stat().st_size <= MAX_FILE_BYTES:
                result.append(p)
        except (AgentError, OSError):
            continue
    if len(result) > MAX_TREE_FILES:
        raise AgentError("Too many candidate files; use a smaller repository")
    return result


def validate_selection(checkout: Path, paths: list[str], tracked: set[str], allowed: set[str] | None = None) -> None:
    if (not isinstance(paths, list) or not (1 <= len(paths) <= MAX_FILES)
        or not all(isinstance(p, str) for p in paths) or len(set(paths)) != len(paths)):
        raise AgentError("Select 1-5 distinct paths")
    if allowed is not None and not set(paths).issubset(allowed):
        raise AgentError("Model selected a file outside the operator-approved scope")
    for p in paths:
        file = guarded_file(checkout, p, allow_new=True)
        if p not in tracked and file.exists():
            raise AgentError("Cannot modify untracked files")
        if p not in tracked and file.parent.resolve() != checkout.resolve() and not file.parent.exists():
            raise AgentError("Cannot create new directory")


def authorized_files(checkout: Path, paths: list[str] | None, tracked: set[str]) -> list[str]:
    """An operator-defined, explicit per-file boundary; no wildcards or recursive grants."""
    if paths is None or not isinstance(paths, list) or not paths:
        raise AgentError("At least one --allowed-file is required; implicit repository-wide access is forbidden")
    validate_selection(checkout, paths, tracked)
    return paths


def validate_source_sensitivity(path: str, content: str) -> None:
    """Block common credentials and terminal-control payloads. Not a DLP guarantee."""
    if any((ord(ch) < 32 and ch not in "\n\r\t") or ord(ch) == 127 for ch in content):
        raise AgentError(f"Control character in {path}; unsafe content blocked")
    patterns = (
        r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
        r"(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"(?:AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|GITHUB_TOKEN)\s*[:=]\s*['\"]?[^\s'\"]{12,}",
    )
    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
        raise AgentError(f"Potential credential in {path}; source upload blocked")


def validate_content_syntax(path: str, content: str) -> None:
    """Parse without running repository code; this is not a semantic or security review."""
    try:
        if path.lower().endswith(".py"):
            ast.parse(content, filename=path)
        elif path.lower().endswith(".json"):
            def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                result: dict[str, Any] = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON object key")
                    result[key] = value
                return result

            def reject_constant(value: str) -> None:
                raise ValueError("Non-finite JSON number")

            json.loads(content, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise AgentError(f"Invalid Python/JSON syntax in {path}") from exc


def read_selected(checkout: Path, paths: list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for path in paths:
        f = guarded_file(checkout, path, allow_new=True)
        raw = f.read_bytes() if f.exists() else b""
        if len(raw) > MAX_FILE_BYTES or b"\x00" in raw:
            raise AgentError("Binary or oversized source file")
        try:
            data[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AgentError("Non UTF-8 source file") from exc
    if sum(len(x.encode("utf-8")) for x in data.values()) > MAX_TOTAL_BYTES:
        raise AgentError("Source context exceeds budget")
    return data


def validate_edits(checkout: Path, edits: Any, bases: dict[str, str], tracked: set[str]) -> list[dict[str, str]]:
    if not isinstance(edits, list) or not edits or len(edits) > MAX_FILES:
        raise AgentError("Invalid edit count")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    total = 0
    for item in edits:
        if not isinstance(item, dict) or set(item) != {"path", "base_sha256", "content"}:
            raise AgentError("Invalid edit schema")
        p, original, content = item["path"], item["base_sha256"], item["content"]
        if not isinstance(p, str) or p not in bases or p in seen or not isinstance(content, str) or not isinstance(original, str):
            raise AgentError("Unexpected, duplicate, or malformed edit")
        f = guarded_file(checkout, p, allow_new=True)
        if p not in tracked and f.exists():
            raise AgentError("Cannot overwrite untracked file")
        if original != sha(bases[p].encode("utf-8")):
            raise AgentError("Stale file checksum in proposal")
        n = len(content.encode("utf-8"))
        total += n
        if n > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or "\x00" in content or content == bases[p]:
            raise AgentError("Oversized, binary, or unchanged edit")
        validate_content_syntax(p, content)
        validate_source_sensitivity(p, content)
        seen.add(p)
        results.append({"path": p, "base_sha256": original, "content": content})
    return results


def proposal_diff(bases: dict[str, str], edits: list[dict[str, str]]) -> str:
    parts = []
    for item in edits:
        p = item["path"]
        parts.extend(difflib.unified_diff(bases[p].splitlines(keepends=True), item["content"].splitlines(keepends=True), fromfile="a/" + p, tofile="b/" + p))
    return "".join(parts)


def private_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentError("Cannot read valid JSON file") from exc
    if not isinstance(data, dict):
        raise AgentError("Expected JSON object")
    return data
