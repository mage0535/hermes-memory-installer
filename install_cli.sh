#!/bin/sh
# Symlink hermes-memory CLI into PATH
ln -sf "/tmp/hermes-memory-installer/bin/hermes-memory" "$HOME/.local/bin/hermes-memory"
echo "hermes-memory CLI installed. Try: hermes-memory doctor"
