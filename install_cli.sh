#!/bin/sh
set -eu

# Install hermes-memory CLI into a stable user path and symlink to ~/.local/bin.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SRC_CLI="${SCRIPT_DIR}/bin/hermes-memory"
TARGET_DIR="${HOME}/.local/share/hermes-memory/bin"
TARGET_CLI="${TARGET_DIR}/hermes-memory"
LINK_DIR="${HOME}/.local/bin"
LINK_PATH="${LINK_DIR}/hermes-memory"

mkdir -p "${TARGET_DIR}" "${LINK_DIR}"
cp "${SRC_CLI}" "${TARGET_CLI}"
chmod +x "${TARGET_CLI}"
ln -sf "${TARGET_CLI}" "${LINK_PATH}"

echo "hermes-memory CLI installed at ${TARGET_CLI}"
echo "Symlinked as ${LINK_PATH}. Try: hermes-memory doctor"
