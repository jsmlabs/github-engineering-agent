#!/bin/sh
# Optional local setup window. Invoke with: sh ./install-unix.sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/installer_gui.py
fi
echo "Python 3.11+ with Tkinter is required." >&2
exit 2
