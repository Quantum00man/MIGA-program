#!/usr/bin/env bash
set -eu

project_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
cd -- "$project_dir"

if [ -n "${TGF_PYTHON:-}" ]; then
    exec "$TGF_PYTHON" "$project_dir/launcher.py" "$@"
fi

for python_command in python3 python; do
    if command -v "$python_command" >/dev/null 2>&1 &&
       "$python_command" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        exec "$python_command" "$project_dir/launcher.py" "$@"
    fi
done

printf '%s\n' \
    'Python 3.10 or newer was not found.' \
    'On Ubuntu 22.04 or newer, install the prerequisites and run this launcher again:' \
    '  sudo apt update' \
    '  sudo apt install python3 python3-venv python3-pip' \
    'On older Ubuntu releases, supply Python 3.10+ through TGF_PYTHON.'
exit 1
