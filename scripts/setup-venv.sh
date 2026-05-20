#!/usr/bin/env bash
#
# Rebuild the openproject-mcp venv from scratch.
# Auto-detects a Python 3.10+ base on the Mac, then installs deps + this
# package in editable mode. Idempotent — safe to re-run any time the venv
# is broken or the base Python has moved.
#
# Usage:
#     bash scripts/setup-venv.sh

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_DIR="$(pwd)"

echo "==> Locating Python 3.10+ on this Mac..."

PY=""
for candidate in \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /usr/local/bin/python3.13 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3
do
    [[ -x "$candidate" ]] || continue
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
        PY="$candidate"
        echo "    using $PY ($("$PY" --version 2>&1))"
        break
    fi
done

if [[ -z "$PY" ]]; then
    cat <<'EOF'

ERROR: No Python 3.10+ found on this Mac.

Install one with:
    brew install python@3.12

Or download from https://www.python.org/downloads/ and re-run this script.
EOF
    exit 1
fi

echo
echo "==> Rebuilding venv at $REPO_DIR/venv..."
rm -rf venv
"$PY" -m venv venv

echo
echo "==> Installing dependencies..."
venv/bin/python3 -m pip install --quiet --upgrade pip
venv/bin/python3 -m pip install --quiet -r requirements.txt
venv/bin/python3 -m pip install --quiet -e src/

echo
echo "==> Verifying import..."
venv/bin/python3 -c "from openproject_mcp.tools.work_packages import create_relation, update_relation, delete_relation; print('ok')"

cat <<EOF

==> Done. Next steps:

1. Confirm ~/Library/Application Support/Claude/claude_desktop_config.json
   has its 'command' field pointing at:
       $REPO_DIR/venv/bin/python3
   (use python3, not python — Apple's Python stub doesn't ship a 'python' alias)

2. Quit and reopen Claude Desktop to reload the MCP subprocess.
EOF
