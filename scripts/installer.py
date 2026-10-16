"""Offline, user-scoped wheel installer with isolated releases and atomic activation.

Never fetches release artifacts, modifies system Python, stores secrets, or elevates.
Each environment is created in its final path so Windows virtualenv launchers
are never relocated. The previous environment survives an update for rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import venv
import zipfile

PACKAGE = "github-engineering-agent"
APP_DIR = "GitHubEngineeringAgent"
MARKER = "github-engineering-agent managed installation v2\n"
SLOT_MARKER = "managed release slot v1\n"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def default_target() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / APP_DIR


def validate_target(target: Path) -> Path:
    path = target.expanduser().resolve(strict=False)
    home = Path.home().resolve()
    if path == home or path == Path(path.anchor) or home not in path.parents:
        raise ValueError("Installation must be in a dedicated directory under your home")
    return path


def validate_wheel(path: Path, expected_sha256: str) -> tuple[Path, str, str]:
    if not HEX64.fullmatch(expected_sha256):
        raise ValueError("Expected SHA-256 must contain exactly 64 lowercase hexadecimal characters")
    wheel = path.expanduser().resolve(strict=True)
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("A local .whl file is required")
    with wheel.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected_sha256:
        raise ValueError("Release wheel SHA-256 mismatch")
    with zipfile.ZipFile(wheel) as archive:
        paths = archive.namelist()
        if any(x.startswith("/") or ".." in Path(x).parts or "\\" in x for x in paths):
            raise ValueError("Wheel contains an unsafe archive member")
        metadata = [x for x in paths if x.startswith("github_engineering_agent-") and x.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Unexpected wheel distribution")
        info = archive.read(metadata[0]).decode("utf-8")
        fields = dict(line.split(": ", 1) for line in info.splitlines()
                      if line.startswith(("Name: ", "Version: ")))
        version = fields.get("Version")
        if fields.get("Name") != PACKAGE or not version or not re.fullmatch(r"[0-9A-Za-z.!+_-]{1,64}", version):
            raise ValueError("Invalid wheel distribution metadata")
    return wheel, actual, version


def python_in(slot: Path) -> Path:
    return slot / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def require_managed(target: Path) -> None:
    if not (target / ".gh-engineer-managed").is_file():
        raise ValueError("No managed installation exists")
    if (target / ".gh-engineer-managed").read_text(encoding="utf-8") != MARKER:
        raise ValueError("Invalid installer ownership marker")


def read_state(target: Path) -> dict:
    require_managed(target)
    state_file = target / "state.json"
    if not state_file.is_file():
        return {"schema": 1, "active": None, "previous": None, "versions": {}}
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if (type(state) is not dict or state.get("schema") != 1
            or any(x is not None and (type(x) is not str or not HEX64.fullmatch(x))
                   for x in (state.get("active"), state.get("previous")))
            or type(state.get("versions")) is not dict
            or any(not HEX64.fullmatch(k) or type(v) is not str
                   for k, v in state["versions"].items())):
        raise ValueError("Invalid installation state; no changes made")
    for key in ("active", "previous"):
        if state[key] is not None and state[key] not in state["versions"]:
            raise ValueError("Install state references unknown release")
    return state


def write_state(target: Path, state: dict) -> None:
    candidate = target / "state.json.tmp"
    if candidate.exists():
        raise ValueError("Interrupted state update detected; inspect before retrying")
    try:
        with candidate.open("x", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(candidate, target / "state.json")
    finally:
        if candidate.exists():
            candidate.unlink()


def run_checked(args: list[str], *, capture: bool = False) -> str:
    outcome = subprocess.run(args, check=True, timeout=240,
                             capture_output=capture, text=capture)
    return outcome.stdout.strip() if capture else ""


def verify_slot(slot: Path, expected_version: str) -> None:
    if (slot / ".slot-managed").read_text(encoding="utf-8") != SLOT_MARKER:
        raise ValueError("Release slot marker is invalid")
    python = python_in(slot)
    if not python.is_file():
        raise ValueError("Release environment is missing")
    run_checked([str(python), "-m", "gh_agent", "--help"])
    actual = run_checked([str(python), "-c",
        "from importlib.metadata import version; print(version('github-engineering-agent'))"], capture=True)
    if actual != expected_version:
        raise ValueError("Installed version does not match expected release")


def install(target: Path, wheel: Path, digest: str) -> str:
    target = validate_target(target)
    wheel, digest, version = validate_wheel(wheel, digest)
    marker = target / ".gh-engineer-managed"
    if target.exists():
        require_managed(target)
        state = read_state(target)
    else:
        target.mkdir(parents=True)
        marker.write_text(MARKER, encoding="utf-8")
        state = read_state(target)
    slot = target / "releases" / digest
    if slot.exists():
        if not (slot / ".slot-managed").is_file() or (slot / ".slot-managed").read_text() != SLOT_MARKER:
            raise ValueError("Existing release directory is not managed")
    else:
        slot.mkdir(parents=True)
        (slot / ".slot-managed").write_text(SLOT_MARKER, encoding="utf-8")
    python = python_in(slot)
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(slot / "venv")
    # Source wheel is rechecked just before pip, though external callers must
    # ensure the local source cannot be modified concurrently.
    validate_wheel(wheel, digest)
    run_checked([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                 "--force-reinstall", str(wheel)])
    verify_slot(slot, version)
    if state["active"] != digest:
        state["previous"] = state["active"]
    state["active"] = digest
    state["versions"][digest] = version
    write_state(target, state)
    return f"Active version {version} verified. Previous release preserved for rollback."


def verify(target: Path) -> str:
    target = validate_target(target)
    state = read_state(target)
    active = state["active"]
    if active is None:
        raise ValueError("No active verified release")
    verify_slot(target / "releases" / active, state["versions"][active])
    return f"Active version {state['versions'][active]} verified (offline)"


def rollback(target: Path) -> str:
    target = validate_target(target)
    state = read_state(target)
    previous = state["previous"]
    if previous is None:
        raise ValueError("No previous release is available for rollback")
    verify_slot(target / "releases" / previous, state["versions"][previous])
    state["active"], state["previous"] = previous, state["active"]
    write_state(target, state)
    return f"Rolled back to verified version {state['versions'][previous]}"


def status(target: Path) -> str:
    state = read_state(validate_target(target))
    active, previous = state["active"], state["previous"]
    return json.dumps({"active": state["versions"].get(active),
                       "previous": state["versions"].get(previous),
                       "installed_releases": len(state["versions"]),
                       "remote_checked": False}, sort_keys=True)


def uninstall(target: Path, confirmation: str) -> str:
    target = validate_target(target)
    if confirmation != "UNINSTALL":
        raise ValueError("Explicit UNINSTALL confirmation is required")
    require_managed(target)
    allowed = {".gh-engineer-managed", "state.json", "releases"}
    if any(entry.name not in allowed for entry in target.iterdir()):
        raise ValueError("Unexpected user files exist; refusing uninstall")
    releases = target / "releases"
    if releases.exists():
        if not releases.is_dir() or releases.is_symlink():
            raise ValueError("Unsafe release directory")
        for slot in releases.iterdir():
            if (not slot.is_dir() or slot.is_symlink() or not HEX64.fullmatch(slot.name)
                    or not (slot / ".slot-managed").is_file()
                    or (slot / ".slot-managed").read_text() != SLOT_MARKER
                    or any(entry.name not in {"venv", ".slot-managed"} for entry in slot.iterdir())):
                raise ValueError("Unrecognized release content; refusing uninstall")
    shutil.rmtree(target)
    return "Managed environments removed; external workspace and credentials unchanged"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, user-level installation manager")
    parser.add_argument("action", choices=("install", "update", "repair", "verify", "rollback", "status", "uninstall"))
    parser.add_argument("--target", type=Path, default=default_target())
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--sha256", default="")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        if args.action in ("install", "update", "repair"):
            if args.wheel is None:
                raise ValueError("--wheel and --sha256 are required")
            result = install(args.target, args.wheel, args.sha256)
        elif args.action == "verify":
            result = verify(args.target)
        elif args.action == "rollback":
            result = rollback(args.target)
        elif args.action == "status":
            result = status(args.target)
        else:
            result = uninstall(args.target, args.confirm)
        print(result)
        return 0
    except (ValueError, KeyError, OSError, json.JSONDecodeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        print(f"Installer operation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
