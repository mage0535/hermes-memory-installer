#!/usr/bin/env python3
"""Cross-check Memory Sidecar storage layers without exposing stored content."""

from __future__ import annotations

import json
import os
import argparse
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen
from datetime import datetime, timezone


_AGENT_HOME_RAW = os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME")
if not _AGENT_HOME_RAW:
    sys.stderr.write(
        "WARNING: AGENT_HOME/HERMES_HOME not set; defaulting to ~/.hermes "
        "(production-safe but not a portable multi-agent contract).\n"
    )
AGENT_HOME = Path(_AGENT_HOME_RAW or str(Path.home() / ".hermes")).expanduser()
STATE_DB = Path(os.environ.get("MEMORY_STATE_DB_PATH", str(AGENT_HOME / "state.db"))).expanduser()
GOVERNANCE_DB = Path(os.environ.get("MEMORY_GOVERNANCE_DB_PATH", str(AGENT_HOME / "memory_governance.db"))).expanduser()
DEFAULT_OUTPUT = AGENT_HOME / "metrics" / "storage-cross-check-latest.json"
HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_BASE_URL", "http://127.0.0.1:8890")
HINDSIGHT_BANK = os.environ.get("HINDSIGHT_BANK", "hermes")
HINDSIGHT_AUTH_TOKEN = os.environ.get("MEMORY_HINDSIGHT_TOKEN") or os.environ.get("HINDSIGHT_AUTH_TOKEN") or ""


def hindsight_headers() -> dict:
    if not HINDSIGHT_AUTH_TOKEN:
        return {}
    return {
        "Authorization": f"Bearer {HINDSIGHT_AUTH_TOKEN}",
        "X-Hindsight-Token": HINDSIGHT_AUTH_TOKEN,
    }


def sqlite_table_counts(path: Path, tables: tuple[str, ...]) -> dict:
    if not path.exists():
        return {"exists": False}
    out = {"exists": True, "size_bytes": path.stat().st_size, "tables": {}}
    try:
        conn = sqlite3.connect(str(path))
        existing = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for table in tables:
            if table not in existing:
                continue
            out["tables"][table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.close()
    except Exception as exc:
        out["error"] = str(exc)
    return out


def hindsight_stats() -> dict:
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{HINDSIGHT_BANK}/stats"
    try:
        with urlopen(Request(url, headers=hindsight_headers()), timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "ok": True,
            "total_documents": payload.get("total_documents"),
            "total_nodes": payload.get("total_nodes"),
            "total_observations": payload.get("total_observations"),
            "pending_consolidation": payload.get("pending_consolidation"),
            "failed_consolidation": payload.get("failed_consolidation"),
        }
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def gbrain_health() -> dict:
    try:
        proc = subprocess.run(["gbrain", "health"], capture_output=True, text=True, timeout=30)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    text = proc.stdout + proc.stderr
    patterns = {
        "health_score": r"Health score:\s*(\d+)/10",
        "missing_embeddings": r"Missing embeddings:\s*(\d+)",
        "stale_pages": r"Stale pages:\s*(\d+)",
        "orphan_pages": r"Orphan pages:\s*(\d+)",
    }
    out = {"ok": proc.returncode == 0}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            out[key] = int(match.group(1))
    try:
        orphan_proc = subprocess.run(["gbrain", "orphans", "--json"], capture_output=True, text=True, timeout=30)
        payload = json.loads(orphan_proc.stdout or "{}")
        rows = payload.get("orphans") if isinstance(payload.get("orphans"), list) else []
        out["orphan_pages_actual"] = len(
            [
                row
                for row in rows
                if isinstance(row, dict)
                and (slug := str(row.get("slug") or ""))
                and slug != "hub-orphan-index"
                and not slug.startswith("hub-orphans-")
            ]
        )
    except Exception as exc:
        out["orphan_count_error"] = str(exc)
    return out


def evaluate(payload: dict) -> list[str]:
    warnings = []
    if not payload["state_db"].get("exists"):
        warnings.append("state_db_missing")
    if not payload["governance_db"].get("exists"):
        warnings.append("governance_db_missing")
    if not payload["hindsight"].get("ok"):
        warnings.append("hindsight_unreachable")
    if not payload["gbrain"].get("ok"):
        warnings.append("gbrain_health_failed")
    failed_consolidation = int(payload["hindsight"].get("failed_consolidation") or 0)
    pending_consolidation = int(payload["hindsight"].get("pending_consolidation") or 0)
    if failed_consolidation > 0 and pending_consolidation >= int(os.environ.get("MEMORY_STORAGE_PENDING_CONSOLIDATION_WARN", "20")):
        warnings.append("hindsight_failed_consolidation")
    if int(payload["gbrain"].get("missing_embeddings") or 0) > 0:
        warnings.append("gbrain_missing_embeddings")
    if int(payload["gbrain"].get("orphan_pages_actual", payload["gbrain"].get("orphan_pages") or 0) or 0) > 0:
        warnings.append("gbrain_orphans")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "state_db": sqlite_table_counts(STATE_DB, ("sessions", "messages", "conversation_history")),
        "governance_db": sqlite_table_counts(
            GOVERNANCE_DB,
            ("governance_meta", "session_search", "canonical_objects", "knowledge_notes"),
        ),
        "hindsight": hindsight_stats(),
        "gbrain": gbrain_health(),
    }
    warnings = evaluate(payload)
    payload["ok"] = not warnings
    payload["warnings"] = warnings
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
