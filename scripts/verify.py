"""Cross-platform offline checks; does not contact GitHub or OpenAI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    [sys.executable, "-m", "compileall", "-q", "gh_agent", "tests"],
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    [sys.executable, "-m", "gh_agent", "--help"],
    [sys.executable, "-m", "gh_agent"],
    [sys.executable, "-m", "gh_agent", "guide"],
    [sys.executable, "-m", "gh_agent", "menu", "--help"],
    [sys.executable, "-m", "gh_agent", "doctor", "--help"],
    [sys.executable, "-m", "gh_agent", "next", "--help"],
]


def main() -> int:
    for args in COMMANDS:
        print("CHECK", " ".join(args[1:]), flush=True)
        result = subprocess.run(args, cwd=ROOT, check=False)
        if result.returncode:
            print("FAILED", result.returncode, file=sys.stderr)
            return result.returncode
    print("LOCAL_VERIFICATION_PASS (offline only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
