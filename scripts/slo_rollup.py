#!/usr/bin/env python3
"""Roll up Hermes Memory SLO indicators from existing metrics artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_OUTPUT = METRICS_DIR / "slo-rollup-latest.json"
DEFAULT_HISTORY = METRICS_DIR / "slo-rollup-history.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def latest_history_row(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return {}
    if not lines:
        return {}
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def replay_success_rate(payload: dict[str, Any]) -> float | None:
    replayed = payload.get("replayed")
    failed = payload.get("failed")
    if not isinstance(replayed, int) or replayed <= 0:
        return None
    failed_count = failed if isinstance(failed, int) else 0
    return round((replayed - failed_count) / replayed, 3)


def recall_latency_from_trend(payload: dict[str, Any]) -> dict[str, float | None]:
    performance = payload.get("performance") if isinstance(payload.get("performance"), dict) else {}
    latency = performance.get("recall_latency") if isinstance(performance.get("recall_latency"), dict) else {}
    monitor = payload.get("monitor") if isinstance(payload.get("monitor"), dict) else {}
    if not latency:
        latency = monitor.get("recall_latency") if isinstance(monitor.get("recall_latency"), dict) else {}
    return {
        "p50_s": latency.get("p50_s"),
        "p95_s": latency.get("p95_s"),
        "max_s": latency.get("max_s"),
    }


def build_slo_rollup(metrics_dir: Path, history_path: Path | None = None) -> dict[str, Any]:
    history = history_path or metrics_dir / "slo-rollup-history.jsonl"
    trend = load_json(metrics_dir / "langsmith-trend-latest.json")
    replay = load_json(metrics_dir / "dead-letter-replay-latest.json")
    monitor = trend.get("monitor") if isinstance(trend.get("monitor"), dict) else {}
    queue_lines = count_jsonl_lines(metrics_dir / "inbound-alert-webhook.jsonl")
    previous_queue_lines = latest_history_row(history).get("alert_queue_lines")
    growth = queue_lines - previous_queue_lines if isinstance(previous_queue_lines, int) else 0

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "acceptance_ok_rate": monitor.get("recent_acceptance_ok_rate", monitor.get("acceptance_ok_rate")),
        "alert_queue_lines": queue_lines,
        "alert_queue_growth": growth,
        "dead_letter_replay_success_rate": replay_success_rate(replay),
        "recall_latency": recall_latency_from_trend(trend),
    }
    if payload["alert_queue_growth"] > 0:
        payload["status"] = "healthy"
    if payload["acceptance_ok_rate"] is not None and float(payload["acceptance_ok_rate"]) < 0.95:
        payload["status"] = "degraded"
    if payload["dead_letter_replay_success_rate"] is not None and float(payload["dead_letter_replay_success_rate"]) < 1.0:
        payload["status"] = "degraded"
    return payload


def append_history(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default=str(METRICS_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()

    metrics_dir = Path(args.metrics_dir).expanduser()
    history = Path(args.history).expanduser()
    payload = build_slo_rollup(metrics_dir, history)
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.no_history:
        append_history(history, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
