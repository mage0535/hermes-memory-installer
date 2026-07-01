# Memory Sidecar v3.5.2

This release adds an agent-agnostic memory quality layer without changing memory services.

## Evaluation

The public synthetic registry contains 40 fictional cases for CI and installation smoke tests. An optional private registry is loaded only from `$AGENT_HOME/.memory_eval/registry_production.py`; it is never installed or committed.

Reports include recall@k, precision@k, contradiction rate, stale-hit rate, and cross-layer agreement. Run a smoke evaluation with `python3 -m memory_eval.runner --mode smoke --registry default`. Production and synthetic reports remain separate.

## Safety

Policy injection and gbrain edge planning use `--dry-run` by default and require `--apply` for writes. Provenance uses `--sanitize-provenance` by default. Phase 2 and Phase 4 remain disabled with `TEMPORAL_TRUTH_ENABLED=false` and `MTM_ENABLED=false`.

Installer schedules are marker-reconciled and idempotent. Production facts, generated reports, credentials, and host-specific paths are excluded from public artifacts.
