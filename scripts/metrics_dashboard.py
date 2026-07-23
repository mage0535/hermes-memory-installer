#!/usr/bin/env python3
"""Render a bilingual operator dashboard from local sidecar health artifacts."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


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
    "SLO Rollup": "slo-rollup-latest.json",
    "Prometheus Alert Bridge": "prometheus-alert-bridge-latest.json",
    "Cron Freshness": "cron-freshness-latest.json",
    "Live Hindsight Refresh": "live-hindsight-refresh-latest.json",
    "System Metrics": "system-metrics-latest.json",
}

TEXT = {
    "zh": {
        "lang": "zh-CN",
        "page_title": "Hermes 记忆体监控中心",
        "hero_title": "Hermes 记忆体监控中心",
        "hero_subtitle": "统一查看 LangSmith、Web 面板、Prometheus、Grafana 与本地告警链路，支持多语言、异常解释、建议动作和逐层下钻。",
        "language": "界面语言",
        "lang_zh": "中文",
        "lang_en": "English",
        "generated_at": "生成时间",
        "metrics_dir": "指标目录",
        "overall_status": "整体状态",
        "view_overview": "总览",
        "view_components": "组件",
        "view_alerts": "告警",
        "view_observability": "观测",
        "summary_total": "组件总数",
        "summary_total_cta": "查看全部组件",
        "summary_healthy": "正常组件",
        "summary_healthy_cta": "查看正常项",
        "summary_attention": "需关注组件",
        "summary_attention_cta": "查看异常项",
        "summary_alerts": "待处理告警",
        "summary_alerts_cta": "查看告警详情",
        "summary_recall": "召回 P95",
        "summary_recall_cta": "查看性能趋势",
        "explanations_title": "原因解读",
        "explanations_subtitle": "把原始系统状态翻译成可读的运维结论，帮助快速理解发生了什么。",
        "actions_title": "建议动作",
        "actions_subtitle": "按影响优先级给出下一步动作，避免只看到红灯却不知道该怎么处理。",
        "attention_title": "异常与关注项",
        "attention_subtitle": "汇总非正常组件，适合先筛选风险，再下钻到具体卡片。",
        "attention_empty": "当前没有需要额外关注的组件。",
        "alerts_title": "告警详情",
        "alerts_subtitle": "支持逐条展开查看来源、原因、上下文和原始 payload。",
        "alerts_empty": "当前没有待进一步处理的告警。",
        "components_title": "核心健康卡片",
        "components_subtitle": "每张卡片都支持展开查看摘要、异常分组和原始 JSON。",
        "observability_title": "Prometheus / Grafana / LangSmith",
        "observability_subtitle": "观测层已经统一：当前状态、长期趋势和链路诊断共用同一个入口。",
        "observability_metrics": "指标入口",
        "observability_api": "状态接口",
        "observability_stack": "部署路径",
        "observability_export": "观测覆盖",
        "observability_export_value": "Web 面板、LangSmith 趋势、OpenMetrics、Grafana 看板、Prometheus 规则",
        "view_details": "展开详情",
        "raw_json": "原始 JSON",
        "no_summary": "暂无摘要信息",
        "none": "无",
        "yes": "是",
        "no": "否",
        "artifact_labels": {
            "Runtime Drift": "运行漂移",
            "Health Summary": "健康总览",
            "LangSmith Trend": "LangSmith 趋势",
            "gbrain Stale": "gbrain 健康",
            "Hindsight Security": "Hindsight 安全",
            "Webhook Receiver": "Webhook 转发",
            "SLO Rollup": "SLO 汇总",
            "Prometheus Alert Bridge": "Prometheus 告警桥接",
            "Cron Freshness": "定时任务新鲜度",
            "System Metrics": "系统资源",
        },
        "detail_labels": {
            "recent_acceptance_ok_rate": "最近接受率",
            "acceptance_ok_rate": "历史接受率",
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
            "artifact": "产物文件",
            "acceptance_ok_rate_slo": "SLO 接受率",
            "alert_queue_growth": "告警队列增长",
            "dead_letter_replay_success_rate": "死信重放成功率",
            "recall_latency_p95_s": "召回 P95（秒）",
            "recall_latency_p50_s": "召回 P50（秒）",
            "recall_latency_max_s": "召回最大延迟（秒）",
            "bridge_alert_count": "桥接告警数",
            "stale_job_count": "陈旧任务数",
            "action_needed_job_count": "失效任务数",
            "memory_available_mb": "可用内存(MB)",
            "swap_pct": "Swap 使用率",
            "disk_pct": "磁盘使用率",
            "state_db_size_mb": "state.db 大小(MB)",
        },
        "sections_reasons": "异常原因",
        "sections_classifications": "分类详情",
        "sections_findings": "发现项",
        "sections_recent_failures": "最近失败",
        "sections_alerts": "告警详情",
        "sections_lag": "延迟详情",
        "sections_upstream_gap": "上游缺口",
        "sections_last_forward": "最近转发原始结果",
        "status_labels": {
            "healthy": "正常",
            "degraded": "降级",
            "action-needed": "需处理",
            "missing": "缺失",
            "unknown": "未知",
            "unreadable": "不可读",
        },
        "severity_labels": {
            "info": "信息",
            "degraded": "需关注",
            "warning": "警告",
            "action-needed": "需处理",
            "critical": "严重",
        },
        "forward_success": "成功，HTTP {status}，尝试 {attempts} 次",
        "forward_failure": "失败，已重试 {attempts} 次",
        "forward_failed": "失败",
    },
    "en": {
        "lang": "en",
        "page_title": "Hermes Memory Control Center",
        "hero_title": "Hermes Memory Control Center",
        "hero_subtitle": "Unified visibility across LangSmith, the web dashboard, Prometheus, Grafana, and the local alerting chain with drilldown, explanations, and suggested actions.",
        "language": "Language",
        "lang_zh": "中文",
        "lang_en": "English",
        "generated_at": "Generated at",
        "metrics_dir": "Metrics dir",
        "overall_status": "Overall status",
        "view_overview": "Overview",
        "view_components": "Components",
        "view_alerts": "Alerts",
        "view_observability": "Observability",
        "summary_total": "Components",
        "summary_total_cta": "View all components",
        "summary_healthy": "Healthy",
        "summary_healthy_cta": "View healthy items",
        "summary_attention": "Needs attention",
        "summary_attention_cta": "View risky items",
        "summary_alerts": "Pending alerts",
        "summary_alerts_cta": "View alert details",
        "summary_recall": "Recall P95",
        "summary_recall_cta": "View performance trends",
        "explanations_title": "Explanations",
        "explanations_subtitle": "Turn raw system states into short operational conclusions.",
        "actions_title": "Suggested Actions",
        "actions_subtitle": "Actionable next steps ordered by impact so operators know what to do next.",
        "attention_title": "Attention Items",
        "attention_subtitle": "Use this list to isolate risky components first, then drill into the exact card.",
        "attention_empty": "There are no components that require extra attention right now.",
        "alerts_title": "Alert Details",
        "alerts_subtitle": "Each alert can be expanded to inspect source, reasons, context fields, and raw payload.",
        "alerts_empty": "There are no alerts that require deeper drilldown right now.",
        "components_title": "Core Health Cards",
        "components_subtitle": "Every card can be expanded to show summary fields, grouped issues, and raw JSON.",
        "observability_title": "Prometheus / Grafana / LangSmith",
        "observability_subtitle": "The observability layer is unified: current state, long-range trends, and trace diagnostics share the same entry point.",
        "observability_metrics": "Metrics endpoint",
        "observability_api": "Status API",
        "observability_stack": "Deployment path",
        "observability_export": "Coverage",
        "observability_export_value": "Web dashboard, LangSmith trend, OpenMetrics, Grafana dashboards, Prometheus rules",
        "view_details": "Expand details",
        "raw_json": "Raw JSON",
        "no_summary": "No summary information",
        "none": "None",
        "yes": "Yes",
        "no": "No",
        "artifact_labels": {
            "Runtime Drift": "Runtime Drift",
            "Health Summary": "Health Summary",
            "LangSmith Trend": "LangSmith Trend",
            "gbrain Stale": "gbrain Health",
            "Hindsight Security": "Hindsight Security",
            "Webhook Receiver": "Webhook Forwarding",
            "SLO Rollup": "SLO Rollup",
            "Prometheus Alert Bridge": "Prometheus Alert Bridge",
            "Cron Freshness": "Cron Freshness",
            "System Metrics": "System Metrics",
        },
        "detail_labels": {
            "recent_acceptance_ok_rate": "Recent acceptance OK rate",
            "acceptance_ok_rate": "Historical acceptance OK rate",
            "lag_status": "Lag status",
            "health_score": "Health score",
            "stale_pages": "Stale pages",
            "actual_orphans": "Actual orphans",
            "classifications": "Classification count",
            "alert_count": "Alert count",
            "external_forward_configured": "External forwarding configured",
            "last_forward": "Last forward result",
            "reason_count": "Reason count",
            "error": "Error",
            "artifact": "Artifact file",
            "acceptance_ok_rate_slo": "SLO acceptance rate",
            "alert_queue_growth": "Alert queue growth",
            "dead_letter_replay_success_rate": "Dead-letter replay success rate",
            "recall_latency_p95_s": "Recall P95 (s)",
            "recall_latency_p50_s": "Recall P50 (s)",
            "recall_latency_max_s": "Recall max latency (s)",
            "bridge_alert_count": "Bridge alert count",
            "stale_job_count": "Stale jobs",
            "action_needed_job_count": "Action-needed jobs",
            "memory_available_mb": "Available memory (MB)",
            "swap_pct": "Swap usage %",
            "disk_pct": "Disk usage %",
            "state_db_size_mb": "state.db size (MB)",
        },
        "sections_reasons": "Reasons",
        "sections_classifications": "Classifications",
        "sections_findings": "Findings",
        "sections_recent_failures": "Recent failures",
        "sections_alerts": "Alerts",
        "sections_lag": "Lag details",
        "sections_upstream_gap": "Upstream gap",
        "sections_last_forward": "Last forward raw result",
        "status_labels": {
            "healthy": "Healthy",
            "degraded": "Degraded",
            "action-needed": "Action needed",
            "missing": "Missing",
            "unknown": "Unknown",
            "unreadable": "Unreadable",
        },
        "severity_labels": {
            "info": "Info",
            "degraded": "Degraded",
            "warning": "Warning",
            "action-needed": "Action needed",
            "critical": "Critical",
        },
        "forward_success": "Success, HTTP {status}, {attempts} attempt(s)",
        "forward_failure": "Failed after {attempts} attempt(s)",
        "forward_failed": "Failed",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "ok": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unreadable", "ok": False, "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "unreadable", "ok": False, "error": "payload_not_object"}


def safe(value: Any) -> str:
    return html.escape(str(value), quote=True)


def slugify(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def copy_for(lang: str) -> dict[str, Any]:
    return TEXT["en"] if lang == "en" else TEXT["zh"]


def localize_status(status: str, lang: str) -> str:
    return copy_for(lang)["status_labels"].get(status, status)


def localize_severity(severity: str, lang: str) -> str:
    return copy_for(lang)["severity_labels"].get(severity, severity)


def artifact_name(name: str, lang: str) -> str:
    return copy_for(lang)["artifact_labels"].get(name, name)


def detail_label(key: str, lang: str) -> str:
    return copy_for(lang)["detail_labels"].get(key, key)


def status_tone(status: str) -> str:
    if status == "healthy":
        return "tone-positive"
    if status in {"degraded", "missing", "unknown"}:
        return "tone-warn"
    return "tone-critical"


def percent(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def float_text(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def format_forward_result(payload: Any, lang: str) -> str | None:
    if not payload:
        return None
    copy = copy_for(lang)
    if not isinstance(payload, dict):
        return str(payload)
    if payload.get("error"):
        attempts = payload.get("attempts")
        if attempts:
            return copy["forward_failure"].format(attempts=attempts)
        return copy["forward_failed"]
    status = payload.get("status")
    attempts = payload.get("attempts")
    if status:
        return copy["forward_success"].format(status=status, attempts=attempts or 1)
    return copy["yes"]


def format_detail_value(key: str, value: Any, lang: str) -> str | None:
    copy = copy_for(lang)
    if value is None:
        return None
    if key in {"recent_acceptance_ok_rate", "acceptance_ok_rate", "acceptance_ok_rate_slo", "dead_letter_replay_success_rate"}:
        return percent(value)
    if key in {"recall_latency_p95_s", "recall_latency_p50_s", "recall_latency_max_s"}:
        return float_text(value)
    if key in {"swap_pct", "disk_pct"}:
        return f"{float(value):.1f}%" if isinstance(value, (int, float)) else str(value)
    if key == "external_forward_configured":
        return copy["yes"] if bool(value) else copy["no"]
    if key == "last_forward":
        return format_forward_result(value, lang)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def infer_langsmith_status(payload: dict[str, Any]) -> str:
    monitor = payload.get("monitor") if isinstance(payload.get("monitor"), dict) else {}
    if payload.get("status"):
        return str(payload["status"])
    if not payload or payload.get("error"):
        return "unknown"
    lag_status = str((monitor.get("lag") or {}).get("status") or "").strip()
    if lag_status in {"healthy", "degraded", "action-needed"}:
        return lag_status
    recent_rate = monitor.get("recent_acceptance_ok_rate")
    if recent_rate in (None, 1.0):
        return "healthy"
    return "degraded"


def summarize(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if name == "LangSmith Trend":
        status = infer_langsmith_status(payload)
        ok = status == "healthy"
    elif name == "System Metrics":
        memory = payload.get("memory") if isinstance(payload.get("memory"), dict) else {}
        disk = payload.get("disk") if isinstance(payload.get("disk"), dict) else {}
        swap_pct = float(memory.get("swap_pct") or 0)
        disk_pct = float(disk.get("pct") or 0)
        if swap_pct >= 80 or disk_pct >= 90:
            status = "action-needed"
        elif swap_pct >= 60 or disk_pct >= 80:
            status = "degraded"
        else:
            status = "healthy"
        ok = status == "healthy"
    else:
        status = str(payload.get("status") or ("healthy" if payload.get("ok") else "unknown"))
        ok = status == "healthy"
    summary: dict[str, Any] = {"name": name, "status": status, "ok": ok}
    if name == "LangSmith Trend":
        monitor = payload.get("monitor") if isinstance(payload.get("monitor"), dict) else {}
        summary["details"] = {
            "recent_acceptance_ok_rate": monitor.get("recent_acceptance_ok_rate"),
            "acceptance_ok_rate": monitor.get("acceptance_ok_rate"),
            "lag_status": (monitor.get("lag") or {}).get("status"),
        }
    elif name == "gbrain Stale":
        after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
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
    elif name == "SLO Rollup":
        recall_latency = payload.get("recall_latency") if isinstance(payload.get("recall_latency"), dict) else {}
        summary["details"] = {
            "acceptance_ok_rate_slo": payload.get("acceptance_ok_rate"),
            "alert_queue_growth": payload.get("alert_queue_growth"),
            "dead_letter_replay_success_rate": payload.get("dead_letter_replay_success_rate"),
            "recall_latency_p95_s": recall_latency.get("p95_s"),
            "recall_latency_p50_s": recall_latency.get("p50_s"),
            "recall_latency_max_s": recall_latency.get("max_s"),
        }
    elif name == "Prometheus Alert Bridge":
        summary["details"] = {
            "bridge_alert_count": payload.get("alert_count"),
            "last_forward": payload.get("forwarded"),
        }
    elif name == "Cron Freshness":
        jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
        summary["details"] = {
            "stale_job_count": sum(1 for job in jobs if job.get("status") == "degraded"),
            "action_needed_job_count": sum(1 for job in jobs if job.get("status") == "action-needed"),
        }
    elif name == "System Metrics":
        memory = payload.get("memory") if isinstance(payload.get("memory"), dict) else {}
        disk = payload.get("disk") if isinstance(payload.get("disk"), dict) else {}
        summary["details"] = {
            "memory_available_mb": memory.get("available_mb"),
            "swap_pct": memory.get("swap_pct"),
            "disk_pct": disk.get("pct"),
            "state_db_size_mb": payload.get("state_db_size_mb"),
        }
    else:
        summary["details"] = {"reason_count": len(payload.get("reasons", [])), "error": payload.get("error")}
    return summary


def dashboard_status_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = {"healthy": 0, "degraded": 0, "action-needed": 0, "missing": 0, "unknown": 0, "unreadable": 0}
    for artifact in payload.get("artifacts", []):
        status = str((artifact.get("summary") or {}).get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def overall_status_from_counts(status_counts: dict[str, int]) -> str:
    if status_counts.get("action-needed") or status_counts.get("unreadable"):
        return "action-needed"
    if status_counts.get("degraded") or status_counts.get("missing") or status_counts.get("unknown"):
        return "degraded"
    return "healthy"


def build_explanations(payload: dict[str, Any], lang: str = "zh") -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    overall = payload["overall_status"]
    if overall == "action-needed":
        out.append(
            {
                "title": "系统存在需要立刻处理的异常" if lang == "zh" else "The system has issues that need action now",
                "body": "至少一个关键组件处于需处理状态，当前监控与告警链路已经检测到真实风险。" if lang == "zh" else "At least one critical component is in action-needed state and the monitoring chain detected a real operational risk.",
            }
        )
    trend = next((item["raw"] for item in payload["artifacts"] if item["name"] == "LangSmith Trend"), {})
    monitor = trend.get("monitor") if isinstance(trend.get("monitor"), dict) else {}
    if (monitor.get("lag") or {}).get("status") == "action-needed":
        out.append(
            {
                "title": "Hindsight 同步延迟偏高" if lang == "zh" else "Hindsight sync lag is high",
                "body": "这通常意味着实时记忆写入或汇总链路落后，召回结果可能变旧。" if lang == "zh" else "This usually means the real-time memory write or summarization pipeline is behind and recall results may become stale.",
            }
        )
    drift = next((item["raw"] for item in payload["artifacts"] if item["name"] == "Runtime Drift"), {})
    if drift.get("status") == "action-needed":
        out.append(
            {
                "title": "运行目录和仓库版本不一致" if lang == "zh" else "Runtime and repository are out of sync",
                "body": "生产脚本与仓库内容不一致时，排障和发布验证会失真。" if lang == "zh" else "When production scripts drift away from the repository, troubleshooting and release validation become unreliable.",
            }
        )
    cron = next((item["raw"] for item in payload["artifacts"] if item["name"] == "Cron Freshness"), {})
    if cron.get("status") == "action-needed":
        out.append(
            {
                "title": "定时任务存在失效或长时间未刷新" if lang == "zh" else "One or more cron jobs are stale or not refreshing",
                "body": "这通常意味着归档、告警、趋势或面板不会继续自动更新，应该先恢复调度链路。" if lang == "zh" else "This usually means archive, alert, trend, or dashboard state will stop refreshing until the scheduling chain is restored.",
            }
        )
    sys_metrics = next((item["raw"] for item in payload["artifacts"] if item["name"] == "System Metrics"), {})
    memory = sys_metrics.get("memory") if isinstance(sys_metrics.get("memory"), dict) else {}
    if float(memory.get("swap_pct") or 0) >= 60:
        out.append(
            {
                "title": "Swap 压力偏高" if lang == "zh" else "Swap pressure is elevated",
                "body": "当前机器已经开始明显依赖 swap，建议优先回收缓存或降低非核心常驻负载。" if lang == "zh" else "The host is relying on swap noticeably; reclaim caches or reduce non-critical resident load first.",
            }
        )
    if not out:
        out.append(
            {
                "title": "当前整体健康" if lang == "zh" else "The system is currently healthy",
                "body": "没有检测到需要立刻处理的核心异常，建议继续观察趋势和近期告警。" if lang == "zh" else "No core issue currently requires immediate action; continue to watch trends and recent alerts.",
            }
        )
    return out


def build_actions(payload: dict[str, Any], lang: str = "zh") -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    drift = next((item["raw"] for item in payload["artifacts"] if item["name"] == "Runtime Drift"), {})
    if drift.get("status") == "action-needed":
        actions.append(
            {
                "title": "先处理脚本漂移" if lang == "zh" else "Fix runtime drift first",
                "body": "重新同步生产脚本与仓库，再重新跑 `audit-deploy` 和接受率检查。" if lang == "zh" else "Resync production scripts with the repository, then rerun deploy audit and acceptance checks.",
            }
        )
    trend = next((item["raw"] for item in payload["artifacts"] if item["name"] == "LangSmith Trend"), {})
    if (trend.get("monitor") or {}).get("lag", {}).get("status") == "action-needed":
        actions.append(
            {
                "title": "检查 Hindsight 积压和同步链路" if lang == "zh" else "Inspect Hindsight backlog and sync chain",
                "body": "优先查看 guardian、archive、summary 和 LangSmith 最近失败记录。" if lang == "zh" else "Inspect guardian, archive, summary, and recent LangSmith failures first.",
            }
        )
    bridge = next((item["raw"] for item in payload["artifacts"] if item["name"] == "Prometheus Alert Bridge"), {})
    if bridge.get("alert_count"):
        actions.append(
            {
                "title": "核对 Prometheus 告警桥接结果" if lang == "zh" else "Verify the Prometheus alert bridge output",
                "body": "确认桥接告警与本地 health summary 告警语义一致，避免重复通知或噪声放大。" if lang == "zh" else "Verify that bridged alerts align with local health-summary alerts to avoid duplicate notifications and amplified noise.",
            }
        )
    cron = next((item["raw"] for item in payload["artifacts"] if item["name"] == "Cron Freshness"), {})
    if cron.get("status") in {"degraded", "action-needed"}:
        actions.append(
            {
                "title": "先恢复定时任务新鲜度" if lang == "zh" else "Restore cron freshness first",
                "body": "优先检查缺失或过期的 cron 任务日志/产物，避免健康面板停止自动刷新。" if lang == "zh" else "Inspect stale cron log/artifact producers first so health state does not silently stop updating.",
            }
        )
    sys_metrics = next((item["raw"] for item in payload["artifacts"] if item["name"] == "System Metrics"), {})
    memory = sys_metrics.get("memory") if isinstance(sys_metrics.get("memory"), dict) else {}
    if float(memory.get("swap_pct") or 0) >= 60:
        actions.append(
            {
                "title": "回收缓存并观察 swap" if lang == "zh" else "Reclaim caches and watch swap",
                "body": "优先清理非核心缓存、重复备份和旧浏览器运行时，再观察 24h 系统趋势。" if lang == "zh" else "Reclaim non-critical caches, duplicate backups, and old browser runtimes first, then watch 24h system trends.",
            }
        )
    if not actions:
        actions.append(
            {
                "title": "继续观察趋势" if lang == "zh" else "Keep watching the trend layer",
                "body": "当前更适合关注 24h/7d 曲线和近期异常，而不是立刻执行变更。" if lang == "zh" else "Focus on 24h/7d trends and recent anomalies instead of making immediate changes.",
            }
        )
    return actions


def build_dashboard_payload(metrics_dir: Path) -> dict:
    artifacts = []
    for name, filename in ARTIFACTS.items():
        payload = load_json(metrics_dir / filename)
        artifacts.append({"name": name, "filename": filename, "summary": summarize(name, payload), "raw": payload})
    status_counts = dashboard_status_counts({"artifacts": artifacts})
    overall_status = overall_status_from_counts(status_counts)
    health_raw = next((item["raw"] for item in artifacts if item["name"] == "Health Summary"), {})
    alerts = health_raw.get("alerts", []) if isinstance(health_raw.get("alerts"), list) else []
    attention_items = [
        {"name": artifact["name"], "status": artifact["summary"]["status"], "filename": artifact["filename"]}
        for artifact in artifacts
        if artifact["summary"]["status"] != "healthy"
    ]
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "ok": overall_status == "healthy",
        "overall_status": overall_status,
        "status_counts": status_counts,
        "metrics_dir": str(metrics_dir),
        "artifacts": artifacts,
        "attention_items": attention_items,
        "alerts": alerts,
    }
    payload["explanations"] = build_explanations(payload, "zh")
    payload["actions"] = build_actions(payload, "zh")
    return payload


def human_summary(payload: dict[str, Any], lang: str = "zh") -> str:
    copy = copy_for(lang)
    counts = payload.get("status_counts") or dashboard_status_counts(payload)
    overall = payload.get("overall_status") or overall_status_from_counts(counts)
    artifacts = payload.get("artifacts", []) if isinstance(payload.get("artifacts"), list) else []
    total = len(artifacts)
    attention = total - counts.get("healthy", 0)
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    alert_count = len(alerts)
    if lang == "en":
        return f"Overall status: {localize_status(overall, lang)}; components={total}; healthy={counts.get('healthy', 0)}; attention={attention}; alerts={alert_count}"
    return f"{copy['overall_status']}：{localize_status(overall, lang)}；组件总数={total}；正常={counts.get('healthy', 0)}；需关注={attention}；告警={alert_count}"


def issue_sections(payload: dict[str, Any], lang: str) -> list[dict[str, Any]]:
    copy = copy_for(lang)
    sections: list[dict[str, Any]] = []
    mappings = [
        ("reasons", copy["sections_reasons"]),
        ("classifications", copy["sections_classifications"]),
        ("findings", copy["sections_findings"]),
        ("recent_failures", copy["sections_recent_failures"]),
        ("alerts", copy["sections_alerts"]),
    ]
    for key, title in mappings:
        value = payload.get(key)
        if isinstance(value, list) and value:
            sections.append({"title": title, "rows": value})
    monitor = payload.get("monitor")
    if isinstance(monitor, dict):
        if isinstance(monitor.get("recent_failures"), list) and monitor["recent_failures"]:
            sections.append({"title": copy["sections_recent_failures"], "rows": monitor["recent_failures"]})
        lag = monitor.get("lag")
        if isinstance(lag, dict) and lag:
            sections.append({"title": copy["sections_lag"], "rows": [lag]})
    last_forward = payload.get("last_forward")
    if isinstance(last_forward, dict) and last_forward:
        sections.append({"title": copy["sections_last_forward"], "rows": [last_forward]})
    return sections


def render_rows(rows: list[dict[str, Any]], lang: str) -> str:
    cards = []
    for row in rows:
        severity = localize_severity(str(row.get("severity") or row.get("status") or "info"), lang)
        header = row.get("code") or row.get("run_name") or row.get("reason") or row.get("title") or "Details"
        body_lines = []
        for key, value in row.items():
            if key in {"code", "severity", "title"}:
                continue
            value_text = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else str(value)
            body_lines.append(f"<tr><th>{safe(detail_label(str(key), lang))}</th><td>{safe(value_text)}</td></tr>")
        cards.append(
            f"""
            <details class="detail-item">
              <summary>
                <span>{safe(str(header))}</span>
                <span class="inline-pill">{safe(severity)}</span>
              </summary>
              <table>{''.join(body_lines)}</table>
            </details>
            """
        )
    return "".join(cards)


def render_story_cards(rows: list[dict[str, str]]) -> str:
    return "".join(f"<article class='story-card'><h3>{safe(row['title'])}</h3><p>{safe(row['body'])}</p></article>" for row in rows)


def language_href(lang: str, query_params: dict[str, str]) -> str:
    params = dict(query_params)
    params["lang"] = lang
    return "/dashboard?" + urlencode(params)


def view_href(view: str, query_params: dict[str, str]) -> str:
    params = dict(query_params)
    params["view"] = view
    return "/dashboard?" + urlencode(params)


def section_class(active_view: str, section_view: str) -> str:
    return "" if active_view in {"overview", section_view} else " hidden"


def render_dashboard(metrics_dir: Path, lang: str = "zh", query_params: dict[str, str] | None = None) -> str:
    copy = copy_for(lang)
    query_params = dict(query_params or {})
    query_params.pop("lang", None)
    active_view = str(query_params.get("view") or "overview")
    if active_view not in {"overview", "components", "alerts", "observability"}:
        active_view = "overview"
    payload = build_dashboard_payload(metrics_dir)
    payload["explanations"] = build_explanations(payload, lang)
    payload["actions"] = build_actions(payload, lang)
    captured_at = datetime.now(timezone.utc).isoformat()
    status_counts = payload["status_counts"]
    overall_status = payload["overall_status"]

    cards = []
    for artifact in payload["artifacts"]:
        name = artifact["name"]
        filename = artifact["filename"]
        raw = artifact["raw"]
        summary = artifact["summary"]
        status = summary["status"]
        detail_rows = "".join(
            f"<tr><th>{safe(detail_label(key, lang))}</th><td>{safe(format_detail_value(key, value, lang))}</td></tr>"
            for key, value in summary.get("details", {}).items()
            if format_detail_value(key, value, lang) is not None
        )
        sections = issue_sections(raw, lang)
        section_html = "".join(f"<section class='issue-section'><h3>{safe(section['title'])}</h3>{render_rows(section['rows'], lang)}</section>" for section in sections)
        cards.append(
            f"""
            <details id="artifact-{safe(slugify(name))}" class="card" {'open' if status != 'healthy' else ''}>
              <summary class="card-head">
                <div>
                  <p class="eyebrow">{safe(filename)}</p>
                  <h2>{safe(artifact_name(name, lang))}</h2>
                </div>
                <div class="summary-actions">
                  <span class="status-pill {status_tone(status)}">{safe(localize_status(status, lang))}</span>
                  <span class="chevron">{safe(copy['view_details'])}</span>
                </div>
              </summary>
              <div class="card-body">
                <table>{detail_rows or f"<tr><td>{safe(copy['no_summary'])}</td></tr>"}</table>
                {section_html}
                <section class="issue-section">
                  <h3>{safe(copy['raw_json'])}</h3>
                  <pre>{safe(json.dumps(raw, ensure_ascii=False, indent=2))}</pre>
                </section>
              </div>
            </details>
            """
        )

    alerts = payload["alerts"]
    attention_rows = [{"code": artifact_name(item["name"], lang), "severity": localize_status(item["status"], lang), "artifact": item["filename"]} for item in payload["attention_items"]]
    attention_html = render_rows(attention_rows, lang) if attention_rows else f"<p class='empty-state'>{safe(copy['attention_empty'])}</p>"
    alerts_html = render_rows(alerts, lang) if alerts else f"<p class='empty-state'>{safe(copy['alerts_empty'])}</p>"

    recall_p95 = copy["none"]
    for artifact in payload["artifacts"]:
        if artifact["name"] == "SLO Rollup":
            recall_latency = artifact["raw"].get("recall_latency") if isinstance(artifact["raw"].get("recall_latency"), dict) else {}
            recall_p95 = format_detail_value("recall_latency_p95_s", recall_latency.get("p95_s"), lang) or copy["none"]
            break

    zh_href = language_href("zh", query_params)
    en_href = language_href("en", query_params)
    overview_href = view_href("overview", query_params)
    components_href = view_href("components", query_params)
    alerts_href = view_href("alerts", query_params)
    observability_href = view_href("observability", query_params)

    return f"""<!doctype html>
<html lang="{safe(copy['lang'])}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe(copy['page_title'])}</title>
  <style>
    :root {{
      --bg: #eef4fb; --bg-strong: #dde9f9; --surface: rgba(255,255,255,.88); --surface-strong: #fff; --surface-soft: #f5f8fe;
      --line: rgba(89,102,126,.18); --text: #17202f; --muted: #5f6b7c; --primary: #0b57d0; --primary-soft: rgba(11,87,208,.1);
      --positive: #137333; --positive-soft: #d7f3df; --warn: #b06000; --warn-soft: #fde6c6; --critical: #c5221f; --critical-soft: #f9dedc;
      --shadow: 0 18px 48px rgba(11,87,208,.11); --radius-xl: 28px; --radius-lg: 20px; --radius-md: 14px;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--text); font-family: "Google Sans","Noto Sans SC","Segoe UI Variable",sans-serif; background:
      linear-gradient(180deg, rgba(11,87,208,.12), transparent 18rem),
      radial-gradient(circle at top left, rgba(66,133,244,.18), transparent 26rem),
      linear-gradient(180deg, var(--bg-strong), var(--bg)); }}
    a {{ color: inherit; text-decoration: none; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px 20px 72px; }}
    .hero,.section {{ background: var(--surface); border: 1px solid rgba(255,255,255,.75); border-radius: var(--radius-lg); box-shadow: var(--shadow); backdrop-filter: blur(16px); }}
    .hero {{ padding: 28px; }} .section {{ margin-top: 28px; padding: 22px 20px; }}
    .hero-top,.section-head,.hero-meta,.toolbar,.lang-switch {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
    .hero-top {{ justify-content: space-between; align-items: start; }}
    .hero h1 {{ margin: 0; font-size: clamp(2.1rem, 4.8vw, 3.7rem); line-height: 1.04; font-weight: 800; }}
    .subtitle,.section-head p {{ color: var(--muted); line-height: 1.65; }} .subtitle {{ margin: 14px 0 0; max-width: 60rem; }}
    .chip,.status-pill,.inline-pill,.toolbar-link,.lang-link {{ display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 40px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--line); background: rgba(255,255,255,.82); font-weight: 700; }}
    .inline-pill {{ min-height: 30px; padding: 0 10px; font-size: .84rem; color: var(--primary); background: var(--primary-soft); border-color: transparent; }}
    .toolbar-link.active,.lang-link.active {{ color: var(--primary); background: var(--primary-soft); border-color: rgba(11,87,208,.22); }}
    .tone-positive {{ background: var(--positive-soft); color: var(--positive); border-color: transparent; }}
    .tone-warn {{ background: var(--warn-soft); color: var(--warn); border-color: transparent; }}
    .tone-critical {{ background: var(--critical-soft); color: var(--critical); border-color: transparent; }}
    .summary-grid,.story-grid,.observability-grid,.grid {{ display: grid; gap: 16px; }}
    .summary-grid {{ grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); margin-top: 22px; }}
    .story-grid {{ grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); }}
    .observability-grid {{ grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); }}
    .grid {{ grid-template-columns: repeat(auto-fit, minmax(320px,1fr)); }}
    .summary-link,.story-card,.observability-card,.card {{ background: var(--surface-strong); border: 1px solid var(--line); border-radius: 8px; }}
    .summary-link {{ padding: 18px; display: block; }} .story-card,.observability-card {{ padding: 18px; }}
    .summary-link p,.story-card p,.observability-card p {{ margin: 0; color: var(--muted); }}
    .summary-link strong {{ display: block; margin-top: 8px; font-size: 2rem; }} .summary-link span {{ display: block; margin-top: 8px; color: var(--primary); font-size: .9rem; }}
    .story-card h3,.observability-card h3 {{ margin: 0 0 10px; }}
    .hidden {{ display: none; }}
    .card-head {{ list-style: none; display: flex; justify-content: space-between; gap: 12px; align-items: start; padding: 18px; cursor: pointer; }}
    .card-body {{ padding: 0 18px 18px; }} .eyebrow {{ margin: 0 0 8px; color: var(--primary); font-size: .78rem; font-weight: 700; }}
    .summary-actions {{ display: flex; flex-direction: column; align-items: end; gap: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .94rem; }} th,td {{ text-align: left; border-top: 1px solid var(--line); padding: 10px 0; vertical-align: top; }} th {{ width: 42%; color: var(--muted); font-weight: 700; }}
    .detail-item {{ background: rgba(255,255,255,.72); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 12px 14px; margin-top: 10px; }}
    .detail-item summary {{ cursor: pointer; display: flex; justify-content: space-between; gap: 10px; align-items: center; font-weight: 700; }}
    .empty-state {{ margin: 0; padding: 18px; background: rgba(255,255,255,.72); border-radius: var(--radius-md); border: 1px solid var(--line); color: var(--muted); }}
    pre {{ overflow: auto; white-space: pre-wrap; font-size: .82rem; color: #243044; background: var(--surface-soft); border-radius: 12px; padding: 14px; margin: 14px 0 0; }}
  </style>
</head>
<body>
  <main>
    <section class="hero" id="section-overview">
      <div class="hero-top">
        <div><h1>{safe(copy['hero_title'])}</h1><p class="subtitle">{safe(copy['hero_subtitle'])}</p></div>
        <div class="lang-switch">
          <span class="chip">{safe(copy['language'])}</span>
          <a class="lang-link {'active' if lang == 'zh' else ''}" href="{safe(zh_href)}">{safe(copy['lang_zh'])}</a>
          <a class="lang-link {'active' if lang == 'en' else ''}" href="{safe(en_href)}">{safe(copy['lang_en'])}</a>
        </div>
      </div>
      <div class="hero-meta">
        <span class="chip">{safe(copy['generated_at'])}: {safe(captured_at)}</span>
        <span class="chip">{safe(copy['metrics_dir'])}: {safe(metrics_dir)}</span>
        <span class="status-pill {status_tone(overall_status)}">{safe(copy['overall_status'])}: {safe(localize_status(overall_status, lang))}</span>
      </div>
      <div class="toolbar">
        <a class="toolbar-link {'active' if active_view == 'overview' else ''}" href="{safe(overview_href)}">{safe(copy['view_overview'])}</a>
        <a class="toolbar-link {'active' if active_view == 'components' else ''}" href="{safe(components_href)}">{safe(copy['view_components'])}</a>
        <a class="toolbar-link {'active' if active_view == 'alerts' else ''}" href="{safe(alerts_href)}">{safe(copy['view_alerts'])}</a>
        <a class="toolbar-link {'active' if active_view == 'observability' else ''}" href="{safe(observability_href)}">{safe(copy['view_observability'])}</a>
      </div>
      <div class="summary-grid">
        <a class="summary-link" href="#section-components"><p>{safe(copy['summary_total'])}</p><strong>{len(ARTIFACTS)}</strong><span>{safe(copy['summary_total_cta'])}</span></a>
        <a class="summary-link" href="#section-components"><p>{safe(copy['summary_healthy'])}</p><strong>{status_counts.get('healthy', 0)}</strong><span>{safe(copy['summary_healthy_cta'])}</span></a>
        <a class="summary-link" href="#section-attention"><p>{safe(copy['summary_attention'])}</p><strong>{len(payload['attention_items'])}</strong><span>{safe(copy['summary_attention_cta'])}</span></a>
        <a class="summary-link" href="#section-alerts"><p>{safe(copy['summary_alerts'])}</p><strong>{len(alerts)}</strong><span>{safe(copy['summary_alerts_cta'])}</span></a>
        <a class="summary-link" href="#section-observability"><p>{safe(copy['summary_recall'])}</p><strong>{safe(recall_p95)}</strong><span>{safe(copy['summary_recall_cta'])}</span></a>
      </div>
    </section>

    <section class="section{section_class(active_view, 'overview')}"><div class="section-head"><div><h2>{safe(copy['explanations_title'])}</h2><p>{safe(copy['explanations_subtitle'])}</p></div></div><div class="story-grid">{render_story_cards(payload['explanations'])}</div></section>
    <section class="section{section_class(active_view, 'overview')}"><div class="section-head"><div><h2>{safe(copy['actions_title'])}</h2><p>{safe(copy['actions_subtitle'])}</p></div></div><div class="story-grid">{render_story_cards(payload['actions'])}</div></section>
    <section id="section-attention" class="section{section_class(active_view, 'overview')}"><div class="section-head"><div><h2>{safe(copy['attention_title'])}</h2><p>{safe(copy['attention_subtitle'])}</p></div></div>{attention_html}</section>
    <section id="section-alerts" class="section{section_class(active_view, 'alerts')}"><div class="section-head"><div><h2>{safe(copy['alerts_title'])}</h2><p>{safe(copy['alerts_subtitle'])}</p></div></div>{alerts_html}</section>
    <section id="section-components" class="section{section_class(active_view, 'components')}"><div class="section-head"><div><h2>{safe(copy['components_title'])}</h2><p>{safe(copy['components_subtitle'])}</p></div></div><div class="grid">{''.join(cards)}</div></section>
    <section id="section-observability" class="section{section_class(active_view, 'observability')}"><div class="section-head"><div><h2>{safe(copy['observability_title'])}</h2><p>{safe(copy['observability_subtitle'])}</p></div></div><div class="observability-grid"><article class="observability-card"><h3>{safe(copy['observability_metrics'])}</h3><p><code>/metrics</code></p></article><article class="observability-card"><h3>{safe(copy['observability_api'])}</h3><p><code>/api/status?lang=zh|en</code></p></article><article class="observability-card"><h3>{safe(copy['observability_export'])}</h3><p>{safe(copy['observability_export_value'])}</p></article><article class="observability-card"><h3>{safe(copy['observability_stack'])}</h3><p><code>deploy/observability/</code></p></article></div></section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default=str(METRICS_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    args = parser.parse_args()
    metrics_dir = Path(args.metrics_dir).expanduser()
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(metrics_dir, lang=args.lang), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output), "lang": args.lang}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
