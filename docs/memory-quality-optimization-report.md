# Memory Quality Optimization Report

Date: 2026-07-02

## Scope

This update implements the first three optimization priorities after v3.5.2:

1. Runtime path normalization and continuous evaluation governance.
2. Policy metadata for importance, current-vs-historical retrieval, and conflict handling.
3. gbrain edge planning visibility and operational reporting.

The work stays additive. It does not modify Hindsight, gateway, headroom, or existing memory service internals.

## Implemented

### Runtime Paths

`runtime_paths.py` is now the canonical helper for new code. It resolves:

- `AGENT_HOME` before `HERMES_HOME`
- fallback `$HOME/.hermes`
- sidecar home
- logs directory
- private production registry path
- governance database path

Legacy helpers touched during acceptance now follow the same precedence.

### Evaluation Governance

`memory_eval.trends` compares report payloads and produces per-registry metric deltas.

`memory_eval.registry_lint` validates public or private registries and reports:

- duplicate IDs
- missing required fields
- secret-like values
- IP-like values
- credential-bearing URLs

The linter reports rule names and case IDs only. It does not echo matched values.

### Policy Layer

The additive `memory_policy` table now owns these governance-only fields:

- `fact_key`
- `conflict_group`
- `valid_from`
- `valid_to`
- `superseded_by`

`current_policies()` filters superseded and expired policy rows for current retrieval decisions.

### gbrain Edge Visibility

`gbrain_edges.planner.summarize_plan()` reports planned edge counts by type and provenance. It does not apply edges and keeps the existing `--dry-run` default boundary intact.

### Operational Report

`memory_ops.report` returns a single JSON summary for operators:

- latest memory evaluation report
- policy row count
- eviction candidate count
- gbrain edge dry-run state
- disabled temporal/MTM flags

### Installer Surface

The installer now exposes explicit flags:

- `--enable-memory-quality`
- `--install-memory-quality-cron`
- `--init-memory-policy`

`deploy_memory_quality_modules()` installs only public modules and excludes private production registries.

Production integration note:

- Runtime authority stays in `$AGENT_HOME/scripts`.
- The sidecar directory provides Python modules, reports, and installer assets.
- On the production Hermes host, `tiered_context_injector.py` runs from `$AGENT_HOME/scripts` and imports policy/shadow helpers from `$AGENT_HOME/memory-sidecar`.

## Recommended Next Work

1. Increase the private production registry from a small baseline to 20-50 stable, sanitized cases.
2. Add a scheduled `registry_lint` run before monthly production benchmarks.
3. Add a real Hindsight/gbrain feeder for edge candidates once dry-run reports are reviewed.
4. Enable `MEMORY_POLICY_RANKING_ENABLED=true` for a controlled production window after policy rows are populated and baseline reports are saved.
5. Review MTM promoted rows before wiring them into direct Hindsight writes.

## 2026-07-02 Implementation Update

The optimization layer now has working implementations beyond the original dry-run shells:

- `governance.inject_policy.inject_from_governance()` reads `memory_objects` and writes sanitized policy rows.
- `governance.policy.apply_policy_to_candidates()` can boost core memories and filter expired or superseded candidates.
- `scripts/tiered_context_injector.py` can apply policy ranking when `MEMORY_POLICY_RANKING_ENABLED=true`.
- `gbrain_edges.hindsight_feeder.build_candidates_from_governance()` builds semantic and temporal edge candidates from governance conflict groups, and structure candidates from shared entity types when production conflict groups are too granular.
- `governance.temporal.temporal_retrieve()` supports `mode=current` and `mode=historical` when `TEMPORAL_TRUTH_ENABLED=true`.
- `mtm.consolidator.MidTermMemory` and `consolidate()` provide a lightweight JSONL mid-term buffer with heuristic promotion into policy metadata.
- `memory_ops.report` includes MTM item counts and computes the same gbrain dry-run edge count used by the feeder CLI.
- `memory_ops.shadow_log` records policy-ranking shadow comparisons without raw query text, titles, snippets, or memory content.

Production validation on 2026-07-02:

- Policy injection populated 16,600 governance policy rows.
- gbrain feeder dry-run planned 96 candidate edges from the production governance database without writing to gbrain.
- `memory_ops.report` reports the same 96 dry-run planned edges.
- Hindsight and gateway remained active after deployment; feature flags that alter runtime retrieval behavior remain disabled by default.

## Policy Ranking Shadow Observation

Shadow observation is the recommended next production phase before enabling policy ranking:

- Enable only `MEMORY_POLICY_SHADOW_LOG_ENABLED=true`.
- Keep `MEMORY_POLICY_RANKING_ENABLED=false` until a 7-day report is reviewed.
- The live recall path still returns the original ranking; the shadow path only computes the policy-ranked alternative and writes metadata.
- The JSONL log stores `query_hash`, candidate IDs, before/after top-k IDs, promoted/demoted IDs, elapsed milliseconds, and candidate-set hash.
- Raw query text, snippets, titles, and memory content are not logged.

Default locations:

- `$AGENT_HOME/logs/memory-policy-shadow.jsonl`
- `$AGENT_HOME/logs/memory-policy-shadow-latest.json`

Daily analysis is staged inside the memory-quality cron block:

```bash
python3 -m memory_ops.shadow_log --days 7 --output "$AGENT_HOME/logs/memory-policy-shadow-latest.json"
```

Production keeps the entire memory-quality cron block registered but paused with `# REMEDIATION-PAUSED` markers. Shadow logging itself is enabled by gateway environment overrides, so the recall path can be observed without automatically turning on the maintenance jobs.

Decision rule:

- `enable_policy_ranking_gray`: enough events, meaningful ranking changes, acceptable latency.
- `continue_shadow_until_enough_data`: fewer than the minimum event count.
- `keep_disabled_latency_too_high`: policy shadow adds too much latency.
- `keep_disabled_low_impact`: ranking rarely changes.
- `continue_shadow_review_samples`: ambiguous result, review promoted/demoted IDs.

Recommended production order:

1. Run `python3 -m governance.inject_policy --db-path "$AGENT_HOME/memory_governance.db" --apply`.
2. Run `python3 -m memory_eval.runner --mode full --registry production --backend live --output "$AGENT_HOME/logs/memory-policy-baseline.json"`.
3. Enable `MEMORY_POLICY_RANKING_ENABLED=true` for `tiered_context_injector.py` only after the baseline exists.
4. Run `python3 -m gbrain_edges.hindsight_feeder --db-path "$AGENT_HOME/memory_governance.db" --dry-run` and inspect planned edge counts before any `--apply`.
5. Run MTM with `MTM_ENABLED=true python3 -m mtm.consolidator --apply`.

## 2026-07-10 Runtime Stabilization

Production runtime issues were traced to three concrete causes:

- `memory_governance_rebuild.py` still defaulted to `$HOME/.agent`, so direct production runs could miss `$AGENT_HOME/state.db` and leave `hindsight_synced_at` stale.
- `session_to_gbrain.py` depended on `GBRAIN_MCP_TOKEN` but production wrappers did not export it, causing MCP 401 failures before archive work started.
- `session_to_gbrain.py` also attempted to archive large `request_dump_*.json` raw transport dumps, which are operationally noisy and can stall page writes without improving knowledge quality.

The shipped fixes are:

- default all directly related runtime scripts to `$HOME/.hermes` instead of `$HOME/.agent`;
- auto-discover gbrain MCP bearer credentials from `$AGENT_HOME/config.yaml` when `GBRAIN_MCP_TOKEN` is unset;
- skip `request_dump_*.json` by default unless `SESSION_TO_GBRAIN_INCLUDE_REQUEST_DUMPS=true`;
- downgrade slight Hindsight node budget overflow from `critical` to `action` when the overage stays within a small grace window and consolidation is otherwise healthy;
- record `execution_ok` vs `business_ok` separately in LangSmith monitor/task payloads and trend summaries;
- keep the alert queue transition-based, with resolved notifications and stricter wording that says auto-fix was attempted rather than guaranteed successful.

Observed production improvements after deployment:

- `hindsight_sync_lag_seconds`: about `21597` seconds down to under `1000` seconds.
- guardian level: `critical` down to `action`.
- gbrain missing embeddings: sharply reduced from `147` to low single digits during auto-fix.
- active alerts: `hindsight_lag` and `recent_acceptance_failures` cleared from the latest alert set; remaining actionable alert is gbrain stale/orphan remediation.

Known remaining issue:

- gbrain stale/orphan recovery is improved but not yet fully clean; follow-up should focus on the last few missing embeddings and the remaining orphan set.

## 2026-07-10 Cold-Layer Closure

The remaining cold-layer work was narrowed and mostly closed:

- `request_dump_*.json` raw transport dumps are now excluded from `session_to_gbrain.py` by default because they are operational noise rather than durable memory pages.
- gbrain orphan handling now treats generated orphan index pages as maintenance artifacts instead of actionable business content.
- direct orphan-link planning is built into `gbrain_deorphan_index.py`, so deorphan maintenance no longer depends only on implicit link extraction.
- production gbrain status improved from `missing_embeddings=147, orphans=40` to `missing_embeddings=0, actionable_orphans=0`.

Current production interpretation:

- `gbrain-stale-latest.json` is now `healthy` when only panel-noise stale counters and generated orphan-index pages remain.
- the remaining stale-page count is treated as an upstream accounting or contributor-visibility gap, not as a local write/read failure.
- active health alerts should now be limited to repository drift or genuine future regressions, not the previously noisy Hindsight lag or recent acceptance failures.

## Acceptance Commands

```bash
python3 -m pytest -q
python3 -m compileall -q memory_eval governance gbrain_edges mtm memory_ops installer scripts
python3 bin/hermes-memory audit-repo --format json
python3 -m memory_eval.runner --mode full --registry default --backend synthetic --output build/memory-benchmark-default.json
python3 -m memory_ops.report --agent-home "$AGENT_HOME"
```
