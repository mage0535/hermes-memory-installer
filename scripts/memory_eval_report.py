#!/usr/bin/env python3
"""Evaluate Hermes memory health from local monitor snapshots and LangSmith runs.

Local Hermes metrics are the authoritative live signal. Remote LangSmith runs are
kept as trend context, but missing remote data must not turn a healthy local
monitor into a 0/100 report.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_NAME = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")
DEFAULT_LIMIT = 100
CURRENT_WINDOW = max(1, int(os.environ.get("MEMORY_EVAL_CURRENT_WINDOW", "5")))
AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_LOCAL_MONITOR = AGENT_HOME / "metrics" / "langsmith-monitor-latest.json"
DEFAULT_LOCAL_TREND = AGENT_HOME / "metrics" / "langsmith-trend-latest.json"


def fetch_runs(limit: int = DEFAULT_LIMIT) -> list[Any]:
    try:
        from langsmith import Client

        return list(Client().list_runs(project_name=PROJECT_NAME, limit=min(limit, 100)))
    except Exception:
        return []


def load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _acceptance_payload(run: Any) -> dict[str, Any]:
    outputs = getattr(run, "outputs", None) or {}
    acceptance = outputs.get("acceptance", {}) if isinstance(outputs, dict) else {}
    payload = acceptance.get("payload", acceptance) if isinstance(acceptance, dict) else {}
    return payload if isinstance(payload, dict) else {}


def _summarize_payloads(payloads: list[dict[str, Any]], source: str) -> dict[str, Any]:
    if not payloads:
        return {"status": "nodata", "message": "No monitor data", "source": source}

    acceptance: list[bool] = []
    lags: list[int] = []
    guardian_levels: list[str] = []
    guardian_usages: list[float] = []
    l2_counts: list[int] = []
    l3_counts: list[int] = []
    latencies: list[float] = []
    storage_ok: list[bool] = []
    for payload in payloads:
        acceptance.append(payload.get("ok") is True)
        guardian = payload.get("guardian", {})
        if isinstance(guardian, dict):
            if isinstance(guardian.get("hindsight_sync_lag_seconds"), (int, float)):
                lags.append(int(guardian["hindsight_sync_lag_seconds"]))
            if guardian.get("level"):
                guardian_levels.append(str(guardian["level"]))
            if isinstance(guardian.get("usage_pct"), (int, float)):
                guardian_usages.append(float(guardian["usage_pct"]))
        storage = payload.get("storage_cross_check")
        if isinstance(storage, dict) and "ok" in storage:
            storage_ok.append(storage.get("ok") is True)
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
        "source": source,
        "sample_count": len(payloads),
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
            "action_count": guardian_levels.count("action"),
        },
        "guardian_usage_pct": guardian_usages[0] if guardian_usages else None,
        "storage_ok": storage_ok[0] if storage_ok else None,
        "recall_quality": {
            "avg_l2_per_query": round(mean(l2_counts), 1) if l2_counts else None,
            "avg_l3_per_query": round(mean(l3_counts), 1) if l3_counts else None,
            "avg_latency_s": round(mean(latencies), 2) if latencies else None,
        },
    }


def analyze_monitor_trend(runs: list[Any]) -> dict[str, Any]:
    monitors = [run for run in runs if getattr(run, "name", None) == "memory-sidecar-monitor"]
    return _summarize_payloads([_acceptance_payload(run) for run in monitors], "langsmith")


def analyze_local_monitor(snapshot: dict[str, Any]) -> dict[str, Any]:
    acceptance = snapshot.get("acceptance", {})
    payload = acceptance.get("payload", acceptance) if isinstance(acceptance, dict) else {}
    if isinstance(payload, dict) and "ok" not in payload and acceptance.get("returncode") == 0:
        payload = dict(payload)
        payload["ok"] = True
    if isinstance(payload, dict) and isinstance(snapshot.get("storage_cross_check"), dict):
        payload = dict(payload)
        payload.setdefault("storage_cross_check", snapshot["storage_cross_check"])
    return _summarize_payloads([payload] if isinstance(payload, dict) and payload else [], "local_monitor")


def merge_trend_context(monitor: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    trend_monitor = trend.get("monitor") if isinstance(trend.get("monitor"), dict) else {}
    if not trend_monitor:
        return monitor
    # 2026-08-06 修复：trend 快照过期（>1h）时不覆盖新鲜的 local_monitor 数据。
    # 背景：LangSmith token 失效后 trend 文件停留在旧快照（acceptance 0%），
    # 无条件覆盖导致已恢复的服务被误判为 degraded。1h 内生成的 trend 才可信。
    captured = trend.get("captured_at")
    if isinstance(captured, str):
        try:
            captured_ts = datetime.fromisoformat(captured.replace("Z", "+00:00")).timestamp()
            if time.time() - captured_ts > 3600:
                return monitor
        except Exception:
            pass
    merged = dict(monitor)
    for key in (
        "acceptance_ok_rate",
        "current_acceptance_ok_rate",
        "current_window",
        "historical_acceptance_failure_count",
        "recent_acceptance_ok_rate",
        "failure_reasons",
        "current_failure_reasons",
    ):
        if key in trend_monitor:
            merged[key] = trend_monitor[key]
    if "lag" in trend_monitor and isinstance(trend_monitor["lag"], dict):
        lag = dict(merged.get("hindsight_lag") or {})
        lag.setdefault("latest_s", trend_monitor["lag"].get("latest_s"))
        lag.setdefault("max_s", trend_monitor["lag"].get("max_s"))
        merged["hindsight_lag"] = lag
    return merged


def analyze_task_performance(runs: list[Any], trend: dict[str, Any] | None = None) -> dict[str, Any]:
    if trend and isinstance(trend.get("tasks"), dict):
        return trend["tasks"]
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
    if isinstance(lag, (int, float)) and lag > 43200:
        score -= 10
        issues.append(f"Hindsight sync lag is {lag:.0f}s")
    elif isinstance(lag, (int, float)):
        strengths.append(f"Hindsight sync lag is {lag:.0f}s")

    latest_guardian = monitor.get("guardian_levels", {}).get("latest")
    if latest_guardian == "critical":
        score -= 20
        issues.append("Guardian is currently critical")
    elif latest_guardian == "action":
        score -= 10
        usage = monitor.get("guardian_usage_pct")
        if isinstance(usage, (int, float)):
            issues.append(f"Guardian is in action band at {usage:.1f}%")
        else:
            issues.append("Guardian is in action band")
    elif latest_guardian in {"active_archive", "warn"}:
        score -= 5
        issues.append(f"Guardian is currently {latest_guardian}")
    else:
        strengths.append("Guardian is currently within capacity")

    recall = monitor.get("recall_quality", {})
    if recall.get("avg_l3_per_query") == 0:
        score -= 5
        issues.append("L3 recall has no current candidates")

    for task_name, task in tasks.items():
        if not isinstance(task, dict):
            continue
        if int(task.get("recent_business_failure_count") or 0) > 0 or task.get("latest_business_ok") is False:
            score -= 10
            issues.append(f"Recent business failure in {task_name}")

    score = max(0, score)
    level = "healthy" if score >= 85 else "degraded" if score >= 60 else "unhealthy"
    return {"score": score, "level": level, "strengths": strengths, "issues": issues}


def build_report(
    runs: list[Any],
    local_monitor: dict[str, Any] | None = None,
    local_trend: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data_sources: list[str] = []
    if local_monitor:
        monitor = analyze_local_monitor(local_monitor)
        data_sources.append("local_monitor")
    else:
        monitor = analyze_monitor_trend(runs)
        if monitor.get("status") != "nodata":
            data_sources.append("langsmith")
    if local_trend:
        monitor = merge_trend_context(monitor, local_trend)
        data_sources.append("local_trend")
    tasks = analyze_task_performance(runs, local_trend)
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT_NAME,
        "run_count": len(runs),
        "data_sources": data_sources,
        "health": evaluate_health(monitor, tasks),
        "monitor": monitor,
        "tasks": tasks,
    }


def format_report(report: dict[str, Any]) -> str:
    health = report["health"]
    monitor = report["monitor"]
    lines = [
        "????? (Hindsight) ??????",
        "",
        f"?????{health['score']}/100 - {health['level'].upper()}",
        f"????{', '.join(report.get('data_sources') or ['none'])}",
        f"?? Acceptance ????{monitor.get('current_acceptance_ok_rate', 0):.0%} "
        f"({monitor.get('current_window', 0)} latest runs)",
        f"?? Acceptance ????{monitor.get('acceptance_ok_rate', 0):.0%} "
        "(trend only)",
        f"?? Guardian?{monitor.get('guardian_levels', {}).get('latest', 'unknown')}",
    ]
    if health["issues"]:
        lines.extend(["", "Current issues:", *[f"- {item}" for item in health["issues"]]])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory evaluation report")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--local-monitor", default=str(DEFAULT_LOCAL_MONITOR))
    parser.add_argument("--local-trend", default=str(DEFAULT_LOCAL_TREND))
    args = parser.parse_args()
    local_monitor = load_json(Path(args.local_monitor))
    local_trend = load_json(Path(args.local_trend))
    report = build_report(fetch_runs(args.limit), local_monitor=local_monitor, local_trend=local_trend)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return {"healthy": 0, "degraded": 1, "unhealthy": 2, "unknown": 1}[report["health"]["level"]]


if __name__ == "__main__":
    raise SystemExit(main())
