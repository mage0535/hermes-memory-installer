#!/usr/bin/env python3
"""Normalize sidecar health artifacts into a local alert queue."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
METRICS_DIR = AGENT_HOME / "metrics"
DEFAULT_ALERTS = METRICS_DIR / "alerts.jsonl"
DEFAULT_STATUS = METRICS_DIR / "health-summary-latest.json"
DEFAULT_STATE = METRICS_DIR / "alert-state-latest.json"
GBRAIN_REPAIR_STATUSES = {"action-needed", "degraded"}
SWAP_DEGRADED_PCT = float(os.environ.get("MEMORY_ALERT_SWAP_DEGRADED_PCT", "85"))
SWAP_ACTION_PCT = float(os.environ.get("MEMORY_ALERT_SWAP_ACTION_PCT", "95"))
DISK_DEGRADED_PCT = float(os.environ.get("MEMORY_ALERT_DISK_DEGRADED_PCT", "85"))
DISK_ACTION_PCT = float(os.environ.get("MEMORY_ALERT_DISK_ACTION_PCT", "90"))


def env_enabled(name: str, default: str = "true") -> bool:
    value = str(os.environ.get(name, default)).strip().lower()
    return value not in {"0", "false", "no", "off"}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "action-needed", "error": f"unreadable artifact: {path.name}"}


def repair_gbrain_stale_if_needed(metrics_dir: Path, stale_payload: dict[str, Any]) -> dict[str, Any]:
    if stale_payload.get("status") not in GBRAIN_REPAIR_STATUSES:
        return stale_payload
    if not env_enabled("MEMORY_ALERT_AUTO_REPAIR_GBRAIN", "true"):
        return stale_payload
    output = metrics_dir / "gbrain-stale-latest.json"
    script = Path(
        os.environ.get(
            "GBRAIN_STALE_MAINTENANCE_SCRIPT",
            str(AGENT_HOME / "scripts" / "gbrain_stale_maintenance.py"),
        )
    ).expanduser()
    command = [
        "flock",
        "-n",
        os.environ.get("GBRAIN_STALE_REPAIR_LOCK", "/tmp/gbrain-stale-refresh.lock"),
        os.environ.get("PYTHON", sys.executable or "/usr/bin/python3"),
        str(script),
        "--refresh-embeddings",
        "--stale-budget",
        os.environ.get("GBRAIN_STALE_REFRESH_BUDGET", "100"),
        "--missing-budget",
        os.environ.get("GBRAIN_MISSING_REFRESH_BUDGET", "0"),
        "--output",
        str(output),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, timeout=int(os.environ.get("GBRAIN_STALE_REPAIR_TIMEOUT", "1200")))
    except (OSError, subprocess.TimeoutExpired):
        return stale_payload
    repaired = load_json(output)
    return repaired or stale_payload


def alert(source: str, code: str, severity: str, detail: dict | None = None) -> dict:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "code": code,
        "severity": severity,
        "detail": detail or {},
    }


def alert_key(row: dict[str, Any]) -> str:
    return f"{row.get('source','unknown')}:{row.get('code','unknown')}"


def enrich_alert(row: dict[str, Any]) -> dict[str, Any]:
    detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
    code = str(row.get("code") or "")
    if code == "hindsight_lag":
        detail.setdefault("reason", "Hindsight 记忆服务处理延迟过高")
        detail.setdefault("recommended_action", "系统已尝试自动修复，请核查最新健康结果；若连续 2-3 个周期仍存在，请人工介入。")
    elif code == "recent_acceptance_failures":
        detail.setdefault("reason", "近期 acceptance 业务检查连续失败")
        detail.setdefault("recommended_action", "优先检查 guardian 状态、Hindsight lag 和 recall 结果；不要只看 LangSmith run 是否 success。")
    elif code == "gbrain_stale_action_needed":
        detail.setdefault("reason", "gbrain 知识图谱 embedding 或 orphan 状态异常")
        if detail.get("auto_fix_attempted"):
            if detail.get("auto_fix_succeeded"):
                detail.setdefault("recommended_action", "系统已尝试自动修复，请核查最新健康结果。")
            else:
                detail.setdefault("recommended_action", "系统已尝试自动修复但未成功，请人工检查 gbrain embed/deorphan 链路。")
        else:
            detail.setdefault("recommended_action", "系统尚未完成自动修复，请先执行 embedding/orphan 恢复，再观察后续周期。")
    row["detail"] = detail
    return row


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def diff_notifications(previous: dict[str, Any], current_alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_map = {key: value for key, value in (previous.get("alerts") or {}).items()} if isinstance(previous.get("alerts"), dict) else {}
    current_map = {alert_key(row): row for row in current_alerts}
    notifications: list[dict[str, Any]] = []
    for key, row in current_map.items():
        prev = previous_map.get(key)
        if not prev or prev.get("severity") != row.get("severity"):
            notifications.append(row)
    for key, prev in previous_map.items():
        if key not in current_map:
            notifications.append(
                {
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "source": str(prev.get("source") or key.split(":", 1)[0]),
                    "code": str(prev.get("code") or key.split(":", 1)[-1]) + "_resolved",
                    "severity": "healthy",
                    "detail": {"reason": "告警恢复", "recommended_action": "状态已恢复，无需动作。"},
                }
            )
    return notifications


def resolve_lang() -> str:
    for key in ("MEMORY_ALERT_LANG", "MEMORY_UI_LANG", "LANGUAGE", "LC_ALL", "LANG"):
        value = str(os.environ.get(key, "")).strip().lower()
        if value.startswith("zh"):
            return "zh"
        if value.startswith("en"):
            return "en"
    return "zh"


def append_system_resource_alerts(alerts: list[dict], payload: dict[str, Any]) -> None:
    memory = payload.get("memory") if isinstance(payload.get("memory"), dict) else {}
    disk = payload.get("disk") if isinstance(payload.get("disk"), dict) else {}
    try:
        swap_pct = float(memory.get("swap_pct") or 0)
    except (TypeError, ValueError):
        swap_pct = 0.0
    try:
        disk_pct = float(disk.get("pct") or 0)
    except (TypeError, ValueError):
        disk_pct = 0.0
    if swap_pct >= SWAP_ACTION_PCT:
        alerts.append(alert("system-resources", "swap_usage_critical", "action-needed", {"swap_pct": swap_pct, "memory": memory}))
    elif swap_pct >= SWAP_DEGRADED_PCT:
        alerts.append(alert("system-resources", "swap_usage_high", "degraded", {"swap_pct": swap_pct, "memory": memory}))
    if disk_pct >= DISK_ACTION_PCT:
        alerts.append(alert("system-resources", "disk_usage_critical", "action-needed", {"disk_pct": disk_pct, "disk": disk}))
    elif disk_pct >= DISK_DEGRADED_PCT:
        alerts.append(alert("system-resources", "disk_usage_high", "degraded", {"disk_pct": disk_pct, "disk": disk}))


def build_alerts(metrics_dir: Path) -> tuple[str, list[dict]]:
    alerts: list[dict] = []
    drift = load_json(metrics_dir / "runtime-drift-latest.json")
    trend = load_json(metrics_dir / "langsmith-trend-latest.json")
    stale = load_json(metrics_dir / "gbrain-stale-latest.json")
    stale = repair_gbrain_stale_if_needed(metrics_dir, stale)
    live_refresh = load_json(metrics_dir / "live-hindsight-refresh-latest.json")
    security = load_json(metrics_dir / "hindsight-security-latest.json")
    cron_freshness = load_json(metrics_dir / "cron-freshness-latest.json")
    system_metrics = load_json(metrics_dir / "system-metrics-latest.json")

    if drift.get("status") == "action-needed":
        for reason in drift.get("reasons", []):
            alerts.append(alert("runtime-drift", reason.get("code", "drift"), "action-needed", reason))
    elif drift.get("status") == "degraded":
        for reason in drift.get("reasons", []):
            alerts.append(alert("runtime-drift", reason.get("code", "drift"), "degraded", reason))

    lag = trend.get("monitor", {}).get("lag", {})
    if lag.get("status") == "action-needed":
        alerts.append(alert("langsmith-trend", "hindsight_lag", "action-needed", lag))
    recent_rate = trend.get("monitor", {}).get("current_acceptance_ok_rate")
    if recent_rate is None:
        recent_rate = trend.get("monitor", {}).get("recent_acceptance_ok_rate")
    latest_acceptance_ok = trend.get("monitor", {}).get("latest_acceptance_ok")
    if recent_rate not in (None, 1.0) and latest_acceptance_ok is not True:
        alerts.append(
            alert(
                "langsmith-trend",
                "recent_acceptance_failures",
                "action-needed",
                {
                    "recent_acceptance_ok_rate": recent_rate,
                    "recent_window": trend.get("monitor", {}).get("current_window", trend.get("monitor", {}).get("recent_window")),
                    "recent_failures": trend.get("monitor", {}).get("recent_failures", []),
                    "current_failure_reasons": trend.get("monitor", {}).get("current_failure_reasons", {}),
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

    task_alerts = {}
    historical_task_alerts = {}
    for name, metrics in (trend.get("tasks") or {}).items():
        if not isinstance(metrics, dict):
            continue
        recent_failures = int(metrics.get("recent_business_failure_count") or 0)
        latest_ok = metrics.get("latest_business_ok")
        if latest_ok is False or (recent_failures > 0 and latest_ok is not True):
            task_alerts[name] = {
                "recent_business_failure_count": recent_failures,
                "recent_business_success_rate": metrics.get("recent_business_success_rate"),
                "latest_business_ok": latest_ok,
                "latest_returncode": metrics.get("latest_returncode"),
                "recent_window": metrics.get("recent_window"),
            }
            continue
        if int(metrics.get("business_failure_count") or 0) > 0 or recent_failures > 0:
            historical_task_alerts[name] = {
                "business_failure_count": metrics.get("business_failure_count"),
                "business_success_rate": metrics.get("business_success_rate"),
                "nonzero_returncodes": metrics.get("nonzero_returncodes"),
                "recent_business_failure_count": recent_failures,
                "latest_business_ok": latest_ok,
            }
    if task_alerts:
        alerts.append(alert("langsmith-task", "recent_task_business_failures", "action-needed", {"tasks": task_alerts}))
    elif historical_task_alerts:
        alerts.append(alert("langsmith-task", "historical_task_business_failures", "info", {"tasks": historical_task_alerts}))

    stale_status = stale.get("status")
    if stale_status == "action-needed":
        detail = dict(stale)
        detail["auto_fix_attempted"] = stale.get("auto_fix_attempted")
        detail["auto_fix_succeeded"] = stale.get("auto_fix_succeeded")
        detail["auto_fix_failed"] = stale.get("auto_fix_failed")
        alerts.append(alert("gbrain-stale", "gbrain_stale_action_needed", "action-needed", detail))
    elif stale_status == "degraded":
        actionable = [
            item for item in stale.get("classifications", [])
            if item.get("severity") in {"action-needed", "degraded"}
            and item.get("code") != "stale_health_counter_not_embedding_stale"
            and item.get("code") != "reported_orphans_counter_discrepancy"
        ]
        if actionable:
            alerts.append(alert("gbrain-stale", "gbrain_stale_degraded", "degraded", {"classifications": actionable}))

    live_refresh_status = live_refresh.get("status")
    if live_refresh_status == "action-needed":
        alerts.append(alert("live-hindsight-refresh", "live_hindsight_refresh_action_needed", "action-needed", live_refresh))
    elif live_refresh_status == "degraded":
        alerts.append(alert("live-hindsight-refresh", "live_hindsight_refresh_degraded", "degraded", live_refresh))

    if security.get("status") == "action-needed":
        alerts.append(alert("hindsight-security", "hindsight_security_action_needed", "action-needed", security))
    elif security.get("status") == "degraded":
        alerts.append(alert("hindsight-security", "hindsight_security_degraded", "degraded", security))

    append_system_resource_alerts(alerts, system_metrics)

    if cron_freshness.get("status") in {"action-needed", "degraded"}:
        stale_jobs = [
            job for job in cron_freshness.get("jobs", [])
            if isinstance(job, dict) and job.get("status") in {"action-needed", "degraded"}
        ]
        if stale_jobs:
            severity = "action-needed" if cron_freshness.get("status") == "action-needed" else "degraded"
            alerts.append(alert("cron-freshness", "cron_jobs_stale", severity, {"jobs": stale_jobs}))

    status = "healthy"
    if any(row["severity"] == "action-needed" for row in alerts):
        status = "action-needed"
    elif any(row["severity"] == "degraded" for row in alerts):
        status = "degraded"
    return status, [enrich_alert(row) for row in alerts]


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
    parser.add_argument("--state-output", default=str(DEFAULT_STATE))
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
    state_path = Path(args.state_output).expanduser()
    previous_state = read_state(state_path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    notifications = diff_notifications(previous_state, alerts)
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if notifications:
        alerts_path = Path(args.alerts).expanduser()
        alerts_path.parent.mkdir(parents=True, exist_ok=True)
        with alerts_path.open("a", encoding="utf-8") as handle:
            for row in notifications:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    webhook = None
    if args.webhook_url and any(row["severity"] in {"action-needed", "degraded", "healthy"} for row in notifications):
        try:
            webhook_payload = dict(payload)
            webhook_payload["alerts"] = notifications
            webhook_payload["alert_count"] = len(notifications)
            webhook = post_webhook(args.webhook_url, webhook_payload)
        except Exception as exc:
            webhook = {"error": str(exc)}
    payload["webhook"] = webhook
    payload["notifications"] = notifications
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "captured_at": payload["captured_at"],
                "status": status,
                "alerts": {
                    alert_key(row): {"source": row["source"], "code": row["code"], "severity": row["severity"]}
                    for row in alerts
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
