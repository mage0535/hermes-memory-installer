#!/usr/bin/env python3
"""Render a static metrics dashboard from local sidecar health artifacts."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_OUTPUT = METRICS_DIR / "dashboard.html"


ARTIFACTS = {
    "Runtime Drift": "runtime-drift-latest.json",
    "Health Summary": "health-summary-latest.json",
    "LangSmith Trend": "langsmith-trend-latest.json",
    "gbrain Stale": "gbrain-stale-latest.json",
    "Hindsight Security": "hindsight-security-latest.json",
    "Webhook Receiver": "webhook-receiver-latest.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "ok": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unreadable", "ok": False, "error": str(exc)}


def safe(value: Any) -> str:
    return html.escape(str(value), quote=True)


def summarize(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status") or ("healthy" if payload.get("ok") else "unknown")
    summary: dict[str, Any] = {"name": name, "status": status, "ok": payload.get("ok") is True}
    if name == "LangSmith Trend":
        monitor = payload.get("monitor", {})
        summary["details"] = {
            "recent_acceptance_ok_rate": monitor.get("recent_acceptance_ok_rate"),
            "acceptance_ok_rate": monitor.get("acceptance_ok_rate"),
            "lag_status": (monitor.get("lag") or {}).get("status"),
        }
    elif name == "gbrain Stale":
        after = payload.get("after", {})
        summary["details"] = {
            "health_score": after.get("health_score"),
            "stale_pages": after.get("stale_pages"),
            "actual_orphans": after.get("orphan_pages_actual"),
            "classifications": len(payload.get("classifications", [])),
        }
    elif name == "Health Summary":
        summary["details"] = {"alert_count": payload.get("alert_count")}
    elif name == "Webhook Receiver":
        summary["details"] = {
            "external_forward_configured": payload.get("external_forward_configured"),
            "last_forward": payload.get("last_forward"),
        }
    else:
        summary["details"] = {
            "reason_count": len(payload.get("reasons", [])),
            "error": payload.get("error"),
        }
    return summary


def build_dashboard_payload(metrics_dir: Path) -> dict[str, Any]:
    artifacts = []
    for name, filename in ARTIFACTS.items():
        payload = load_json(metrics_dir / filename)
        artifacts.append(
            {
                "name": name,
                "filename": filename,
                "summary": summarize(name, payload),
                "raw": payload,
            }
        )
    ok = all(item["summary"].get("ok") for item in artifacts)
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "metrics_dir": str(metrics_dir),
        "artifacts": artifacts,
    }


def render_dashboard(metrics_dir: Path) -> str:
    captured_at = datetime.now(timezone.utc).isoformat()
    cards = []
    raw_blocks = []
    for name, filename in ARTIFACTS.items():
        payload = load_json(metrics_dir / filename)
        summary = summarize(name, payload)
        detail_rows = "".join(
            f"<tr><th>{safe(key)}</th><td>{safe(value)}</td></tr>"
            for key, value in summary.get("details", {}).items()
            if value is not None
        )
        state = safe(summary["status"])
        cards.append(
            f"""
            <section class="card status-{state}">
              <div class="card-head"><h2>{safe(name)}</h2><span>{state}</span></div>
              <table>{detail_rows or '<tr><td>No details</td></tr>'}</table>
            </section>
            """
        )
        raw_blocks.append(
            f"<details><summary>{safe(filename)}</summary><pre>{safe(json.dumps(payload, ensure_ascii=False, indent=2))}</pre></details>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes Memory Metrics</title>
  <style>
    :root {{ --bg: #f6f2e8; --ink: #1f241c; --ok: #227950; --warn: #9b6a00; --bad: #a12727; --card: #fffaf0; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; color: var(--ink); background: radial-gradient(circle at top left, #fff7cc, transparent 30rem), var(--bg); }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 2px solid #29291f; margin-bottom: 24px; }}
    h1 {{ font-size: clamp(2rem, 5vw, 4rem); line-height: .95; margin: 0 0 12px; letter-spacing: -0.04em; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .card {{ background: var(--card); border: 2px solid #29291f; box-shadow: 6px 6px 0 #29291f; padding: 16px; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .card h2 {{ margin: 0 0 12px; font-size: 1.1rem; }}
    .card span {{ font: 700 .8rem ui-monospace, SFMono-Regular, Menlo, monospace; text-transform: uppercase; }}
    .status-healthy span {{ color: var(--ok); }}
    .status-degraded span, .status-missing span, .status-unknown span {{ color: var(--warn); }}
    .status-action-needed span, .status-unreadable span {{ color: var(--bad); }}
    table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
    th, td {{ text-align: left; border-top: 1px solid #d9ceb8; padding: 7px 0; vertical-align: top; }}
    th {{ width: 46%; font-weight: 700; }}
    details {{ margin-top: 12px; background: rgba(255,255,255,.45); border: 1px solid #d9ceb8; padding: 10px; }}
    pre {{ overflow: auto; white-space: pre-wrap; font-size: .78rem; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Hermes Memory Metrics</h1>
      <p>Generated {safe(captured_at)} from {safe(metrics_dir)}</p>
    </header>
    <div class="grid">{''.join(cards)}</div>
    <section><h2>Raw Artifacts</h2>{''.join(raw_blocks)}</section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default=str(METRICS_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    metrics_dir = Path(args.metrics_dir).expanduser()
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(metrics_dir), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
