"""Operator-configured verification inside a bounded Docker container.

Docker is a trusted host dependency, not a security boundary against a
compromised daemon. Use only a trusted rootless/isolated Docker installation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .core import AgentError, assert_checkout, private_json_write, sha

_DIGEST = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_./-]*@sha256:[a-f0-9]{64}$")
_MAX_ARGS = 32
_MAX_SECONDS = 300


def verification_path(proposal: Path) -> Path:
    return Path(str(proposal) + ".verified.json")


def run_isolated(checkout: Path, image: str, argv: list[str], timeout: int) -> dict:
    if not isinstance(image, str) or not _DIGEST.fullmatch(image):
        raise AgentError("Test image must be pinned by sha256 digest")
    if (not isinstance(argv, list) or not 1 <= len(argv) <= _MAX_ARGS
            or any(not isinstance(a, str) or not a or "\x00" in a or len(a) > 512 for a in argv)):
        raise AgentError("Test command must be a bounded JSON string array")
    if type(timeout) is not int or not 1 <= timeout <= _MAX_SECONDS:
        raise AgentError("Test timeout must be between 1 and 300 seconds")
    if os.name != "posix" or any(ch in str(checkout) for ch in (",", "\n", "\r")):
        raise AgentError("Docker verification requires a POSIX path without mount delimiters")
    import resource  # Only reached on POSIX hosts
    cid_dir = tempfile.TemporaryDirectory(prefix="gh-engineer-cid-")
    try:
        cid = Path(cid_dir.name) / "cid"
        workspace = Path(cid_dir.name) / "work"
        try:
            shutil.copytree(checkout, workspace, symlinks=True)
        except OSError as exc:
            raise AgentError("Cannot prepare disposable verification workspace") from exc
        # The operator's checkout stays untouched. Tests can write inside the
        # disposable workspace, without network access or host credentials.
        cmd = [
            "docker", "run", "--rm", "--pull=never", "--cidfile", str(cid),
            "--network=none", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--pids-limit=64",
            "--memory=512m", "--cpus=1", "--user", f"{os.getuid()}:{os.getgid()}",
            "--tmpfs=/tmp:rw,nosuid,noexec,size=64m",
            "--mount", f"type=bind,source={workspace},target=/work",
            "--workdir=/work", "--env=HOME=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1",
            image, *argv,
        ]
        try:
            with (Path(cid_dir.name) / "stdout").open("wb") as out, \
                 (Path(cid_dir.name) / "stderr").open("wb") as err:
                result = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err,
                                        timeout=timeout, check=False,
                                        preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (262144, 262144)),
                                        env={
                                            "PATH": os.environ.get("PATH", ""),
                                            "HOME": os.environ.get("HOME", "/"),
                                        })
        except subprocess.TimeoutExpired as exc:
            # A client timeout need not stop the daemon-side container.
            # Attempt cleanup without trusting cleanup failure as success.
            if cid.exists():
                identifier = cid.read_text(encoding="ascii").strip()
                if re.fullmatch(r"[a-f0-9]{64}", identifier):
                    try:
                        subprocess.run(["docker", "rm", "-f", identifier],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=15, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            raise AgentError("Isolated test timed out; inspect Docker for surviving containers") from exc
        except OSError as exc:
            raise AgentError("Docker unavailable; verification did not run") from exc
        if result.returncode != 0 and cid.exists():
            identifier = cid.read_text(encoding="ascii").strip()
            if re.fullmatch(r"[a-f0-9]{64}", identifier):
                try:
                    subprocess.run(["docker", "rm", "-f", identifier],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=15, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        with (Path(cid_dir.name) / "stdout").open("rb") as out, \
             (Path(cid_dir.name) / "stderr").open("rb") as err:
            return {"exit_code": result.returncode,
                    "stdout_excerpt": out.read(2048).decode("utf-8", errors="replace"),
                    "stderr_excerpt": err.read(2048).decode("utf-8", errors="replace")}
    finally:
        cid_dir.cleanup()


def verify_commit(checkout: Path, proposal: Path, record: dict, receipt: dict,
                  image: str, argv: list[str], timeout: int) -> dict:
    path = verification_path(proposal)
    if path.exists():
        raise AgentError("Verification record already exists; inspect it before retrying")
    commit = assert_checkout(checkout, record["repo"], record["base"], require_base=False)
    if commit != receipt.get("commit") or sha(proposal.read_bytes()) != receipt.get("proposal_sha256"):
        raise AgentError("Verification requires the exact approved proposal and commit")
    from .core import run_git
    if run_git(checkout, "branch", "--show-current") != receipt.get("branch"):
        raise AgentError("Verification checkout branch mismatch")
    result = run_isolated(checkout, image, argv, timeout)
    report = {"schema": 1, "proposal_sha256": receipt["proposal_sha256"],
              "commit": commit, "branch": receipt["branch"],
              "image": image, "argv": argv,
              "outcome": "PASS" if result["exit_code"] == 0 else "FAIL",
              **result}
    private_json_write(path, report)
    return report


def check_gate(proposal: Path, receipt: dict, *, override: bool, reason: str | None) -> str:
    path = verification_path(proposal)
    if path.exists():
        from .core import load_json
        report = load_json(path)
        if (report.get("schema") != 1
                or report.get("proposal_sha256") != receipt.get("proposal_sha256")
                or report.get("commit") != receipt.get("commit")
                or report.get("branch") != receipt.get("branch")):
            raise AgentError("Stale or invalid verification record")
        if report.get("outcome") == "PASS" and report.get("exit_code") == 0:
            return "PASS"
        # Explicit exception is for unavailable tests, NOT known test failures.
        raise AgentError("Recorded test failure blocks publication")
    if override:
        if not isinstance(reason, str) or not 12 <= len(reason.strip()) <= 300:
            raise AgentError("Unverified publication requires --unverified-reason (12-300 characters)")
        return "EXCEPTION: " + reason.strip()
    raise AgentError("Missing commit-bound verification; run verify or approve an explicit exception")
