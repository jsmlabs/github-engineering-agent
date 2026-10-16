#!/bin/sh
# Use with: sh ./run-agent.sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 scripts/installer.py launch --agent-args gui
