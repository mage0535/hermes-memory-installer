#!/usr/bin/env python3
"""Normalize sidecar health artifacts into a local alert queue."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_ALERTS = METRICS_DIR / "alerts.jsonl"
DEFAULT_STATUS = METRICS_DIR / "health-summary-latest.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "action-needed", "error": f"unreadable artifact: {path.name}"}


def alert(source: str, code: str, severity: str, detail: dict | None = None) -> dict:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "code": code,
        "severity": severity,
        "detail": detail or {},
    }


def resolve_lang() -> str:
    for key in ("MEMORY_ALERT_LANG", "MEMORY_UI_LANG", "LANGUAGE", "LC_ALL", "LANG"):
        value = str(os.environ.get(key, "")).strip().lower()
        if value.startswith("zh"):
            return "zh"
        if value.startswith("en"):
            return "en"
    return "zh"


def build_alerts(metrics_dir: Path) -> tuple[str, list[dict]]:
    alerts: list[dict] = []
    drift = load_json(metrics_dir / "runtime-drift-latest.json")
    trend = load_json(metrics_dir / "langsmith-trend-latest.json")
    stale = load_json(metrics_dir / "gbrain-stale-latest.json")
    security = load_json(metrics_dir / "hindsight-security-latest.json")

    if drift.get("status") == "action-needed":
        for reason in drift.get("reasons", []):
            alerts.append(alert("runtime-drift", reason.get("code", "drift"), "action-needed", reason))
    elif drift.get("status") == "degraded":
        for reason in drift.get("reasons", []):
            alerts.append(alert("runtime-drift", reason.get("code", "drift"), "degraded", reason))

    lag = trend.get("monitor", {}).get("lag", {})
    if lag.get("status") == "action-needed":
        alerts.append(alert("langsmith-trend", "hindsight_lag", "action-needed", lag))
    recent_rate = trend.get("monitor", {}).get("recent_acceptance_ok_rate")
    if recent_rate not in (None, 1.0):
        alerts.append(
            alert(
                "langsmith-trend",
                "recent_acceptance_failures",
                "action-needed",
                {
                    "recent_acceptance_ok_rate": recent_rate,
                    "recent_window": trend.get("monitor", {}).get("recent_window"),
                    "recent_failures": trend.get("monitor", {}).get("recent_failures", []),
                },
            )
        )
    if trend.get("monitor", {}).get("acceptance_ok_rate") not in (None, 1.0):
        alerts.append(
            alert(
                "langsmith-trend",
                "historical_acceptance_failures",
                "info",
                {
                    "acceptance_ok_rate": trend.get("monitor", {}).get("acceptance_ok_rate"),
                    "failure_reasons": trend.get("monitor", {}).get("failure_reasons", {}),
                    "recent_failures": trend.get("monitor", {}).get("recent_failures", []),
                },
            )
        )

    stale_status = stale.get("status")
    if stale_status == "action-needed":
        alerts.append(alert("gbrain-stale", "gbrain_stale_action_needed", "action-needed", stale))
    elif stale_status == "degraded":
        actionable = [
            item for item in stale.get("classifications", [])
            if item.get("severity") in {"action-needed", "degraded"}
            and item.get("code") != "stale_health_counter_not_embedding_stale"
            and item.get("code") != "reported_orphans_counter_discrepancy"
        ]
        if actionable:
            alerts.append(alert("gbrain-stale", "gbrain_stale_degraded", "degraded", {"classifications": actionable}))

    if security.get("status") == "action-needed":
        alerts.append(alert("hindsight-security", "hindsight_security_action_needed", "action-needed", security))
    elif security.get("status") == "degraded":
        alerts.append(alert("hindsight-security", "hindsight_security_degraded", "degraded", security))

    status = "healthy"
    if any(row["severity"] == "action-needed" for row in alerts):
        status = "action-needed"
    elif any(row["severity"] == "degraded" for row in alerts):
        status = "degraded"
    return status, alerts


def post_webhook(webhook_url: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return {"status": response.status, "reason": response.reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default=str(METRICS_DIR))
    parser.add_argument("--alerts", default=str(DEFAULT_ALERTS))
    parser.add_argument("--status-output", default=str(DEFAULT_STATUS))
    parser.add_argument("--webhook-url", default=os.environ.get("MEMORY_ALERT_WEBHOOK_URL", ""))
    args = parser.parse_args()

    metrics_dir = Path(args.metrics_dir).expanduser()
    status, alerts = build_alerts(metrics_dir)
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "lang": resolve_lang(),
        "status": status,
        "ok": status == "healthy",
        "alert_count": len(alerts),
        "alerts": alerts,
    }
    status_path = Path(args.status_output).expanduser()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if alerts:
        alerts_path = Path(args.alerts).expanduser()
        alerts_path.parent.mkdir(parents=True, exist_ok=True)
        with alerts_path.open("a", encoding="utf-8") as handle:
            for row in alerts:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    webhook = None
    if args.webhook_url and any(row["severity"] == "action-needed" for row in alerts):
        try:
            webhook = post_webhook(args.webhook_url, payload)
        except Exception as exc:
            webhook = {"error": str(exc)}
    payload["webhook"] = webhook
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
