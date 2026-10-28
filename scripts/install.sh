#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
uv tool install --force "${repo_dir}"
install -Dm644 "${repo_dir}/man/gway-tv.1" "${HOME}/.local/share/man/man1/gway-tv.1"
printf 'Installed gway-tv and its user-local man page.\n'
