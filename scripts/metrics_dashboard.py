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

ARTIFACT_LABELS = {
    "Runtime Drift": "运行漂移",
    "Health Summary": "健康总览",
    "LangSmith Trend": "LangSmith 趋势",
    "gbrain Stale": "gbrain 健康",
    "Hindsight Security": "Hindsight 安全",
    "Webhook Receiver": "Webhook 转发",
}

DETAIL_LABELS = {
    "recent_acceptance_ok_rate": "最近验收通过率",
    "acceptance_ok_rate": "累计验收通过率",
    "lag_status": "延迟状态",
    "health_score": "健康分",
    "stale_pages": "陈旧页面",
    "actual_orphans": "实际孤页",
    "classifications": "分类条目",
    "alert_count": "告警数量",
    "external_forward_configured": "已配置外部转发",
    "last_forward": "最近转发结果",
    "reason_count": "原因数量",
    "error": "错误",
}

STATUS_LABELS = {
    "healthy": "正常",
    "degraded": "降级",
    "action-needed": "需处理",
    "missing": "缺失",
    "unknown": "未知",
    "unreadable": "不可读",
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


def percent(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def format_forward_result(payload: Any) -> str | None:
    if not payload:
        return None
    if not isinstance(payload, dict):
        return str(payload)
    if payload.get("error"):
        attempts = payload.get("attempts")
        return f"失败，已重试 {attempts} 次" if attempts else "失败"
    status = payload.get("status")
    attempts = payload.get("attempts")
    if status:
        return f"成功，HTTP {status}，尝试 {attempts or 1} 次"
    return "成功"


def localize_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def display_artifact_name(name: str) -> str:
    return ARTIFACT_LABELS.get(name, name)


def detail_label(key: str) -> str:
    return DETAIL_LABELS.get(key, key)


def format_detail_value(key: str, value: Any) -> str | None:
    if value is None:
        return None
    if key in {"recent_acceptance_ok_rate", "acceptance_ok_rate"}:
        return percent(value)
    if key == "external_forward_configured":
        return "是" if bool(value) else "否"
    if key == "last_forward":
        return format_forward_result(value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return str(value)


def status_tone(status: str) -> str:
    if status == "healthy":
        return "tone-positive"
    if status in {"degraded", "missing", "unknown"}:
        return "tone-warn"
    return "tone-critical"


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
    status_counts = {"healthy": 0, "degraded": 0, "action-needed": 0, "missing": 0, "unknown": 0, "unreadable": 0}
    for name, filename in ARTIFACTS.items():
        payload = load_json(metrics_dir / filename)
        summary = summarize(name, payload)
        status_counts[summary["status"]] = status_counts.get(summary["status"], 0) + 1
        detail_rows = "".join(
            f"<tr><th>{safe(detail_label(key))}</th><td>{safe(format_detail_value(key, value))}</td></tr>"
            for key, value in summary.get("details", {}).items()
            if format_detail_value(key, value) is not None
        )
        state = safe(summary["status"])
        status_label = safe(localize_status(summary["status"]))
        artifact_label = safe(display_artifact_name(name))
        cards.append(
            f"""
            <section class="card status-{state}">
              <div class="card-head">
                <div>
                  <p class="eyebrow">{safe(filename)}</p>
                  <h2>{artifact_label}</h2>
                </div>
                <span class="status-pill {status_tone(summary['status'])}">{status_label}</span>
              </div>
              <table>{detail_rows or '<tr><td>No details</td></tr>'}</table>
            </section>
            """
        )
        raw_blocks.append(
            f"<details><summary>{artifact_label} · {safe(filename)}</summary><pre>{safe(json.dumps(payload, ensure_ascii=False, indent=2))}</pre></details>"
        )
    total_alerts = load_json(metrics_dir / ARTIFACTS["Health Summary"]).get("alert_count") or 0
    overall_status = "healthy"
    if status_counts.get("action-needed") or status_counts.get("unreadable"):
        overall_status = "action-needed"
    elif status_counts.get("degraded") or status_counts.get("missing") or status_counts.get("unknown"):
        overall_status = "degraded"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes 记忆体仪表板</title>
  <style>
    :root {{
      --bg: #f6f8fe;
      --bg-accent: #e8f0fe;
      --surface: rgba(255, 255, 255, 0.82);
      --surface-strong: #ffffff;
      --surface-soft: #eef3fd;
      --line: rgba(108, 117, 141, 0.18);
      --text: #1b1f2a;
      --muted: #5d6475;
      --primary: #0b57d0;
      --primary-soft: #d3e3fd;
      --positive: #137333;
      --positive-soft: #c4eed0;
      --warn: #b06000;
      --warn-soft: #fde6c6;
      --critical: #c5221f;
      --critical-soft: #f9dedc;
      --shadow: 0 10px 30px rgba(11, 87, 208, 0.12);
      --radius-xl: 32px;
      --radius-lg: 24px;
      --radius-md: 18px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Segoe UI Variable", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(11, 87, 208, 0.18), transparent 28rem),
        radial-gradient(circle at top right, rgba(66, 133, 244, 0.16), transparent 24rem),
        linear-gradient(180deg, var(--bg-accent), var(--bg));
    }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px 20px 72px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(227, 239, 255, 0.86));
      border: 1px solid rgba(255,255,255,0.7);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
      padding: 28px;
      backdrop-filter: blur(20px);
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: start;
      flex-wrap: wrap;
    }}
    .hero h1 {{
      margin: 0;
      font-size: clamp(2rem, 5vw, 3.8rem);
      line-height: 1.02;
      letter-spacing: -0.05em;
      font-weight: 800;
    }}
    .subtitle {{
      margin: 14px 0 0;
      max-width: 62rem;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.7;
    }}
    .hero-meta {{
      display: inline-flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 18px;
    }}
    .chip, .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 14px;
      font-size: .92rem;
      font-weight: 700;
      white-space: nowrap;
    }}
    .chip {{
      background: rgba(255,255,255,0.8);
      border: 1px solid var(--line);
      color: var(--text);
    }}
    .tone-positive {{ background: var(--positive-soft); color: var(--positive); }}
    .tone-warn {{ background: var(--warn-soft); color: var(--warn); }}
    .tone-critical {{ background: var(--critical-soft); color: var(--critical); }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }}
    .summary-card {{
      background: var(--surface-strong);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 18px 18px 16px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
    }}
    .summary-card p {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: .88rem;
    }}
    .summary-card strong {{
      font-size: 2rem;
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      margin: 34px 0 16px;
      flex-wrap: wrap;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 1.25rem;
      letter-spacing: -0.02em;
    }}
    .section-head p {{
      margin: 0;
      color: var(--muted);
      font-size: .94rem;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 18px; }}
    .card {{
      background: var(--surface);
      border: 1px solid rgba(255,255,255,0.7);
      border-radius: var(--radius-lg);
      padding: 20px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
      transform: translateY(0);
      transition: transform .22s ease, box-shadow .22s ease;
    }}
    .card:hover {{ transform: translateY(-2px); box-shadow: 0 14px 36px rgba(11, 87, 208, 0.16); }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 16px;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--primary);
      font-size: .78rem;
      font-weight: 700;
      letter-spacing: .04em;
    }}
    .card h2 {{
      margin: 0;
      font-size: 1.18rem;
      line-height: 1.25;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: .94rem; }}
    th, td {{ text-align: left; border-top: 1px solid var(--line); padding: 10px 0; vertical-align: top; }}
    th {{ width: 42%; font-weight: 700; color: var(--muted); }}
    td {{ word-break: break-word; }}
    .raw-blocks {{
      display: grid;
      gap: 14px;
      margin-top: 18px;
    }}
    details {{
      background: rgba(255,255,255,0.7);
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      padding: 14px 16px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
      color: var(--text);
    }}
    pre {{
      overflow: auto;
      white-space: pre-wrap;
      font-size: .82rem;
      color: #243044;
      background: var(--surface-soft);
      border-radius: 16px;
      padding: 14px;
      margin: 14px 0 0;
    }}
    @media (max-width: 720px) {{
      main {{ padding: 16px 14px 52px; }}
      .hero {{ padding: 22px 18px; border-radius: 24px; }}
      .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
      th {{ width: 40%; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1>Hermes 记忆体仪表板</h1>
          <p class="subtitle">集中查看运行漂移、验收趋势、gbrain 健康、安全审计和告警转发状态。这个页面只负责展示本地健康产物，不直接执行修复动作。</p>
          <div class="hero-meta">
            <span class="chip">生成时间：{safe(captured_at)}</span>
            <span class="chip">指标目录：{safe(metrics_dir)}</span>
            <span class="status-pill {status_tone(overall_status)}">整体状态：{safe(localize_status(overall_status))}</span>
          </div>
        </div>
      </div>
      <div class="summary-grid">
        <section class="summary-card">
          <p>组件总数</p>
          <strong>{len(ARTIFACTS)}</strong>
        </section>
        <section class="summary-card">
          <p>正常组件</p>
          <strong>{status_counts.get("healthy", 0)}</strong>
        </section>
        <section class="summary-card">
          <p>需关注组件</p>
          <strong>{status_counts.get("degraded", 0) + status_counts.get("missing", 0) + status_counts.get("unknown", 0)}</strong>
        </section>
        <section class="summary-card">
          <p>待处理告警</p>
          <strong>{total_alerts}</strong>
        </section>
      </div>
    </section>
    <div class="section-head">
      <div>
        <h2>核心健康卡片</h2>
        <p>适合人工巡检。每张卡片都来自一个本地健康产物。</p>
      </div>
    </div>
    <div class="grid">{''.join(cards)}</div>
    <section>
      <div class="section-head">
        <div>
          <h2>原始健康产物</h2>
          <p>保留 JSON 原文，便于排查字段和值的来源。</p>
        </div>
      </div>
      <div class="raw-blocks">{''.join(raw_blocks)}</div>
    </section>
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
