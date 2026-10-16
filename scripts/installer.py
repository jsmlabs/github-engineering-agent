"""Offline, user-scoped installer for a trusted local release wheel.

No network requests, elevated privileges, arbitrary shell strings or secret storage.
The installer only manages its dedicated application directory.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv
import zipfile

PACKAGE = "github-engineering-agent"
APP_DIR = "GitHubEngineeringAgent"


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
        raise ValueError("Target must be a dedicated directory below the current user's home")
    if path.is_symlink():
        raise ValueError("Refusing symlink installation directory")
    return path


def validate_wheel(path: Path, expected_sha256: str) -> tuple[Path, str]:
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("Provide a lowercase 64-digit SHA-256 digest")
    wheel = path.expanduser().resolve(strict=True)
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("Select a local .whl file")
    actual = hashlib.file_digest(wheel.open("rb"), "sha256").hexdigest()
    if actual != expected_sha256:
        raise ValueError("Wheel integrity check failed")
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        if not any(name.endswith(".dist-info/METADATA") and name.startswith("github_engineering_agent-") for name in members):
            raise ValueError("Wheel is not the expected package")
        if any(name.startswith("/") or ".." in Path(name).parts or "\\" in name for name in members):
            raise ValueError("Wheel contains unsafe archive paths")
    return wheel, actual


def python_in(target: Path) -> Path:
    return target / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run_command(argv: list[str]) -> None:
    subprocess.run(argv, check=True, timeout=180)


def install(target: Path, wheel: Path, digest: str) -> str:
    target = validate_target(target)
    wheel, digest = validate_wheel(wheel, digest)
    marker = target / ".gh-engineer-managed"
    if target.exists() and not marker.is_file():
        raise ValueError("Existing directory is not managed by this installer")
    target.mkdir(parents=True, exist_ok=True)
    environment = python_in(target)
    if not environment.is_file():
        venv.EnvBuilder(with_pip=True).create(target / "venv")
    run_command([str(environment), "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall", str(wheel)])
    run_command([str(environment), "-m", "gh_agent", "--help"])
    marker.write_text("github-engineering-agent managed installation v1\n", encoding="utf-8")
    return "Installation verified"


def verify(target: Path) -> str:
    target = validate_target(target)
    if not (target / ".gh-engineer-managed").is_file():
        raise ValueError("No managed installation found")
    environment = python_in(target)
    if not environment.is_file():
        raise ValueError("Installed Python environment is missing")
    run_command([str(environment), "-m", "gh_agent", "--help"])
    return "Installed CLI verified (offline)"


def uninstall(target: Path, confirmation: str) -> str:
    target = validate_target(target)
    if confirmation != "UNINSTALL":
        raise ValueError("Explicit UNINSTALL confirmation required")
    marker = target / ".gh-engineer-managed"
    if not marker.is_file() or marker.read_text(encoding="utf-8") != "github-engineering-agent managed installation v1\n":
        raise ValueError("Not an installation owned by this installer")
    if any(p.name not in {"venv", ".gh-engineer-managed"} for p in target.iterdir()):
        raise ValueError("Unknown files present; refusing to remove user data")
    shutil.rmtree(target)
    return "Managed application directory removed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline user-level installation manager")
    parser.add_argument("action", choices=("install", "update", "repair", "verify", "uninstall"))
    parser.add_argument("--target", type=Path, default=default_target())
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--sha256", default="")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        if args.action in ("install", "update", "repair"):
            if args.wheel is None:
                raise ValueError("--wheel and --sha256 are required for installation, updates and repair")
            result = install(args.target, args.wheel, args.sha256)
        elif args.action == "verify":
            result = verify(args.target)
        else:
            result = uninstall(args.target, args.confirm)
        print(result)
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        print(f"Installation operation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
