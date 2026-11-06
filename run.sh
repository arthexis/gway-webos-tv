#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -eq 0 || "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Usage: ./run.sh SCRIPT [ARG ...]"
    echo "Run a file from scripts/ using this repository's virtual environment."
    exit 0
fi
venv="$repo_dir/.venv"
if [[ ! -x "$venv/bin/python" ]]; then
    echo "Virtual environment not found at $venv; see the README development setup." >&2
    exit 1
fi
name="${1#scripts/}"
shift
if [[ "$name" == */* || "$name" == .* || ! -f "$repo_dir/scripts/$name" ]]; then
    echo "Script not found in scripts/: $name" >&2
    exit 1
fi
export PATH="$venv/bin:$PATH"
case "$name" in
    *.py) exec "$venv/bin/python" "$repo_dir/scripts/$name" "$@" ;;
    *.sh) exec bash "$repo_dir/scripts/$name" "$@" ;;
    *) echo "Unsupported script type: $name" >&2; exit 1 ;;
esac
