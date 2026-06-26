#!/usr/bin/env python3
"""Classify and optionally refresh gbrain stale-page health debt."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HEALTH_PATTERNS = {
    "health_score": r"Health score:\s*(\d+)/10",
    "missing_embeddings": r"Missing embeddings:\s*(\d+)",
    "stale_pages": r"Stale pages:\s*(\d+)",
    "orphan_pages": r"Orphan pages:\s*(\d+)",
}


def run(command: list[str], timeout: int = 300) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"command not found: {command[0]}"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "timeout"}
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def parse_health(text: str) -> dict:
    out = {}
    for key, pattern in HEALTH_PATTERNS.items():
        match = re.search(pattern, text)
        out[key] = int(match.group(1)) if match else None
    out["ok"] = out.get("health_score") is not None
    return out


def action_summary(actions: list[dict], before: dict, after: dict) -> dict:
    stale_before = int(before.get("stale_pages") or 0)
    stale_after = int(after.get("stale_pages") or 0)
    summary = {
        "stale_pages_changed": stale_after != stale_before,
        "stale_pages_delta": stale_after - stale_before,
        "embed_stale_found_chunks": None,
        "reindex_code_failures": None,
    }
    for action in actions:
        stdout = action.get("stdout") or ""
        if action.get("name") == "embed_stale":
            match = re.search(r"Embedded\s+(\d+)\s+chunks", stdout)
            if match:
                summary["embed_stale_found_chunks"] = int(match.group(1))
        if action.get("name") == "reindex_code":
            match = re.search(r"(\d+)\s+failed", stdout)
            if match:
                summary["reindex_code_failures"] = int(match.group(1))
    return summary


def classify_health(health: dict, effects: dict | None = None) -> list[dict]:
    stale = int(health.get("stale_pages") or 0)
    missing = int(health.get("missing_embeddings") or 0)
    orphans = int(health.get("orphan_pages") or 0)
    actual_orphans = int(health.get("orphan_pages_actual") or 0)
    items = []
    if stale:
        code = "stale_embeddings_or_pages"
        severity = "degraded"
        recommendation = "gbrain embed --stale"
        if effects and effects.get("embed_stale_found_chunks") == 0:
            code = "stale_health_counter_not_embedding_stale"
            severity = "info"
            recommendation = "classify stale pages or fix gbrain health accounting"
        if effects and effects.get("reindex_code_failures"):
            severity = "degraded"
            recommendation = "fix code page metadata, then rerun gbrain reindex-code --yes"
        items.append(
            {
                "code": code,
                "severity": severity,
                "count": stale,
                "recommended_action": recommendation,
            }
        )
    if missing:
        items.append(
            {
                "code": "missing_embeddings",
                "severity": "action-needed",
                "count": missing,
                "recommended_action": "gbrain embed --all",
            }
        )
    if actual_orphans > 0:
        items.append(
            {
                "code": "actual_orphans",
                "severity": "degraded",
                "count": actual_orphans,
                "recommended_action": "run gbrain deorphan wrapper",
            }
        )
    elif orphans:
        items.append(
            {
                "code": "reported_orphans_counter_discrepancy",
                "severity": "info",
                "count": orphans,
                "recommended_action": "treat as gbrain health-panel counter discrepancy",
            }
        )
    return items


def actual_orphan_count() -> int | None:
    result = run(["gbrain", "orphans", "--count"], timeout=60)
    match = re.search(r"(\d+)", (result.get("stdout") or "") + (result.get("stderr") or ""))
    return int(match.group(1)) if match else None


def build_report(refresh_embeddings: bool, reindex_code: bool, output: str) -> dict:
    before_cmd = run(["gbrain", "health"], timeout=60)
    before = parse_health(before_cmd["stdout"] + before_cmd["stderr"])
    actions = []

    if refresh_embeddings and int(before.get("stale_pages") or 0) > 0:
        action = run(["gbrain", "embed", "--stale"], timeout=900)
        actions.append({"name": "embed_stale", "command": ["gbrain", "embed", "--stale"], **action})

    if reindex_code:
        action = run(["gbrain", "reindex-code", "--yes"], timeout=900)
        actions.append({"name": "reindex_code", "command": ["gbrain", "reindex-code", "--yes"], **action})

    after_cmd = run(["gbrain", "health"], timeout=60)
    after = parse_health(after_cmd["stdout"] + after_cmd["stderr"])
    actual_orphans = actual_orphan_count()
    if actual_orphans is not None:
        after["orphan_pages_actual"] = actual_orphans
    effects = action_summary(actions, before, after)
    classifications = classify_health(after, effects)
    actionable = [item for item in classifications if item.get("severity") in {"action-needed", "degraded"}]
    status = "healthy" if not actionable else "degraded"
    if any(item["severity"] == "action-needed" for item in classifications):
        status = "action-needed"

    report = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status == "healthy",
        "before": before,
        "after": after,
        "classifications": classifications,
        "action_effects": effects,
        "actions": actions,
    }
    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-embeddings", action="store_true")
    parser.add_argument("--reindex-code", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = build_report(args.refresh_embeddings, args.reindex_code, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
