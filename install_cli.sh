#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-$HOME/.local/bin}"
mkdir -p "${TARGET_DIR}"
cp "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bin/hermes-memory" "${TARGET_DIR}/hermes-memory"
chmod +x "${TARGET_DIR}/hermes-memory"
echo "Installed hermes-memory CLI to ${TARGET_DIR}/hermes-memory"
