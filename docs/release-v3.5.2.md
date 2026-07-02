# Memory Sidecar v3.5.2

This release adds an agent-agnostic memory quality layer without changing memory services.

## Evaluation

The public synthetic registry contains 40 fictional cases for CI and installation smoke tests. An optional private registry is loaded only from `$AGENT_HOME/.memory_eval/registry_production.py`; it is never installed or committed.

Reports include recall@k, precision@k, contradiction rate, stale-hit rate, and cross-layer agreement. Run a smoke evaluation with `python3 -m memory_eval.runner --mode smoke --registry default`. Production and synthetic reports remain separate.

`runtime_paths.py` is the canonical path resolver for new modules. It gives `AGENT_HOME` priority over `HERMES_HOME`, falls back to `$HOME/.hermes`, and derives logs, sidecar, registry, and governance database paths from one source.

Use `python3 -m memory_eval.registry_lint --registry production` before adding or changing private production cases. The linter reports rule names and case IDs without echoing secret-like values.

Use `--previous <report.json>` with `memory_eval.runner` to compute metric deltas for trend monitoring.

## Safety

Policy injection and gbrain edge planning use `--dry-run` by default and require `--apply` for writes. Provenance uses `--sanitize-provenance` by default. Phase 2 and Phase 4 remain disabled with `TEMPORAL_TRUTH_ENABLED=false` and `MTM_ENABLED=false`.

Installer schedules are marker-reconciled and idempotent. Production facts, generated reports, credentials, and host-specific paths are excluded from public artifacts.

## Governance And Operations

The additive `memory_policy` table now owns policy-only fields for `fact_key`, `conflict_group`, `valid_from`, `valid_to`, and `superseded_by`. These fields support current-vs-historical retrieval decisions without duplicating source memory objects.

`memory_ops.report` produces a compact operational report covering the latest evaluation report, policy row counts, eviction candidates, gbrain edge planning state, and disabled extension flags.

Production validation populated 16,600 policy rows and confirmed that gbrain dry-run planning now reports 96 candidate edges from governance data. Runtime-impacting feature flags remain opt-in so deployment does not alter existing recall behavior until explicitly enabled.

`MEMORY_POLICY_SHADOW_LOG_ENABLED=true` enables a safe observation mode for policy ranking. It leaves live recall unchanged, computes the policy-ranked alternative in the background, and writes only hashes, memory IDs, rank deltas, and latency to `$AGENT_HOME/logs/memory-policy-shadow.jsonl`. The memory-quality cron block analyzes the last 7 days into `$AGENT_HOME/logs/memory-policy-shadow-latest.json`.

The installer exposes explicit memory quality switches:

- `--enable-memory-quality`
- `--install-memory-quality-cron`
- `--init-memory-policy`
