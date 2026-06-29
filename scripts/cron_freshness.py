#!/usr/bin/env python3
"""Report freshness of production cron-driven artifacts and logs."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_OUTPUT = AGENT_HOME / "metrics" / "cron-freshness-latest.json"

CHECKS = [
    {"name": "langsmith_monitor", "path": Path("/var/log/langsmith-monitor.log"), "max_age_s": 8 * 3600},
    {"name": "langsmith_trend", "path": Path("/var/log/langsmith-trend.log"), "max_age_s": 8 * 3600},
    {"name": "auto_summary", "path": Path("/var/log/auto-summary.log"), "max_age_s": 8 * 3600},
    {"name": "session_gbrain", "path": Path("/var/log/session-gbrain.log"), "max_age_s": 8 * 3600},
    {"name": "archive_sessions", "path": Path("/var/log/archive-sessions.log"), "max_age_s": 30 * 3600},
    {"name": "runtime_drift_check", "path": Path("/var/log/runtime-drift-check.log"), "max_age_s": 8 * 3600},
    {"name": "alert_queue", "path": Path("/var/log/alert-queue.log"), "max_age_s": 8 * 3600},
    {"name": "metrics_dashboard", "path": Path("/var/log/metrics-dashboard.log"), "max_age_s": 8 * 3600},
    {"name": "openmetrics_exporter", "path": Path("/var/log/hermes-openmetrics-exporter.log"), "max_age_s": 8 * 3600},
    {"name": "slo_rollup", "path": Path("/var/log/hermes-slo-rollup.log"), "max_age_s": 3600},
    {"name": "telegram_lang_sync", "path": Path("/var/log/telegram-lang-sync.log"), "max_age_s": 3600},
    {"name": "prometheus_alert_sync", "path": Path("/var/log/prometheus-alert-sync.log"), "max_age_s": 1800},
    {"name": "system_metrics", "path": Path("/var/log/system-metrics.log"), "max_age_s": 7200},
    {"name": "gbrain_stale_refresh", "path": Path("/var/log/gbrain-stale.log"), "max_age_s": 7200},
    {"name": "state_db_checkpoint", "path": Path("/var/log/hermes-state-db-checkpoint.log"), "max_age_s": 30 * 3600},
    {"name": "snapshot_retention", "path": Path("/var/log/hermes-snapshot-retention.log"), "max_age_s": 30 * 3600},
]


def classify_age(age_s: float | None, max_age_s: int) -> str:
    if age_s is None:
        return "action-needed"
    if age_s <= max_age_s:
        return "healthy"
    if age_s <= max_age_s * 2:
        return "degraded"
    return "action-needed"


def build_report() -> dict:
    now = time.time()
    jobs = []
    for row in CHECKS:
        path = row["path"]
        mtime = path.stat().st_mtime if path.exists() else None
        age_s = None if mtime is None else round(now - mtime, 1)
        status = classify_age(age_s, int(row["max_age_s"]))
        jobs.append(
            {
                "name": row["name"],
                "path": str(path),
                "exists": path.exists(),
                "max_age_s": int(row["max_age_s"]),
                "age_s": age_s,
                "status": status,
                "updated_at": None if mtime is None else datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            }
        )
    overall = "healthy"
    if any(job["status"] == "action-needed" for job in jobs):
        overall = "action-needed"
    elif any(job["status"] == "degraded" for job in jobs):
        overall = "degraded"
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": overall,
        "ok": overall == "healthy",
        "jobs": jobs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    payload = build_report()
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] != "action-needed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
