#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
uv tool install --force "${repo_dir}"
install -Dm644 "${repo_dir}/man/gway-tv.1" "${HOME}/.local/share/man/man1/gway-tv.1"
install -Dm644 "${repo_dir}/man/tv.1" "${HOME}/.local/share/man/man1/tv.1"
printf 'Installed tv, gway-tv, and their user-local man pages.\n'
if ! command -v tesseract >/dev/null 2>&1; then
    printf 'YouTube navigation also needs local OCR: sudo apt-get install tesseract-ocr tesseract-ocr-eng\n' >&2
fi
