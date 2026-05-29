#!/usr/bin/env bash
set -euo pipefail

VERSION="3.0"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Hermes Memory Sidecar Installer v${VERSION}"
echo "Using ${PYTHON_BIN} from $(command -v "${PYTHON_BIN}")"

exec "${PYTHON_BIN}" "${ROOT_DIR}/installer/install.py" "$@"
