#!/usr/bin/env python3
"""Export Hermes Memory sidecar health artifacts in OpenMetrics text format."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_OUTPUT = METRICS_DIR / "openmetrics.prom"
QUEUE_FILE = "inbound-alert-webhook.jsonl"
DEAD_LETTER_FILE = "failed-alert-webhook.jsonl"


STATUS_VALUE = {
    "healthy": 0,
    "ok": 0,
    "degraded": 1,
    "warning": 1,
    "action-needed": 2,
    "critical": 2,
    "missing": 3,
    "unreadable": 3,
    "unknown": 3,
}


ARTIFACTS = {
    "runtime_drift": "runtime-drift-latest.json",
    "health_summary": "health-summary-latest.json",
    "langsmith_trend": "langsmith-trend-latest.json",
    "gbrain_stale": "gbrain-stale-latest.json",
    "hindsight_security": "hindsight-security-latest.json",
    "webhook_receiver": "webhook-receiver-latest.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "ok": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unreadable", "ok": False, "error": str(exc)}


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def status_code(payload: dict[str, Any]) -> int:
    status = str(payload.get("status") or ("healthy" if payload.get("ok") else "unknown")).lower()
    return STATUS_VALUE.get(status, STATUS_VALUE["unknown"])


def metric_line(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if not labels:
        return f"{name} {value}"
    label_text = ",".join(f'{key}="{val.replace(chr(34), chr(92) + chr(34))}"' for key, val in sorted(labels.items()))
    return f"{name}{{{label_text}}} {value}"


def render_openmetrics(metrics_dir: Path) -> str:
    payloads = {name: load_json(metrics_dir / filename) for name, filename in ARTIFACTS.items()}
    lines = [
        "# HELP hermes_memory_component_status Component status code: healthy=0 degraded=1 action-needed=2 missing=3.",
        "# TYPE hermes_memory_component_status gauge",
    ]
    for component, payload in payloads.items():
        lines.append(metric_line("hermes_memory_component_status", status_code(payload), {"component": component}))

    health = payloads["health_summary"]
    webhook = payloads["webhook_receiver"]
    gbrain = payloads["gbrain_stale"]
    langsmith = payloads["langsmith_trend"]

    lines.extend(
        [
            "# HELP hermes_memory_alert_count Current alert count from health summary.",
            "# TYPE hermes_memory_alert_count gauge",
            metric_line("hermes_memory_alert_count", int(health.get("alert_count") or 0)),
            "# HELP hermes_memory_webhook_queue_lines Lines retained in webhook queue files.",
            "# TYPE hermes_memory_webhook_queue_lines gauge",
            metric_line("hermes_memory_webhook_queue_lines", count_jsonl_lines(metrics_dir / QUEUE_FILE), {"queue": "inbound"}),
            metric_line("hermes_memory_webhook_queue_lines", count_jsonl_lines(metrics_dir / DEAD_LETTER_FILE), {"queue": "dead_letter"}),
        ]
    )

    last_forward = webhook.get("last_forward") or {}
    lines.extend(
        [
            "# HELP hermes_memory_webhook_last_forward_ok Whether the last external forward succeeded.",
            "# TYPE hermes_memory_webhook_last_forward_ok gauge",
            metric_line("hermes_memory_webhook_last_forward_ok", 0 if last_forward.get("error") else 1),
            "# HELP hermes_memory_webhook_last_forward_attempts Attempt count from the last external forward.",
            "# TYPE hermes_memory_webhook_last_forward_attempts gauge",
            metric_line("hermes_memory_webhook_last_forward_attempts", int(last_forward.get("attempts") or 0)),
        ]
    )

    after = gbrain.get("after") or {}
    classifications = gbrain.get("classifications") or []
    upstream_gap_active = any(str(item.get("category")) == "upstream_gbrain_gap" for item in classifications)
    lines.extend(
        [
            "# HELP hermes_memory_gbrain_health_score Latest gbrain health score.",
            "# TYPE hermes_memory_gbrain_health_score gauge",
            metric_line("hermes_memory_gbrain_health_score", float(after.get("health_score") or 0)),
            "# HELP hermes_memory_gbrain_upstream_gap_active Whether stale-page health is blocked by upstream gbrain gaps.",
            "# TYPE hermes_memory_gbrain_upstream_gap_active gauge",
            metric_line("hermes_memory_gbrain_upstream_gap_active", 1 if upstream_gap_active else 0),
        ]
    )

    monitor = langsmith.get("monitor") or {}
    recent_rate = monitor.get("recent_acceptance_ok_rate")
    if recent_rate is not None:
        lines.extend(
            [
                "# HELP hermes_memory_langsmith_recent_acceptance_ok_rate Recent acceptance success rate from LangSmith trend.",
                "# TYPE hermes_memory_langsmith_recent_acceptance_ok_rate gauge",
                metric_line("hermes_memory_langsmith_recent_acceptance_ok_rate", float(recent_rate)),
            ]
        )

    generated = int(datetime.now(timezone.utc).timestamp())
    lines.extend(
        [
            "# HELP hermes_memory_openmetrics_generated_timestamp_seconds Export generation time.",
            "# TYPE hermes_memory_openmetrics_generated_timestamp_seconds gauge",
            metric_line("hermes_memory_openmetrics_generated_timestamp_seconds", generated),
            "# EOF",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default=str(METRICS_DIR))
    parser.add_argument("--output", help="Write OpenMetrics text to this file instead of stdout")
    args = parser.parse_args()

    text = render_openmetrics(Path(args.metrics_dir).expanduser())
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(output)}, ensure_ascii=False))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
