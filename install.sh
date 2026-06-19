#!/usr/bin/env bash
set -euo pipefail

VERSION="3.5"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Memory Sidecar Installer v${VERSION}"
echo "Python: $(command -v "${PYTHON_BIN}") ($(${PYTHON_BIN} --version 2>&1))"
echo ""

# Install PyYAML if needed
if ! ${PYTHON_BIN} -c "import yaml" 2>/dev/null; then
    echo "[installer] Installing PyYAML..."
    ${PYTHON_BIN} -m pip install "PyYAML>=6.0" --quiet
fi

exec "${PYTHON_BIN}" "${ROOT_DIR}/installer/install.py" "$@"
