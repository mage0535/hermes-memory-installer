#!/usr/bin/env bash
set -euo pipefail
: "${MEMORY_SIDECAR_HOME:?MEMORY_SIDECAR_HOME is required}"
OUTPUT_DIR="${MEMORY_EVAL_OUTPUT_DIR:-${AGENT_HOME}/logs}"
mkdir -p "$OUTPUT_DIR"
cd "$MEMORY_SIDECAR_HOME"
python3 -m memory_eval.runner --mode smoke --registry "${MEMORY_EVAL_REGISTRY:-all}" --output "$OUTPUT_DIR/memory-smoke.json"
