#!/usr/bin/env python3
"""Classify and optionally refresh gbrain stale-page health debt."""

from __future__ import annotations

import argparse
import json
import os
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
DEFAULT_GBRAIN_ENV_FILE = Path(os.environ.get("GBRAIN_ENV_FILE", str(Path.home() / ".gbrain.env"))).expanduser()
DEFAULT_GBRAIN_CONFIG_FILE = Path(os.environ.get("GBRAIN_CONFIG_FILE", str(Path.home() / ".gbrain" / "config.json"))).expanduser()
GBRAIN_EMBED_BIN = os.environ.get("GBRAIN_EMBED_BIN") or "gbrain-embed"
GBRAIN_DEORPHAN_BIN = os.environ.get(
    "GBRAIN_DEORPHAN_BIN",
    str((Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser() / "scripts" / "gbrain-bulk-deorphan-wrapper.sh")),
)
DEFAULT_STALE_BUDGET = max(0, int(os.environ.get("GBRAIN_STALE_REFRESH_BUDGET", "100")))
DEFAULT_MISSING_BUDGET = max(0, int(os.environ.get("GBRAIN_MISSING_REFRESH_BUDGET", "0")))
DEFAULT_PREVIOUS_REPORT = Path(
    os.environ.get(
        "GBRAIN_STALE_PREVIOUS_REPORT",
        str(
            Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
            / "metrics"
            / "gbrain-stale-latest.json"
        ),
    )
).expanduser()


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def gbrain_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(load_env_file(DEFAULT_GBRAIN_ENV_FILE))
    return env


def gbrain_database_url() -> str | None:
    env = gbrain_env()
    if env.get("GBRAIN_DATABASE_URL"):
        return env["GBRAIN_DATABASE_URL"]
    if env.get("DATABASE_URL"):
        return env["DATABASE_URL"]
    if DEFAULT_GBRAIN_CONFIG_FILE.exists():
        try:
            payload = json.loads(DEFAULT_GBRAIN_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if payload.get("engine") == "postgres" and payload.get("database_url"):
            return str(payload["database_url"])
    return None


def run(command: list[str], timeout: int = 300) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=gbrain_env())
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"command not found: {command[0]}"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "timeout"}
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def find_missing_embedding_slugs(limit: int = 10) -> list[str]:
    db_url = gbrain_database_url()
    if not db_url:
        return []
    query = (
        "SELECT p.slug "
        "FROM pages p "
        "WHERE EXISTS ("
        "  SELECT 1 FROM content_chunks c "
        "  WHERE c.page_id = p.id AND c.embedding IS NULL"
        ") "
        "ORDER BY p.updated_at DESC "
        f"LIMIT {max(1, int(limit))};"
    )
    result = run(["psql", db_url, "-At", "-c", query], timeout=120)
    if result.get("returncode") != 0:
        return []
    return [line.strip() for line in (result.get("stdout") or "").splitlines() if line.strip()]


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
        "embed_all_found_chunks": None,
        "reindex_code_failures": None,
    }
    for action in actions:
        stdout = action.get("stdout") or ""
        if action.get("name") == "embed_stale":
            match = re.search(r"Embedded\s+(\d+)\s+chunks", stdout)
            if match:
                summary["embed_stale_found_chunks"] = int(match.group(1))
        if action.get("name") == "embed_all":
            match = re.search(r"Embedded\s+(\d+)\s+chunks", stdout)
            if match:
                summary["embed_all_found_chunks"] = int(match.group(1))
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
        if effects and (
            effects.get("embed_stale_found_chunks") == 0
            or (
                int(health.get("missing_embeddings") or 0) == 0
                and effects.get("stale_pages_changed") is False
                and effects.get("embed_stale_found_chunks") is not None
            )
        ):
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


def upstream_gap(classifications: list[dict]) -> dict:
    codes = {item.get("code") for item in classifications}
    panel_only_codes = {
        "stale_health_counter_not_embedding_stale",
        "reported_orphans_counter_discrepancy",
    }
    active = bool(codes & panel_only_codes)
    return {
        "active": active,
        "reason": "gbrain health reports non-actionable panel counters" if active else None,
        "required_capability": (
            "Expose stale/orphan contributors via JSON, or stop counting non-actionable cached counters in health score."
            if active
            else None
        ),
        "public_request": "docs/gbrain-stale-upstream-request.md" if active else None,
    }


def load_previous_report(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def previous_panel_only_evidence(previous: dict, health: dict) -> bool:
    classifications = previous.get("classifications") if isinstance(previous.get("classifications"), list) else []
    codes = {item.get("code") for item in classifications if isinstance(item, dict)}
    if "stale_health_counter_not_embedding_stale" not in codes:
        return False
    if int(health.get("missing_embeddings") or 0) != 0:
        return False
    if int(health.get("orphan_pages_actual") or 0) != 0:
        return False
    previous_after = previous.get("after") if isinstance(previous.get("after"), dict) else {}
    previous_stale = previous_after.get("stale_pages")
    current_stale = health.get("stale_pages")
    return previous_stale is None or int(previous_stale or 0) == int(current_stale or 0)


def actual_orphan_count() -> int | None:
    return len(filtered_orphan_rows())


def filtered_orphan_rows() -> list[dict]:
    result = run(["gbrain", "orphans", "--count"], timeout=60)
    if result.get("returncode") == 0:
        rows_result = run(["gbrain", "orphans", "--json"], timeout=120)
        try:
            payload = json.loads(rows_result.get("stdout") or "{}")
        except json.JSONDecodeError:
            payload = {}
        rows = payload.get("orphans") if isinstance(payload.get("orphans"), list) else []
        filtered = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "")
            if slug == "hub-orphan-index" or slug.startswith("hub-orphans-"):
                continue
            filtered.append(row)
        return filtered
    return []


def embed_command(mode: str, budget: int) -> list[str]:
    command = [GBRAIN_EMBED_BIN, "embed", mode]
    if budget > 0:
        command.extend(["--limit", str(budget)])
    return command


def public_embed_command(mode: str, budget: int) -> list[str]:
    command = ["gbrain", "embed", mode]
    if budget > 0:
        command.extend(["--limit", str(budget)])
    return command


def public_slug_embed_command(slugs: list[str]) -> list[str]:
    return ["gbrain", "embed", "--slugs", *slugs]


def embed_missing_slugs(actions: list[dict], missing_count: int, name: str) -> None:
    if missing_count <= 0:
        return
    missing_slugs = find_missing_embedding_slugs(limit=max(1, int(missing_count)))
    if not missing_slugs:
        return
    action = run(["gbrain", "embed", "--slugs", *missing_slugs], timeout=900)
    actions.append({"name": name, "command": public_slug_embed_command(missing_slugs), **action})


def build_report(
    refresh_embeddings: bool,
    reindex_code: bool,
    output: str,
    stale_budget: int = DEFAULT_STALE_BUDGET,
    missing_budget: int = DEFAULT_MISSING_BUDGET,
    previous_report_path: Path | None = DEFAULT_PREVIOUS_REPORT,
) -> dict:
    before_cmd = run(["gbrain", "health"], timeout=60)
    before = parse_health(before_cmd["stdout"] + before_cmd["stderr"])
    actions = []

    if refresh_embeddings and int(before.get("stale_pages") or 0) > 0 and stale_budget != 0:
        action = run(embed_command("--stale", stale_budget), timeout=900)
        actions.append({"name": "embed_stale", "command": public_embed_command("--stale", stale_budget), **action})
    if refresh_embeddings and int(before.get("missing_embeddings") or 0) > 0:
        embed_missing_slugs(actions, int(before.get("missing_embeddings") or 0), "embed_missing_slugs")
    if refresh_embeddings and int(before.get("missing_embeddings") or 0) > 0 and missing_budget != 0:
        action = run(embed_command("--all", missing_budget), timeout=1800)
        actions.append({"name": "embed_all", "command": public_embed_command("--all", missing_budget), **action})

    if reindex_code:
        action = run(["gbrain", "reindex-code", "--yes"], timeout=900)
        actions.append({"name": "reindex_code", "command": ["gbrain", "reindex-code", "--yes"], **action})
    if int(before.get("orphan_pages") or 0) > 0:
        action = run([GBRAIN_DEORPHAN_BIN], timeout=900)
        actions.append({"name": "deorphan", "command": [GBRAIN_DEORPHAN_BIN], **action})
        if refresh_embeddings:
            post_deorphan_cmd = run(["gbrain", "health"], timeout=60)
            post_deorphan = parse_health(post_deorphan_cmd["stdout"] + post_deorphan_cmd["stderr"])
            embed_missing_slugs(
                actions,
                int(post_deorphan.get("missing_embeddings") or 0),
                "embed_post_deorphan_missing_slugs",
            )

    after_cmd = run(["gbrain", "health"], timeout=60)
    after = parse_health(after_cmd["stdout"] + after_cmd["stderr"])
    actual_orphans = actual_orphan_count()
    after["orphan_pages_actual"] = actual_orphans
    effects = action_summary(actions, before, after)
    previous = load_previous_report(previous_report_path)
    if not refresh_embeddings and not reindex_code and previous_panel_only_evidence(previous, after):
        effects["stale_pages_changed"] = False
        effects["embed_stale_found_chunks"] = 0
    classifications = classify_health(after, effects)
    actionable = [item for item in classifications if item.get("severity") in {"action-needed", "degraded"}]
    status = "healthy" if not actionable else "degraded"
    if any(item["severity"] == "action-needed" for item in classifications):
        status = "action-needed"
    actions_ok = bool(actions) and all((action.get("returncode") or 0) == 0 for action in actions)
    auto_fix_succeeded = actions_ok and not actionable

    report = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status == "healthy",
        "before": before,
        "after": after,
        "classifications": classifications,
        "upstream_gap": upstream_gap(classifications),
        "action_effects": effects,
        "refresh_budget": {"stale": stale_budget, "missing": missing_budget},
        "actions": actions,
        "auto_fix_attempted": bool(actions),
        "auto_fix_succeeded": auto_fix_succeeded,
        "auto_fix_failed": bool(actions) and not auto_fix_succeeded,
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
    parser.add_argument("--stale-budget", type=int, default=DEFAULT_STALE_BUDGET)
    parser.add_argument("--missing-budget", type=int, default=DEFAULT_MISSING_BUDGET)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = build_report(args.refresh_embeddings, args.reindex_code, args.output, args.stale_budget, args.missing_budget)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
