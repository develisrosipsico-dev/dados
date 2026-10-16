#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps -e .

# Modelo público oficial, revisão e checksum fixados. Não desabilita TLS.
mkdir -p .local/tessdata
model=.local/tessdata/por.traineddata
checksum=c4932b937207a9514b7514d518b931a99938c02a28a5a5a553f8599ed58b7deb
if ! (printf '%s  %s\n' "$checksum" "$model" | sha256sum --check --status); then
    temporary=$(mktemp .local/tessdata/.por.XXXXXX)
    trap 'rm -f "$temporary"' EXIT
    curl --fail --location --proto '=https' --tlsv1.2 \
        https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/por.traineddata \
        --output "$temporary"
    printf '%s  %s\n' "$checksum" "$temporary" | sha256sum --check
    mv "$temporary" "$model"
    trap - EXIT
fi
export TESSDATA_PREFIX="$PWD/.local/tessdata"
.venv/bin/python -m pytest -q
