#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _coerce_number(value: str | None) -> int | float | str | None:
    if value is None:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except Exception:
        return value


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def build_report_payload(db_path: Path, top_notes: int = 5) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        governance_meta = {}
        if _table_exists(conn, "governance_meta"):
            governance_meta = {
                row["key"]: _coerce_number(row["value"])
                for row in conn.execute("SELECT key, value FROM governance_meta").fetchall()
            }
        top_note_rows = []
        if _table_exists(conn, "knowledge_note_index"):
            top_note_rows = conn.execute(
                """
                SELECT note_id, source_path, title, tags, modified_at
                FROM knowledge_note_index
                ORDER BY modified_at DESC
                LIMIT ?
                """,
                (top_notes,),
            ).fetchall()
        recall_rollups = []
        if _table_exists(conn, "recall_metric_rollups"):
            cols = _table_columns(conn, "recall_metric_rollups")
            select_cols = [
                "intent",
                "sample_count",
                "avg_duration_ms",
                "p50_duration_ms",
                "p95_duration_ms",
                "avg_live_hindsight_used",
                "avg_live_hindsight_results",
                "avg_cache_hits",
                "avg_cache_misses",
                "avg_weak_fallback_suppressed",
                "avg_knowledge_hit",
                "knowledge_top1_rate",
                "knowledge_top3_rate",
                "updated_at",
            ]
            available = [col for col in select_cols if col in cols]
            recall_rollups = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT {", ".join(available)}
                    FROM recall_metric_rollups
                    ORDER BY sample_count DESC, updated_at DESC
                    """
                ).fetchall()
            ]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "db_path": str(db_path),
            "governance": {
                "knowledge_notes_total": int(governance_meta.get("knowledge_notes_total", 0) or 0),
                "hindsight_items_total": int(governance_meta.get("hindsight_items_total", 0) or 0),
                "last_rebuild_at": governance_meta.get("last_rebuild_at"),
            },
            "top_notes": [
                {
                    "note_id": row["note_id"],
                    "source_path": row["source_path"],
                    "title": row["title"],
                    "tags": row["tags"],
                    "modified_at": row["modified_at"],
                }
                for row in top_note_rows
            ],
            "recall_rollups": recall_rollups,
        }
    finally:
        conn.close()


def render_markdown(payload: dict) -> str:
    lines = [
        "# Memory Observability Report",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Governance DB: `{payload['db_path']}`",
        f"- Knowledge notes: `{payload['governance']['knowledge_notes_total']}`",
        f"- Hindsight items: `{payload['governance']['hindsight_items_total']}`",
        "",
        "## Top Notes",
        "",
    ]
    if payload["top_notes"]:
        for row in payload["top_notes"]:
            lines.append(f"- `{row['source_path']}` — {row['title']}")
    else:
        lines.append("- No indexed knowledge notes")
    lines.extend(["", "## Recall Rollups", ""])
    if payload["recall_rollups"]:
        lines.append("| Intent | Samples | Avg ms | P95 ms | Knowledge hit | Knowledge top1 | Knowledge top3 | Avg cache hits |")
        lines.append("|--------|---------|--------|--------|---------------|----------------|----------------|----------------|")
        for row in payload["recall_rollups"]:
            lines.append(
                f"| {row['intent']} | {row['sample_count']} | {row.get('avg_duration_ms') or 0} | "
                f"{row.get('p95_duration_ms') or 0} | {row.get('avg_knowledge_hit') or 0} | "
                f"{row.get('knowledge_top1_rate') or 0} | {row.get('knowledge_top3_rate') or 0} | "
                f"{row.get('avg_cache_hits') or 0} |"
            )
    else:
        lines.append("- No recall rollups available")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory sidecar observability report")
    parser.add_argument("--db", required=True, help="Path to governance DB")
    parser.add_argument("--top-notes", type=int, default=5)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    payload = build_report_payload(Path(args.db), top_notes=args.top_notes)
    if args.format == "markdown":
        print(render_markdown(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
