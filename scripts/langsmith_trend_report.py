#!/usr/bin/env python3
"""Summarize recent LangSmith sidecar runs into privacy-preserving trend metrics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_NAME = os.environ.get("LANGSMITH_PROJECT", "hermes-memory-installer")
DEFAULT_LAG_THRESHOLD_S = int(os.environ.get("MEMORY_LAG_WARN_THRESHOLD_S", "3600"))
AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
DEFAULT_LOCAL_MONITOR = AGENT_HOME / "metrics" / "langsmith-monitor-latest.json"


class LocalRun:
    def __init__(self, name: str, outputs: dict):
        self.name = name
        self.status = "success"
        self.outputs = outputs
        self.error = None
        self.start_time = None
        self.end_time = None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 3)


def output_payload(run: Any) -> dict:
    outputs = getattr(run, "outputs", None)
    return outputs if isinstance(outputs, dict) else {}


def elapsed_from_run(run: Any) -> float | None:
    payload = output_payload(run)
    value = payload.get("elapsed_s")
    if isinstance(value, (int, float)):
        return float(value)
    start = getattr(run, "start_time", None)
    end = getattr(run, "end_time", None)
    if start and end:
        try:
            return round((end - start).total_seconds(), 3)
        except Exception:
            return None
    return None


def summarize_values(values: list[float]) -> dict:
    return {
        "count": len(values),
        "avg_s": round(mean(values), 3) if values else None,
        "p95_s": percentile(values, 95),
        "max_s": round(max(values), 3) if values else None,
    }


def acceptance_payload_from_monitor(payload: dict) -> dict:
    acceptance = payload.get("acceptance") if isinstance(payload.get("acceptance"), dict) else {}
    nested = acceptance.get("payload") if isinstance(acceptance.get("payload"), dict) else {}
    return nested or acceptance


def acceptance_reason_codes(acceptance: dict) -> list[str]:
    if not acceptance:
        return ["acceptance_missing"]
    if acceptance.get("ok") is True:
        return []
    errors = acceptance.get("errors") if isinstance(acceptance.get("errors"), list) else []
    if errors:
        codes = []
        for error in errors:
            text = str(error).lower()
            if "guardian" in text:
                codes.append("guardian")
            elif "hindsight" in text or "lag" in text:
                codes.append("hindsight_lag")
            elif "knowledge" in text:
                codes.append("knowledge_recall")
            elif "recall" in text or "candidate" in text or "top title" in text:
                codes.append("recall_coverage")
            else:
                codes.append("acceptance_error")
        return sorted(set(codes))
    return ["acceptance_not_ok"]


def lag_values_from_monitor_runs(monitor_runs: list[Any]) -> list[int]:
    values = []
    for run in monitor_runs:
        payload = output_payload(run)
        acceptance = acceptance_payload_from_monitor(payload)
        guardian = acceptance.get("guardian") if isinstance(acceptance.get("guardian"), dict) else {}
        value = guardian.get("hindsight_sync_lag_seconds")
        if isinstance(value, (int, float)):
            values.append(int(value))
    return values


def lag_summary(values: list[int], threshold_s: int = DEFAULT_LAG_THRESHOLD_S) -> dict:
    consecutive = 0
    for value in values:
        if value > threshold_s:
            consecutive += 1
        else:
            break
    status = "healthy"
    if consecutive >= 2:
        status = "action-needed"
    elif values and values[0] > threshold_s:
        status = "degraded"
    return {
        "threshold_s": threshold_s,
        "latest_s": values[0] if values else None,
        "max_s": max(values) if values else None,
        "over_threshold_count": sum(1 for value in values if value > threshold_s),
        "consecutive_over_threshold": consecutive,
        "status": status,
    }


def monitor_metrics(runs: list[Any]) -> dict:
    monitor_runs = [run for run in runs if getattr(run, "name", None) == "memory-sidecar-monitor"]
    acceptance_ok = []
    acceptance_elapsed = []
    recall_elapsed = []
    latest_guardian = {}
    latest_gbrain = {}
    latest_storage_ok = None
    failure_reasons: dict[str, int] = {}
    recent_failures = []
    recall_stage_timings: dict[str, list[float]] = {"l2_s": [], "l3_s": [], "fusion_s": [], "total_s": []}

    for run in monitor_runs:
        payload = output_payload(run)
        acceptance = payload.get("acceptance") if isinstance(payload.get("acceptance"), dict) else {}
        acceptance_payload = acceptance_payload_from_monitor(payload)
        storage = payload.get("storage_cross_check") if isinstance(payload.get("storage_cross_check"), dict) else {}
        ok_value = acceptance.get("ok")
        if ok_value is None:
            ok_value = acceptance_payload.get("ok")
        acceptance_ok.append(bool(ok_value))
        reason_codes = acceptance_reason_codes(acceptance_payload)
        for code in reason_codes:
            failure_reasons[code] = failure_reasons.get(code, 0) + 1
        if reason_codes:
            recent_failures.append(
                {
                    "run_name": getattr(run, "name", None),
                    "status": getattr(run, "status", None),
                    "reasons": reason_codes,
                    "returncode": acceptance.get("returncode"),
                    "elapsed_s": acceptance.get("elapsed_s"),
                }
            )
        if isinstance(acceptance.get("elapsed_s"), (int, float)):
            acceptance_elapsed.append(float(acceptance["elapsed_s"]))
        guardian = acceptance.get("guardian") or acceptance_payload.get("guardian")
        if isinstance(guardian, dict) and not latest_guardian:
            latest_guardian = guardian
        storage_payload = storage.get("payload") if isinstance(storage.get("payload"), dict) else {}
        if storage_payload:
            if latest_storage_ok is None:
                latest_storage_ok = bool(storage_payload.get("ok"))
            gbrain = storage_payload.get("gbrain")
            if isinstance(gbrain, dict) and not latest_gbrain:
                latest_gbrain = gbrain
        recalls = payload.get("recalls") if isinstance(payload.get("recalls"), list) else []
        for row in recalls:
            if isinstance(row, dict) and isinstance(row.get("elapsed_s"), (int, float)):
                recall_elapsed.append(float(row["elapsed_s"]))
        acceptance_recalls = acceptance_payload.get("recalls") if isinstance(acceptance_payload.get("recalls"), list) else []
        for row in acceptance_recalls:
            timings = row.get("timings") if isinstance(row, dict) and isinstance(row.get("timings"), dict) else {}
            for key in recall_stage_timings:
                if isinstance(timings.get(key), (int, float)):
                    recall_stage_timings[key].append(float(timings[key]))

    return {
        "count": len(monitor_runs),
        "acceptance_ok_rate": round(sum(acceptance_ok) / len(acceptance_ok), 3) if acceptance_ok else None,
        "acceptance_latency": summarize_values(acceptance_elapsed),
        "recall_latency": summarize_values(recall_elapsed),
        "latest_guardian_level": latest_guardian.get("level"),
        "latest_guardian_usage_pct": latest_guardian.get("usage_pct"),
        "latest_hindsight_lag_s": latest_guardian.get("hindsight_sync_lag_seconds"),
        "latest_storage_ok": latest_storage_ok,
        "latest_gbrain_health_score": latest_gbrain.get("health_score"),
        "latest_gbrain_missing_embeddings": latest_gbrain.get("missing_embeddings"),
        "latest_gbrain_orphans": latest_gbrain.get("orphan_pages_actual", latest_gbrain.get("orphan_pages")),
        "failure_reasons": dict(sorted(failure_reasons.items())),
        "recent_failures": recent_failures[:5],
        "lag": lag_summary(lag_values_from_monitor_runs(monitor_runs)),
        "acceptance_recall_stage_latency": {
            key: summarize_values(values) for key, values in recall_stage_timings.items()
        },
    }


def task_metrics(runs: list[Any]) -> dict:
    tasks: dict[str, list[Any]] = {}
    for run in runs:
        name = getattr(run, "name", None)
        if not name or name == "memory-sidecar-monitor":
            continue
        tasks.setdefault(name, []).append(run)
    out = {}
    for name, rows in sorted(tasks.items()):
        elapsed = [value for value in (elapsed_from_run(run) for run in rows) if value is not None]
        failures = sum(1 for run in rows if getattr(run, "status", "") != "success" or bool(getattr(run, "error", None)))
        returncodes = [
            output_payload(run).get("returncode")
            for run in rows
            if isinstance(output_payload(run).get("returncode"), int)
        ]
        out[name] = {
            "count": len(rows),
            "failure_count": failures,
            "success_rate": round((len(rows) - failures) / len(rows), 3) if rows else None,
            "latency": summarize_values(elapsed),
            "nonzero_returncodes": sum(1 for code in returncodes if code != 0),
        }
    return out


def build_trend_report(runs: list[Any]) -> dict:
    error_count = sum(1 for run in runs if getattr(run, "status", "") != "success" or bool(getattr(run, "error", None)))
    monitor = monitor_metrics(runs)
    tasks = task_metrics(runs)
    task_latencies = [
        (name, metrics["latency"].get("p95_s"))
        for name, metrics in tasks.items()
        if metrics.get("latency", {}).get("p95_s") is not None
    ]
    slowest = max(task_latencies, key=lambda item: item[1]) if task_latencies else None
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT_NAME,
        "run_count": len(runs),
        "error_count": error_count,
        "success_rate": round((len(runs) - error_count) / len(runs), 3) if runs else None,
        "monitor": monitor,
        "tasks": tasks,
        "performance": {
            "acceptance_latency": monitor["acceptance_latency"],
            "recall_latency": monitor["recall_latency"],
            "acceptance_recall_stage_latency": monitor["acceptance_recall_stage_latency"],
            "slowest_task_by_p95": {"name": slowest[0], "p95_s": slowest[1]} if slowest else None,
        },
    }


def fetch_runs(limit: int) -> list[Any]:
    from langsmith import Client

    client = Client()
    return list(client.list_runs(project_name=PROJECT_NAME, limit=limit))


def load_local_monitor_run(path: str) -> LocalRun | None:
    monitor_path = Path(path).expanduser()
    if not monitor_path.exists():
        return None
    try:
        payload = json.loads(monitor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return LocalRun("memory-sidecar-monitor", payload)


def publish_report(report: dict) -> dict:
    from langsmith import traceable

    @traceable(run_type="chain", name="memory-sidecar-trend-report", project_name=PROJECT_NAME)
    def _emit() -> dict:
        return report

    return {"published": True, "project": PROJECT_NAME, "result": _emit()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", default="")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--local-monitor", default=str(DEFAULT_LOCAL_MONITOR))
    parser.add_argument("--no-local-monitor", action="store_true")
    args = parser.parse_args()

    runs = fetch_runs(args.limit)
    if not args.no_local_monitor:
        local_run = load_local_monitor_run(args.local_monitor)
        if local_run:
            runs.insert(0, local_run)
    report = build_trend_report(runs)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    published = publish_report(report) if args.publish and os.environ.get("LANGSMITH_API_KEY") else None
    print(json.dumps({"report": report, "langsmith": published}, ensure_ascii=False, indent=2))
    return 0 if report.get("success_rate") is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
