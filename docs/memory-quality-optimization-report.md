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

## 2026-07-15 Production Evaluation Follow-up

The 2026-07-15 scheduled evaluation reported `DEGRADED`, but live root-cause analysis split the symptoms into two categories.

True runtime issues:

- production monitor children were not inheriting the intended `MEMORY_GUARDIAN_NODE_LIMIT=30000`, so Guardian was incorrectly reported as critical at the old 20000 budget;
- the hourly gbrain stale cron did not pass `--refresh-embeddings`, so missing embeddings were reported without the advertised auto-fix actually running;
- one stale cron-session chunk was left without a text embedding and required an embedding-service restart plus targeted repair.

Monitoring and scoring issues:

- fast acceptance intentionally skips L3, so `l3_count=0` in fast mode is not an L3 failure;
- the architecture knowledge sample was retrieved from authoritative `object` memory rather than the `knowledge` source, so acceptance now counts that specific object match as a valid knowledge hit;
- local LangSmith monitor output is wrapped under `snapshot`, and trend reporting now unwraps it before computing latest health;
- alerting now distinguishes current latest acceptance from historical failed monitor runs, preventing old failures from keeping `recent_acceptance_failures` active after the latest run is healthy;
- storage cross-check filters generated orphan-index pages before flagging gbrain orphan debt.

Post-fix production result:

- full acceptance is green (`ok=true`, no reason buckets);
- Guardian is green at the 30000 node budget, around 72.6% usage;
- Hindsight lag is below threshold;
- gbrain has 0 missing embeddings and 0 actionable orphans;
- health summary is `healthy`; only historical acceptance failures remain as info-level context.

Next recommended optimization:

- tune relationship/people recall separately. The optional relationship sample can still return no candidates and sometimes waits on live Hindsight until timeout. This is a recall-quality improvement, not a production health blocker.

## 2026-07-17 Guardian And Evaluation Report Consistency

Root cause of a later `DEGRADED` evaluation was configuration and scoring drift, not an active Hindsight ingestion failure:

- direct Guardian invocations used the old implicit `20000` node budget, while the LangSmith monitor correctly used the production `30000` budget;
- the same live node count was therefore reported as `critical` by the timer path and `ok` by the monitor path;
- the standalone evaluation script only used the full historical run set, so resolved Guardian and acceptance failures continued to reduce the live score.

The corrective changes are intentionally narrow:

- `memory_guardian.py` now has `30000` as its shared default, with `MEMORY_GUARDIAN_NODE_LIMIT` still taking precedence for installations that need another budget;
- `memory_eval_report.py` is now a tracked, deployed script rather than a server-only artifact;
- evaluation health uses the newest five monitor runs and the newest Guardian level. Historical acceptance failures and critical samples remain visible as trend context only;
- installer and deployment audit manifests include `memory_eval_report.py`.

Validation completed before deployment:

- `python -m pytest -q`: `250 passed, 2 skipped`;
- `python bin/hermes-memory audit-repo --format json`: `ok=true`.

Operational acceptance after deployment:

- direct Guardian status must show `node_limit=30000` and a non-critical level at the current node count;
- a full acceptance check must return `ok=true`;
- the regenerated evaluation report must expose `current_acceptance_ok_rate` and must not degrade solely because historical samples were failed or critical.

Final production verification:

- direct Guardian reported `node_limit=30000`, `usage_pct=73.3`, and `level=ok`;
- full acceptance reported `ok=true` with no error buckets and a 42-second sync lag;
- the regenerated LangSmith evaluation reported `100/100 healthy` from the newest five runs. Its historical acceptance rate was retained as trend context only;
- targeted gbrain maintenance returned `missing_embeddings=0`, zero actionable orphans, and `status=healthy`.

Deployment hardening:

- a tracked source checkout is now the drift-audit reference; the unrelated same-named server directory is no longer used as the memory deployment baseline;
- deployed Python and shell scripts are normalized to LF by the installer before atomic replacement. This prevents Windows checkout line endings from breaking Linux shebang execution or creating false script-hash drift;
- a previously immutable webhook receiver retained its immutable protection after its verified line-ending-only normalization; all affected pre-normalization files were backed up before the change.

## 2026-07-15 LangSmith And Recall Optimization Pass

The next optimization pass closed the P0-P4 follow-up items without changing Hindsight, gateway, or headroom service code.

Implemented changes:

- P0: live Hindsight L3 recall now uses `MEMORY_LIVE_HINDSIGHT_TIMEOUT_S` with a default 3 second timeout instead of the previous fixed 20 second wait. Slow live recall degrades to existing L2/L3 cache candidates.
- P0 addendum: foreground recall no longer performs inline governance DB rebuilds by default. Production keeps the governance index fresh with a `flock`-guarded background cron every 15 minutes; `MEMORY_RECALL_INLINE_GOVERNANCE_REBUILD=true` remains available as an explicit override.
- P1: LangSmith trend reports now separate current acceptance health from historical failures with `current_acceptance_ok_rate`, `current_window`, `current_failure_reasons`, and `historical_acceptance_failure_count`.
- P2: `gbrain_stale_maintenance.py --refresh-embeddings` is budgeted with `--stale-budget` and `--missing-budget`. Production cron uses `--stale-budget 100 --missing-budget 0` to avoid unbounded `embed --all` on fixed hardware.
- P3: weak recall rows now classify likely cause as `retrieval_timeout` or `no_seed_data` instead of reporting every zero-result query as a generic no-candidate failure.
- P4: alerting consumes the current acceptance signal first, while historical acceptance failures remain info-level context.
- SLO rollup now prefers `current_acceptance_ok_rate` when present, so old historical failures do not keep a recovered system degraded.

Validation:

- local full test suite: `242 passed, 2 skipped`;
- repository privacy audit: `audit-repo ok=true`.
- production timing probe found the remaining cold L3 latency was a first-query governance rebuild in the hub layer; after moving rebuild to cron, foreground `get_l3("agent memory architecture")` no longer pays that rebuild cost.

## 2026-07-15 Swap Restart Storm Fix

Root cause:

- The legacy `$AGENT_HOME/scripts/swap-pressure-responder.sh` restarted `hindsight` and `hermes-gateway` whenever swap exceeded 75%.
- Swap is a lagging pressure signal. Once swap reached 99-100%, the responder restarted core services every 15 minutes even when the services were otherwise healthy.
- Each Hindsight restart loaded and indexed the long-term memory bank again, which recreated CPU and memory pressure and kept the host in a restart loop.

Permanent fix:

- Removed the legacy swap responder from production cron.
- Extended `hermes_load_shedder.py` so normal pressure only deprioritizes browser publishing and clears stale temporary browser trees.
- Added critical-pressure handling: stale persistent browser publishing trees and their publishing parent runners are terminated before any memory core service is touched. Production sets the persistent-browser age gate to 180 seconds under critical pressure.
- The load shedder intentionally contains no `systemctl restart` path for `hindsight` or `hermes-gateway`; core restarts must be health-check driven, not swap-percentage driven.

Validation:

- Unit tests cover temporary browser cleanup, critical persistent-browser termination, and absence of core-service restart commands.
- Production cron keeps only `hermes_load_shedder.py` for pressure response.

## 2026-07-15 gbrain Missing-Embedding Repair

Root cause:

- `gbrain_stale_maintenance.py` previously treated any residual `missing_embeddings > 0` as an `embed --all` problem.
- On this host, `embed --all` is not an operator-safe recovery path: even with a low limit it still scans the full corpus and can be terminated under pressure.
- The actionable defect was only a single null `content_chunks.embedding` row for the generated page `hub-orphans-sessions`, plus temporary real orphans that were cleared by the deorphan wrapper.

Permanent fix:

- `gbrain_stale_maintenance.py` now discovers missing-embedding slugs from the configured gbrain Postgres database and runs targeted `gbrain embed --slugs ...` before considering any full-corpus repair path.
- The targeted repair path reuses the existing gbrain environment file, so it can talk to the local embedding server without requiring a separate manual shell setup.
- After targeted embed and deorphan, the remaining stale/orphan panel counters are downgraded to info-only upstream-gap debt when no actionable missing embeddings or real orphans remain.

Validation:

- Production repair cleared the last real missing embedding (`hub-orphans-sessions`) and reduced real orphan count to zero.
- Fresh `gbrain-stale-latest.json` now reports `status=healthy`, `auto_fix_succeeded=true`, and only info-level `stale_health_counter_not_embedding_stale` / `reported_orphans_counter_discrepancy`.

## 2026-07-15 Three-Way Consistency Note

At handoff time, the three environments were aligned at the content level:

- local worktree and GitHub `main` / `codex/v3.5.2` point to the same public commit `e213384`;
- the production server repository carries the same swap-storm fix content but a different local commit id because the server repository has no Git remote configured and is committed independently for drift closure;
- production runtime drift is `healthy`, the server repository is clean, and the deployed runtime scripts match the server repository hashes.

Operational state at handoff:

- `runtime-drift-latest.json`: `healthy`;
- `health-summary-latest.json`: `healthy`, with only `historical_acceptance_failures` remaining as info-level context;
- `hindsight.service` and `hermes-gateway` stayed on their `10:45` start timestamps across the post-fix pressure window, confirming that the restart storm path was removed rather than merely delayed.

## 2026-07-17 Final Recheck And Observability Closure

Follow-up recheck found the core memory pipeline healthy, but two observability details still needed closure.

Findings:

- The deployed source checkout, GitHub `main`, and local release worktree all pointed to the same public commit before this pass. Runtime drift was healthy and deployed script hashes matched the tracked source checkout.
- Live Guardian status was healthy at the shared 30000 node budget, with about 73.3% usage and no pending or failed operations.
- Full production acceptance returned `ok=true`, with L2 and L3 both active in the recall rows and no reason buckets.
- LangSmith ingestion logs showed `429 Too Many Requests` because the tenant had exceeded the monthly unique traces quota. Local monitor, trend, SLO, and alert artifacts still worked, but the online LangSmith project could no longer be treated as the only fresh source until quota resets or is upgraded.
- A manual `gbrain_stale_maintenance.py` status-only run could still report `degraded` from stale panel counters, even though the scheduled repair run had already proven `missing_embeddings=0` and real actionable orphans were zero.
- `hermes-memory status` displayed `alerts=1` when the only remaining alert was info-level historical context, which was technically accurate as a raw count but misleading for operator triage.

Changes:

- Added `LANGSMITH_PUBLISH=false` support to the LangSmith monitor, trend publisher, and generic task wrapper. This lets production keep generating local health artifacts while suppressing remote trace writes during quota exhaustion.
- Production LangSmith wrapper scripts now call the deployed runtime scripts under the agent script directory instead of the retired same-named repository path. This closes a hidden runtime-source split that was not visible in script hash drift.
- `gbrain_stale_maintenance.py` now reads the previous maintenance artifact during status-only checks. If the previous run already proved the remaining stale/orphan values are panel-only upstream debt and current missing embeddings plus real orphans are still zero, the status-only report remains `healthy` with info classifications.
- `hermes-memory status` now counts only `action-needed` and `degraded` alerts in the one-line operator summary. Info-level historical context remains present in `health-summary-latest.json`.

Operational guidance:

- During LangSmith quota exhaustion, set `LANGSMITH_PUBLISH=false` for scheduled monitor, trend, and wrapper jobs. Keep writing local outputs under the agent metrics directory.
- After quota resets or a higher plan is available, remove the override and run one monitor plus one trend publish to restore online freshness.
- Do not treat `historical_acceptance_failures` as a live incident when `current_acceptance_ok_rate=1.0`, latest Guardian is non-critical, and the SLO rollup says `acceptance_window=current`.
- Treat remaining gbrain stale/orphan counters as upstream reporting debt when `missing_embeddings=0`, `orphan_pages_actual=0`, and the latest repair artifact only contains info classifications.

Validation targets for future handoff:

- local tests include the LangSmith publish-disable gate, gbrain status-only panel-debt check, and info-alert status count regression;
- production should show `hermes-memory status` as `healthy alerts=0 ...` when only historical info remains;
- production gbrain status-only and scheduled refresh artifacts should agree on healthy/actionable state, not just on raw panel counters.

Final verification on the live server after deployment:

- source checkout: fast-forwarded to the latest GitHub `main` during final sync;
- wrapper smoke: monitor and trend both returned `langsmith=null` with no 429 quota errors;
- full acceptance: `ok=true`, ten recall rows, empty `reason_buckets`;
- Guardian: `node_limit=30000`, `usage_pct=73.3`, `level=ok`;
- gbrain status-only: `status=healthy`, `missing_embeddings=0`, `orphan_pages_actual=0`, classifications are info-only;
- drift check: `healthy`, deployed scripts match the tracked source checkout;
- operator status: `healthy alerts=0 acceptance=100.0%`.

## 2026-07-17 Live Hindsight Recall Timeout Closure

Follow-up investigation treated the live Hindsight timeout log as an actionable defect rather than a harmless fallback.

Root cause:

- Hindsight `/health`, `/stats`, and `/entities` stayed responsive, but `/v1/default/banks/hermes/memories/recall` timed out for multiple queries even with small payloads.
- The API ignores unsupported `k` parameters, so shrinking top-k at the caller does not reduce work.
- Client-side short timeouts do not cancel the server-side recall work immediately. Metrics showed more than twenty `/memories/recall` requests still in progress after timed-out clients disconnected, which can make later live recall attempts slower.

Fix:

- `tiered_context_injector.py` now has a persistent live-Hindsight circuit breaker.
- Foreground live Hindsight is now explicit opt-in via `MEMORY_LIVE_HINDSIGHT_ENABLED=true`. Production defaults to cache-backed L3 because the live recall endpoint is not currently bounded enough for user-facing requests.
- When live recall is explicitly enabled and then fails or times out, the circuit writes `$AGENT_HOME/metrics/live-hindsight-circuit.json` and skips new foreground live recall attempts for `MEMORY_LIVE_HINDSIGHT_CIRCUIT_COOLDOWN_S` seconds, default `600`.
- While the circuit is open, foreground recall continues to use governance, object, hub, knowledge, and `hindsight_cache` candidates. This prevents repeated user-facing requests or acceptance checks from adding more stuck live recall work.
- A successful future live recall clears the circuit automatically.

Operational guidance:

- If foreground live Hindsight is disabled or the circuit file exists and `open_until` is still in the future, do not treat skipped live recall as data loss. It is protecting the host while cached Hindsight remains available.
- If `/memories/recall` remains slow after the cooldown, investigate Hindsight service internals separately: reranker latency, request cancellation behavior, and recall endpoint concurrency. Do not increase foreground timeout as the primary fix.
- If `hindsight_http_requests_in_progress_requests{endpoint="/v1/default/banks/hermes/memories/recall"}` stays high for multiple minutes, a controlled Hindsight restart can clear abandoned work, but it should remain health-check driven and not tied to swap percentage.

Validation:

- Regression tests cover timeout-triggered circuit opening and circuit-open live recall skipping.
- Full local suite after the fix: `257 passed, 2 skipped`.
- Production deployment found `19` abandoned live recall requests in progress. A controlled `hindsight.service` restart cleared that backlog.
- The first post-deploy acceptance run opened the live recall circuit after one timeout. The second acceptance run had no live recall attempts, no timeout stderr, `ok=true`, and `/memories/recall` in-progress returned to `0`.
- Operator status remained `healthy alerts=0 acceptance=100.0%` after the circuit opened.
- Recheck after the initial circuit expired proved the passive circuit alone was insufficient: the first post-expiry acceptance triggered another live timeout and left one in-progress recall. Foreground live Hindsight was therefore made opt-in by default, and the local regression suite increased to `258 passed, 2 skipped`.

## 2026-07-17 Post-Fix Recheck And gbrain Refresh

Fresh production recheck after making foreground live Hindsight opt-in found no further live-recall regression:

- source checkout, GitHub `main`, and deployed runtime script hashes were aligned at the then-current runtime commit before this documentation-only update;
- `MEMORY_LIVE_HINDSIGHT_ENABLED` was unset in production, so foreground recall stayed on the cache-backed L3 path;
- two consecutive full acceptance runs returned `ok=true`, empty `reason_buckets`, and no timeout stderr;
- `live_hindsight_used` was false for every acceptance row, and Hindsight `/memories/recall` in-progress stayed at `0`;
- `hermes-memory status` remained `healthy alerts=0 acceptance=100.0%`;
- runtime drift remained `healthy`.

The same recheck found a new gbrain maintenance item:

- `gbrain_stale_maintenance.py` reported `missing_embeddings=1`, which is actionable even when the rest of the memory stack is healthy.
- A budgeted refresh with `--refresh-embeddings --stale-budget 100 --missing-budget 0` embedded one stale chunk and ran deorphan cleanup.
- After repair, `missing_embeddings=0`, `orphan_pages_actual=0`, `status=healthy`, and remaining gbrain classifications were info-only upstream panel-counter debt.

Operational note:

- Continue using the budgeted gbrain refresh job rather than `embed --all` on this fixed-size host.
- If foreground live Hindsight is ever re-enabled for experiments, keep it behind `MEMORY_LIVE_HINDSIGHT_ENABLED=true` and monitor `/memories/recall` in-progress before exposing it to user-facing paths.

## 2026-07-17 gbrain Alert Auto-Remediation Closure

The 04:45 UTC `gbrain_stale_action_needed` alert was a real actionable state, not a stale alert artifact.

Root cause:

- The scheduled gbrain refresh ran `embed --stale` before `deorphan`.
- `deorphan` can create or expose a new hub/orphan page chunk after the first embedding pass.
- The script did not re-check missing embeddings after `deorphan`, so the report stayed at `missing_embeddings=1`, `auto_fix_failed=true`.
- `alert_queue.py` only consumed `gbrain-stale-latest.json`; it did not retry a safe repair before sending the user-facing action-needed notification.

Fix:

- `gbrain_stale_maintenance.py` now re-runs `gbrain health` after `deorphan` and embeds any newly missing slugs with `gbrain embed --slugs ...`.
- The repair remains budgeted and targeted. It still avoids unbounded `embed --all` when `--missing-budget 0` is configured for this fixed-size host.
- `alert_queue.py` now performs one guarded gbrain stale repair attempt before building a gbrain action-needed/degraded alert. This is enabled by default with `MEMORY_ALERT_AUTO_REPAIR_GBRAIN=true` and can be disabled with `false/0/no/off`.
- The alert queue uses the same `flock` lock as the scheduled refresh, so it does not start concurrent embedding repair jobs.

Validation:

- Regression tests cover post-deorphan missing embedding repair and alert-queue pre-notification repair.
- Local validation after the fix: `260 passed, 2 skipped`.
- Privacy audit after the fix: `python bin/hermes-memory audit-repo --format json` returned `ok=true`.
- Production repair changed gbrain from `missing_embeddings=1`, `status=action-needed` to `missing_embeddings=0`, `orphan_pages_actual=0`, `status=healthy`.
- Production `alert_queue.py` then emitted a resolved transition and `hermes-memory status` returned `healthy alerts=0 acceptance=100.0%`.

Operational guidance:

- Future gbrain embedding/orphan alerts should be treated as auto-remediated first: the alert queue will retry the bounded repair before notifying Hermes.
- If a future gbrain alert still reaches the user, it means the repair command ran or was blocked by lock/timeout and the latest artifact still contains actionable debt.
- Continue avoiding full-corpus embedding refresh on this host unless there is a verified database-wide embedding gap.

## 2026-07-17 Deep Runtime Recheck And Observability Tightening

Fresh deep runtime analysis found no current memory-system action/degraded incident, but it did find two observability gaps that could mislead future operators.

Evidence:

- `hermes-memory status` returned `healthy alerts=0 acceptance=100.0%`.
- `gbrain-stale-latest.json` was healthy with `missing_embeddings=0`, `orphan_pages_actual=0`, and `auto_fix_succeeded=true`.
- `langsmith-trend-latest.json` still carried the pre-repair gbrain value `latest_gbrain_missing_embeddings=1`.
- `cron-freshness-latest.json` had not been refreshed since June because the `cron-freshness` job was missing from the live root crontab.
- `cron_freshness.py` also checked silent task logs for runtime drift and alert queue even though their real freshness signal is the metrics artifact they write.

Fix:

- `langsmith_trend_report.py` now overlays the latest local `gbrain-stale-latest.json` artifact onto the trend report's `latest_gbrain_*` fields. This prevents repaired gbrain state from being hidden by older LangSmith/local monitor runs.
- `cron_freshness.py` now checks artifact files for silent jobs: runtime drift, alert queue, metrics dashboard, OpenMetrics, SLO rollup, system metrics, gbrain stale refresh, and LangSmith monitor/trend.
- `alert_queue.py` now reads `cron-freshness-latest.json` and raises `cron-freshness:cron_jobs_stale` if any freshness job is degraded or action-needed.
- Production root crontab now includes the idempotent `cron-freshness` schedule:
  `*/15 * * * * AGENT_HOME=$AGENT_HOME /usr/bin/python3 $AGENT_HOME/scripts/cron_freshness.py >> /var/log/cron-freshness.log 2>&1 # cron-freshness`

Validation:

- Regression tests cover cron freshness alert propagation, artifact-backed silent-job checks, and trend gbrain artifact overlay.
- Production trend refresh showed `latest_gbrain_health_score=8`, `latest_gbrain_missing_embeddings=0`, `latest_gbrain_orphans=0`, and `current_acceptance_ok_rate=1.0`.
- Production cron freshness returned `status=healthy` with no stale jobs.
- Production alert queue returned `status=healthy`; only info-level historical acceptance context remained.
- Operator status remained `healthy alerts=0 acceptance=100.0%`.

Operational guidance:

- Treat stale `cron-freshness-latest.json` as an observability incident even when memory recall is otherwise healthy.
- For tasks that are intentionally quiet on success, add or prefer a metrics artifact in `cron_freshness.py`; do not rely on empty log files.
- After any manual gbrain repair, refresh the trend report before reading `latest_gbrain_*` values from LangSmith trend artifacts.

## 2026-07-17 Storage Cross-Check And Missing-Slug Repair Closure

The follow-up deep recheck found one additional real data-quality defect behind the trend-layer `latest_storage_ok=false` signal.

Evidence:

- Live `memory_storage_cross_check.py` returned `ok=false` with `gbrain_orphans`.
- A gbrain repair run reduced actionable orphans to zero, but then reported `missing_embeddings=1`.
- Direct database inspection showed the missing chunk belonged to `hub-orphans-sessions`.
- The helper query in `find_missing_embedding_slugs()` returned no slugs because PostgreSQL rejected `SELECT DISTINCT p.slug ... ORDER BY p.updated_at`.

Fix:

- `gbrain_stale_maintenance.py` now uses a `WHERE EXISTS` page query for missing-embedding slug discovery, avoiding the PostgreSQL `DISTINCT`/`ORDER BY` restriction.
- `memory_storage_cross_check.py` now writes a latest artifact to `$AGENT_HOME/metrics/storage-cross-check-latest.json` every time it runs.
- `langsmith_trend_report.py` now overlays `storage-cross-check-latest.json` before reporting `latest_storage_ok` and gbrain summary fields.

Validation:

- Production gbrain repair found `hub-orphans-sessions`, embedded the missing chunk, and returned `status=healthy`.
- Production storage cross-check returned `ok=true`, empty `warnings`, `missing_embeddings=0`, and `orphan_pages_actual=0`.
- Production trend refresh returned `latest_storage_ok=true`, `latest_gbrain_missing_embeddings=0`, and `current_acceptance_ok_rate=1.0`.
- Production alert queue remained `healthy`; only info-level historical acceptance context remained.
- Operator status remained `healthy alerts=0 acceptance=100.0%`.

Operational guidance:

- If `latest_storage_ok=false` appears again while gbrain stale is healthy, run storage cross-check first and inspect `$AGENT_HOME/metrics/storage-cross-check-latest.json`; do not rely on older LangSmith monitor snapshots.
- Keep missing-embedding repair targeted by slug. Do not fall back to full-corpus embedding unless the slug query returns no actionable rows and direct database inspection confirms a wider gap.

## 2026-07-17 Closed-Loop Recheck Until No Pending Action

An additional closed-loop recheck was run after the storage and gbrain fixes.

Evidence:

- The current monitor run returned `returncode=0`.
- `storage-cross-check-latest.json` returned `ok=true`, empty `warnings`, `missing_embeddings=0`, and `orphan_pages_actual=0`.
- `langsmith-trend-latest.json` returned `latest_storage_ok=true`, `latest_gbrain_missing_embeddings=0`, and `current_acceptance_ok_rate=1.0`.
- `cron-freshness-latest.json` returned `healthy` with no stale jobs.
- `alert_queue.py` returned `healthy`; only info-level historical acceptance context remained.
- `hermes-memory status` returned `healthy alerts=0 acceptance=100.0%`.

Follow-up hardening:

- `cron_freshness.py` now includes `storage_cross_check` and validates `$AGENT_HOME/metrics/storage-cross-check-latest.json` freshness.
- This closes the remaining observability gap where trend could depend on a stale storage artifact without the freshness layer noticing.

Operational guidance:

- A future stale `storage_cross_check` freshness failure should be treated as an observability problem first. It does not necessarily mean memory recall is broken, but it does mean trend storage fields may be stale.
- The current known non-action item is `langsmith-trend:historical_acceptance_failures` at `info` severity. It is retained for history and should not page the operator while current acceptance remains 100%.

## 2026-07-17 Stale Pages Severity Decision

Hermes reported a remaining gbrain risk: `Stale pages: 1138`, with a recommendation to run a full embedding job or `sync_brain()`.

Decision:

- Do not run full-corpus embedding refresh or full `sync_brain()` for this signal alone.
- Keep the current bounded maintenance path: `gbrain_stale_maintenance.py --refresh-embeddings --stale-budget 100 --missing-budget 0`.
- Treat `stale_health_counter_not_embedding_stale` as info-level upstream health-panel debt unless a discriminating probe finds actionable stale chunks.

Evidence:

- `gbrain health` reported `Embed coverage: 100.0%` and `Missing embeddings: 0`.
- `gbrain_stale_maintenance.py` returned `status=healthy` with only info-level classifications.
- A bounded discriminating probe using `embed --stale --limit 25` returned `Embedded 0 chunks (0 stale found)`.
- Storage cross-check returned `ok=true` and empty `warnings`.
- Trend reported `latest_storage_ok=true`, `latest_gbrain_missing_embeddings=0`, and `current_acceptance_ok_rate=1.0`.
- Operator status returned `healthy alerts=0 acceptance=100.0%`.

Reasoning:

- The raw `Stale pages` counter is not enough to justify heavy production work on the current fixed-size host.
- The actionable condition is `missing_embeddings > 0`, real orphan pages, or a bounded `embed --stale` run that finds chunks to refresh.
- When `embed --stale` finds zero chunks and embedding coverage is 100%, the remaining stale count should be treated as gbrain health accounting/reporting debt, not as a recall-breaking incident.

Operational guidance:

- Do not escalate `Stale pages` to critical by count alone.
- If `embed --stale` returns nonzero chunks, let the bounded maintenance job process them.
- If `missing_embeddings > 0`, use targeted slug repair first.
- Avoid unbounded `embed --all` or full `sync_brain()` unless direct evidence shows a database-wide embedding gap.

## 2026-07-21 Pipeline Business-Failure Alerting Hotfix

- Task wrappers now persist local latest business status under `$AGENT_HOME/metrics/langsmith-task-<task>-latest.json` before optional LangSmith publish.
- `langsmith_trend_report.py` merges local latest task status ahead of remote LangSmith history, so current successful runs can clear action-needed task alerts even if LangSmith ingestion is quota-limited.
- `alert_queue.py` escalates latest task business failures to `action-needed`; historical task failures remain `info`.
- `archive_sessions.py` now sets SQLite `busy_timeout` and emits per-session publish progress for intermittent stall diagnosis.
- `memory_guardian.py` adds `ACTIVE_ARCHIVE=0.78` while preserving overflow grace semantics.
- Production-specific capacity should be supplied by environment, for example `MEMORY_GUARDIAN_NODE_LIMIT`, not hard-coded into public defaults.

Verification:
- Main worktree: `python -m pytest -q` -> 268 passed, 2 skipped.
- Main worktree: `python bin/hermes-memory audit-repo --format json` -> ok true.
- Production runtime: task latest status for archive/session/summary reported `business_ok=true`; health summary remained healthy with only historical info alerts.

## 2026-07-21 Three-Way Consistency Recheck

- Local publishable worktree and GitHub `origin/main` matched at verification time; the publishable worktree was clean.
- Full test gate previously recorded as `268 passed, 2 skipped`; privacy audit was `ok=true`.
- Production source/runtime content check: 8 source files and 5 runtime scripts matched the GitHub main SHA256 set; mismatch count `0`.
- Production source Git metadata remains at older base with dirty production files by design; do not hard reset it unless preserving/relocating production-only continuation notes first. Runtime code content is aligned and should be treated as the operational truth.
- Current runtime validation should continue to prefer generated health artifacts under `$AGENT_HOME/metrics` plus alert queue output, not stale historical LangSmith aggregates alone.

## 2026-07-23 Three-Way Runtime Drift Recheck

- Rechecked local publishable worktree, GitHub `origin/main`, production source, and production runtime scripts. Binary hash drift was mostly Windows-vs-Linux line-ending noise; normalized LF comparison reduced source drift to targeted runtime/config files.
- Public code changes: `hindsight-service.py` now follows the active Hermes model provider configuration at runtime while keeping conservative Hindsight worker/LLM limits; importing the wrapper is side-effect-free for tests. `memory_watermark.py` now defaults to `$HOME/.hermes` when `AGENT_HOME`/`HERMES_HOME` are unset.
- Production-only drift handling: legacy runtime helpers with hard-coded production paths or personal domain labels should be replaced by the public portable versions during deployment, not copied back into GitHub.
- Runtime drift alert semantics: `repo_dirty` is now `info` when the deploy audit shows no missing or mismatched runtime scripts, so production-only continuation notes do not create false degraded alerts.
- Cron freshness semantics: `gbrain_stale_refresh` uses an 8-hour freshness threshold to match its 6-hour production schedule plus operational buffer.
- Verification before publish: targeted regression tests passed; full local gate reported `272 passed, 2 skipped`; privacy audit returned `ok=true`.
- Deployment rule: server source and runtime should be synced from GitHub main for code, while production data/config/continuation notes remain server-local.
