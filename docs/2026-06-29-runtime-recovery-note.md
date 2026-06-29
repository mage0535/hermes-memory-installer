## 2026-06-29 Runtime Recovery, Drift Closure, and Resource Trim

Completed in this round:

- Synced runtime-only fixes back into the deployment repository and production script directory, including `auto_archive_sessions.py`, `profile_isolation_check.py`, `rotate_dashboard_token.py`, and `system_metrics_collector.py`.
- Fixed `dashboard-info` / CLI default home drift to `.hermes` and aligned deploy manifests with the actual production runtime.
- Fixed dashboard token rotation so rotating the token now restarts `hermes-metrics-dashboard.service` and Prometheus, eliminating the stale-token 401 condition.
- Fixed runtime drift caused by an unsynced `langsmith_trend_report.py` threshold change and committed all server-repo changes; drift status is now healthy.
- Increased gbrain publish timeouts in `session_to_gbrain.py`, then verified `archive_sessions.py --batch 1` succeeds on the previously stuck archive watermark.
- Repaired Hindsight startup by downgrading `tokenizers` in the Hermes venv to `0.22.1`, which restored compatibility with the installed `transformers` / `sentence-transformers` stack.
- Added Hindsight readiness waiting to `memory_guardian.py`; `memory-guardian.service` now completes successfully instead of failing during Hindsight cold start.
- Fixed `memory_governance_rebuild.py` so `hindsight_headers()` is defined before use, then forced a governance rebuild to refresh `hindsight_synced_at`.
- Re-ran LangSmith monitor + trend report and cleared the `hindsight_lag` alert; current operator status is healthy.
- Reduced log pressure by vacuuming systemd journal to 120M and truncating oversized historical gbrain embedding logs.

Current production state after verification:

- `hindsight.service`: active and healthy on the local runtime bind address.
- `memory-guardian.timer`: active; `memory-guardian.service` last run succeeded.
- `hermes-metrics-dashboard.service`: active; token-gated dashboard access works again.
- `Prometheus` / `Grafana`: active.
- `hermes-memory status`: `healthy alerts=0 acceptance=100.0% queue_growth=2 dead_letter_replay=unknown recall_p95_s=26.713 forward=ok`.
- `runtime-drift-latest.json`: healthy.
- `health-summary-latest.json`: healthy.

Remaining non-blocking gaps observed:

- Dashboard overall status can still show `action-needed` when `gbrain-stale-latest.json` reports missing embeddings / stale pages. This is a real gbrain quality gap, not a dashboard bug.
- `gbrain_stale_maintenance.py --refresh-embeddings` launches a long-running `gbrain embed --stale` task; it should be treated as background maintenance, not as an instant repair.
- `sync_embeddings.py --stats` assumes a `message_embeddings` table in `semantics.db` and currently errors on this host. That script needs schema-aware fallback logic before it can be used as an operator-safe tool.
- `state.db` remains about 4.0G and the runtime snapshot directory remains about 3.9G. These were intentionally not deleted today because they still provide rollback value. A follow-up should add explicit retention rules before pruning.

Recommended next implementation slice:

1. Make `sync_embeddings.py` schema-aware or retire it if `semantics.db` is no longer authoritative.
2. Split gbrain maintenance into two explicit modes: quick report vs background repair, and persist progress so dashboard status reflects in-flight maintenance.
3. Add retention policy for runtime state snapshots and large historical logs, with configurable keep-count / keep-days.
4. Investigate why gbrain still reports `missing_embeddings=131` and `orphan_pages_actual=2` after deorphan scheduling is in place; likely needs one full embedding pass plus targeted orphan cleanup.
