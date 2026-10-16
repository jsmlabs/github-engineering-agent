"""Local-only setup readiness. Never disclose credential values or contact providers."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys


def snapshot() -> dict:
    return {
        "schema": 1,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_supported": sys.version_info >= (3, 11),
        "git_cli": bool(shutil.which("git")),
        "docker_cli": bool(shutil.which("docker")),
        "github_token_present": bool(os.environ.get("GITHUB_TOKEN")),
        "openai_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "network_checked": False,
        "credentials_verified": False,
        "permissions_modified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline prerequisites and credential presence check")
    parser.add_argument("--json", action="store_true")
    options = parser.parse_args(argv)
    state = snapshot()
    if options.json:
        print(json.dumps(state, sort_keys=True))
    else:
        print("Local setup readiness (no network requests)")
        for key, value in state.items():
            print(f"{key.replace('_', ' ')}: {value}")
        print("Credential presence is NOT proof of access or authorization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
