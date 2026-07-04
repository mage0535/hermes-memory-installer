#!/usr/bin/env python3
"""Bridge Prometheus firing alerts into the local Hermes webhook pipeline."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_PROMETHEUS_URL = os.environ.get("MEMORY_PROMETHEUS_URL", "http://127.0.0.1:9090")
DEFAULT_WEBHOOK_URL = os.environ.get("MEMORY_ALERT_LOCAL_WEBHOOK_URL", "http://127.0.0.1:9499/alerts")
DEFAULT_STATUS = AGENT_HOME / "metrics" / "prometheus-alert-bridge-latest.json"


def fetch_alerts(prometheus_url: str) -> list[dict[str, Any]]:
    url = urllib.parse.urljoin(prometheus_url.rstrip("/") + "/", "api/v1/alerts")
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else {}
    alerts = data.get("alerts") if isinstance(data, dict) else []
    return [row for row in alerts if isinstance(row, dict) and row.get("state") == "firing"]


def build_bridge_payload(alerts: list[dict[str, Any]], lang: str = "zh") -> dict[str, Any]:
    rows = []
    for row in alerts:
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        annotations = row.get("annotations") if isinstance(row.get("annotations"), dict) else {}
        severity = str(labels.get("severity") or "warning").lower()
        mapped = "action-needed" if severity in {"critical", "warning"} else "info"
        rows.append(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "source": "prometheus",
                "code": labels.get("alertname", "prometheus_alert"),
                "severity": mapped,
                "detail": {
                    "summary": annotations.get("summary"),
                    "description": annotations.get("description"),
                    "service": labels.get("service"),
                    "active_at": row.get("activeAt"),
                    "value": row.get("value"),
                    "labels": labels,
                },
            }
        )
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "lang": lang,
        "status": "action-needed" if rows else "healthy",
        "ok": not rows,
        "alert_count": len(rows),
        "alerts": rows,
    }


def post_local_webhook(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as response:
        return {"status": response.status, "reason": response.reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prometheus-url", default=DEFAULT_PROMETHEUS_URL)
    parser.add_argument("--webhook-url", default=DEFAULT_WEBHOOK_URL)
    parser.add_argument("--lang", default=os.environ.get("MEMORY_ALERT_LANG", "zh"))
    parser.add_argument("--status-output", default=str(DEFAULT_STATUS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    alerts = fetch_alerts(args.prometheus_url)
    payload = build_bridge_payload(alerts, lang=args.lang)
    forwarded = None
    if payload["alerts"] and not args.dry_run:
        forwarded = post_local_webhook(args.webhook_url, payload)
    payload["forwarded"] = forwarded
    output = Path(args.status_output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
