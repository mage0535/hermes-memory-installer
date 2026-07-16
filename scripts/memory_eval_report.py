#!/usr/bin/env python3
"""Evaluate Hermes memory health from LangSmith monitor runs.

The latest monitoring window determines the live health state.  Older runs are
preserved as trend context so a recovered service is not reported as degraded.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_NAME = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")
DEFAULT_LIMIT = 100
CURRENT_WINDOW = max(1, int(os.environ.get("MEMORY_EVAL_CURRENT_WINDOW", "5")))


def fetch_runs(limit: int = DEFAULT_LIMIT) -> list[Any]:
    from langsmith import Client

    return list(Client().list_runs(project_name=PROJECT_NAME, limit=min(limit, 100)))


def _acceptance_payload(run: Any) -> dict[str, Any]:
    outputs = getattr(run, "outputs", None) or {}
    acceptance = outputs.get("acceptance", {}) if isinstance(outputs, dict) else {}
    payload = acceptance.get("payload", acceptance) if isinstance(acceptance, dict) else {}
    return payload if isinstance(payload, dict) else {}


def analyze_monitor_trend(runs: list[Any]) -> dict[str, Any]:
    monitors = [run for run in runs if getattr(run, "name", None) == "memory-sidecar-monitor"]
    if not monitors:
        return {"status": "nodata", "message": "No monitor data"}

    acceptance = []
    lags = []
    guardian_levels = []
    l2_counts = []
    l3_counts = []
    latencies = []
    for run in monitors:
        payload = _acceptance_payload(run)
        acceptance.append(payload.get("ok") is True)
        guardian = payload.get("guardian", {})
        if isinstance(guardian, dict):
            if isinstance(guardian.get("hindsight_sync_lag_seconds"), (int, float)):
                lags.append(int(guardian["hindsight_sync_lag_seconds"]))
            if guardian.get("level"):
                guardian_levels.append(str(guardian["level"]))
        recalls = payload.get("recalls", [])
        if isinstance(recalls, list):
            for row in recalls:
                if not isinstance(row, dict):
                    continue
                if isinstance(row.get("l2_count"), (int, float)):
                    l2_counts.append(int(row["l2_count"]))
                if isinstance(row.get("l3_count"), (int, float)):
                    l3_counts.append(int(row["l3_count"]))
                timings = row.get("timings", {})
                if isinstance(timings, dict) and isinstance(timings.get("total_s"), (int, float)):
                    latencies.append(float(timings["total_s"]))

    current = acceptance[:CURRENT_WINDOW]
    return {
        "sample_count": len(monitors),
        "acceptance_ok_rate": round(sum(acceptance) / len(acceptance), 3),
        "current_acceptance_ok_rate": round(sum(current) / len(current), 3),
        "current_window": len(current),
        "historical_acceptance_failure_count": acceptance.count(False),
        "hindsight_lag": {
            "latest_s": lags[0] if lags else None,
            "avg_s": round(mean(lags), 0) if lags else None,
            "max_s": max(lags) if lags else None,
        },
        "guardian_levels": {
            "latest": guardian_levels[0] if guardian_levels else None,
            "critical_count": guardian_levels.count("critical"),
        },
        "recall_quality": {
            "avg_l2_per_query": round(mean(l2_counts), 1) if l2_counts else None,
            "avg_l3_per_query": round(mean(l3_counts), 1) if l3_counts else None,
            "avg_latency_s": round(mean(latencies), 2) if latencies else None,
        },
    }


def analyze_task_performance(runs: list[Any]) -> dict[str, Any]:
    tasks: dict[str, dict[str, int]] = {}
    for run in runs:
        name = getattr(run, "name", None)
        if not name or name == "memory-sidecar-monitor":
            continue
        task = tasks.setdefault(str(name), {"count": 0, "errors": 0})
        task["count"] += 1
        if getattr(run, "status", "") != "success" or getattr(run, "error", None):
            task["errors"] += 1
    return tasks


def evaluate_health(monitor: dict[str, Any], tasks: dict[str, Any]) -> dict[str, Any]:
    if monitor.get("status") == "nodata":
        return {"score": 0, "level": "unknown", "strengths": [], "issues": ["No monitor data"]}

    score = 100
    issues: list[str] = []
    strengths: list[str] = []
    current_rate = monitor.get("current_acceptance_ok_rate")
    if isinstance(current_rate, (int, float)) and current_rate < 0.95:
        score -= 20
        issues.append(f"Current acceptance rate is {current_rate:.0%}")
    else:
        strengths.append("Current acceptance window is healthy")

    lag = monitor.get("hindsight_lag", {}).get("latest_s")
    if isinstance(lag, (int, float)) and lag > 3600:
        score -= 10
        issues.append(f"Hindsight sync lag is {lag:.0f}s")
    elif isinstance(lag, (int, float)):
        strengths.append(f"Hindsight sync lag is {lag:.0f}s")

    latest_guardian = monitor.get("guardian_levels", {}).get("latest")
    if latest_guardian == "critical":
        score -= 10
        issues.append("Guardian is currently critical")
    else:
        strengths.append("Guardian is currently within capacity")

    recall = monitor.get("recall_quality", {})
    if recall.get("avg_l3_per_query") == 0:
        score -= 5
        issues.append("L3 recall has no current candidates")
    score = max(0, score)
    level = "healthy" if score >= 85 else "degraded" if score >= 60 else "unhealthy"
    return {"score": score, "level": level, "strengths": strengths, "issues": issues}


def build_report(runs: list[Any]) -> dict[str, Any]:
    monitor = analyze_monitor_trend(runs)
    tasks = analyze_task_performance(runs)
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT_NAME,
        "run_count": len(runs),
        "health": evaluate_health(monitor, tasks),
        "monitor": monitor,
        "tasks": tasks,
    }


def format_report(report: dict[str, Any]) -> str:
    health = report["health"]
    monitor = report["monitor"]
    lines = [
        "外挂记忆体 (Hindsight) 运行状况摘要",
        "",
        f"综合评分：{health['score']}/100 - {health['level'].upper()}",
        f"当前 Acceptance 通过率：{monitor.get('current_acceptance_ok_rate', 0):.0%} "
        f"({monitor.get('current_window', 0)} latest runs)",
        f"历史 Acceptance 通过率：{monitor.get('acceptance_ok_rate', 0):.0%} "
        "(trend only)",
        f"当前 Guardian：{monitor.get('guardian_levels', {}).get('latest', 'unknown')}",
    ]
    if health["issues"]:
        lines.extend(["", "Current issues:", *[f"- {item}" for item in health["issues"]]])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory evaluation report")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(fetch_runs(args.limit))
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return {"healthy": 0, "degraded": 1, "unhealthy": 2, "unknown": 1}[report["health"]["level"]]


if __name__ == "__main__":
    raise SystemExit(main())
