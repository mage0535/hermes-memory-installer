#!/usr/bin/env python3
"""
Agent Session -> gbrain Archiver

Reads finished sessions from state.db and outputs structured JSON for
gbrain ingestion via MCP tools. Designed for both one-time bulk archive
and daily incremental runs.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

from session_to_gbrain import ensure_gbrain_page
from state_db_schema import detect_state_schema, sql_expr

AGENT_HOME = os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME") or os.path.expanduser("~/.agent")
STATE_DB = os.path.join(AGENT_HOME, "state.db")
MARKER_KEY = "gbrain_archive_watermark"


def connect_db():
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_state_meta(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()


def get_watermark(conn):
    return get_archive_cursor(conn)[0]


def get_archive_cursor(conn):
    ensure_state_meta(conn)
    cur = conn.execute("SELECT value FROM state_meta WHERE key = ?", (MARKER_KEY,))
    row = cur.fetchone()
    if not row:
        return 0.0, ""
    raw = str(row[0])
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return float(payload.get("timestamp") or 0.0), str(payload.get("session_id") or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return float(raw), ""


def set_watermark(conn, ts):
    set_archive_cursor(conn, ts, "")


def set_archive_cursor(conn, ts, session_id):
    ensure_state_meta(conn)
    value = json.dumps(
        {"timestamp": float(ts), "session_id": str(session_id or "")},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    conn.execute("INSERT OR REPLACE INTO state_meta (key, value) VALUES (?, ?)", (MARKER_KEY, value))
    conn.commit()


def fetch_sessions(
    conn,
    older_than_days,
    watermark,
    batch_size,
    all_sessions,
    cursor_session_id="",
):
    schema = detect_state_schema(conn)
    cutoff = datetime.datetime.now() - datetime.timedelta(days=older_than_days)
    cutoff_ts = cutoff.timestamp()
    query = f"""
        SELECT id,
               COALESCE({sql_expr(schema.session_source, "'unknown'")}, 'unknown') AS source,
               COALESCE({sql_expr(schema.session_title, "''")}, '') AS title,
               {sql_expr(schema.session_started_at, "0", "started_at")} ,
               {sql_expr(schema.session_ended_at, "0", "ended_at")} ,
               COALESCE({sql_expr(schema.session_end_reason, "''")}, '') AS end_reason,
               COALESCE({sql_expr(schema.session_message_count, "0")}, 0) AS message_count,
               COALESCE({sql_expr(schema.session_tool_call_count, "0")}, 0) AS tool_call_count,
               COALESCE({sql_expr(schema.session_input_tokens, "0")}, 0) AS input_tokens,
               COALESCE({sql_expr(schema.session_output_tokens, "0")}, 0) AS output_tokens,
               COALESCE({sql_expr(schema.session_model, "'N/A'")}, 'N/A') AS model
        FROM sessions
        WHERE {sql_expr(schema.session_ended_at, "NULL")} IS NOT NULL
          AND {sql_expr(schema.session_started_at, "0")} < ?
          AND (
              {sql_expr(schema.session_started_at, "0")} > ?
              OR (
                  {sql_expr(schema.session_started_at, "0")} = ?
                  AND id > ?
              )
          )
        ORDER BY {sql_expr(schema.session_started_at, "0")} ASC, id ASC
    """
    if not all_sessions and batch_size:
        query += f" LIMIT {int(batch_size)}"
    cur = conn.execute(query, (cutoff_ts, watermark, watermark, cursor_session_id))
    return [dict(row) for row in cur.fetchall()]


def fetch_messages(conn, session_id, max_samples=10):
    schema = detect_state_schema(conn)
    cur = conn.execute(
        f"""
        SELECT {sql_expr(schema.message_role, "'assistant'", "role")},
               {sql_expr(schema.message_content, "''", "content")},
               {sql_expr(schema.message_timestamp, "0", "timestamp")},
               COALESCE({sql_expr(schema.message_tool_name, "''")}, '') AS tool_name
        FROM messages
        WHERE session_id = ?
        ORDER BY {sql_expr(schema.message_timestamp, "0")} ASC, id ASC
        """,
        (session_id,),
    )
    rows = cur.fetchall()
    total = len(rows)
    if total <= max_samples:
        indices = list(range(total))
    else:
        indices = list(range(3)) + list(range(total - (max_samples - 3), total))
    sampled = []
    for i in indices:
        if i < total:
            row = rows[i]
            sampled.append(
                {
                    "role": row["role"],
                    "content": str(row["content"] or "")[:500],
                    "timestamp": row["timestamp"],
                    "tool_name": row["tool_name"],
                    "index": i + 1,
                }
            )
    return sampled, total


def build_page(session, messages, msg_total):
    started = datetime.datetime.fromtimestamp(session["started_at"])
    ended = datetime.datetime.fromtimestamp(session["ended_at"]) if session.get("ended_at") else started
    duration_min = int((ended - started).total_seconds() / 60) if session.get("ended_at") else 0
    source = session.get("source", "unknown")
    title_str = session.get("title", "") or "Untitled session"
    user_msgs = [m["content"] for m in messages if m["role"] == "user" and m["content"]]
    summary = user_msgs[0][:200] if user_msgs else title_str
    page_title = f"{source.capitalize()} Session - {started.strftime('%Y-%m-%d %H:%M')}"
    timeline = []
    for message in messages:
        ts = datetime.datetime.fromtimestamp(message["timestamp"]).strftime("%H:%M")
        role_mark = "U" if message["role"] == "user" else "A"
        content_preview = (message["content"] or "")[:200]
        timeline.append(f"- **{ts}** [{role_mark}] {content_preview}")
    content = f"""---
title: "{page_title}"
tags: [session, {source}, archived]
---

## Session Info
- **Source**: {source}
- **Time**: {started.strftime('%Y-%m-%d %H:%M')} -> {ended.strftime('%H:%M')} ({duration_min} min)
- **Model**: {session.get('model', 'N/A')}
- **Messages**: {msg_total}
- **API Calls**: {session.get('tool_call_count', 0)}
- **Tokens**: {session.get('input_tokens', 0):,} in / {session.get('output_tokens', 0):,} out

## Session Summary
{summary}

## Key Timeline
""" + "\n".join(timeline)
    return {
        "slug": f"session-{session['id'][:20]}",
        "content": content,
        "tags": ["session", source, "archived"],
        "timeline": {
            "date": started.strftime("%Y-%m-%d"),
            "summary": f"{source} session - {msg_total} messages",
            "detail": summary[:500],
        },
        "session_id": session["id"],
    }


def publish_page(page):
    timeline = page.get("timeline") or {}
    timeline_entry = None
    if timeline.get("date") and timeline.get("summary"):
        timeline_entry = (str(timeline["date"]), str(timeline["summary"]))
    return ensure_gbrain_page(
        page["slug"],
        page["content"],
        page.get("tags") or [],
        timeline_entry=timeline_entry,
    )


def publish_sessions(conn, sessions, publisher=publish_page):
    published = []
    max_ts = 0.0
    for session in sessions:
        msgs, total = fetch_messages(conn, session["id"])
        page = build_page(session, msgs, total)
        if not publisher(page):
            return False, published, 0.0
        published.append(page)
        max_ts = max(max_ts, float(session["started_at"] or 0))
    return True, published, max_ts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    conn = connect_db()
    watermark, cursor_session_id = get_archive_cursor(conn)
    sys.stderr.write(f"Watermark: {datetime.datetime.fromtimestamp(watermark).isoformat() if watermark > 0 else 'never'}\n")
    sessions = fetch_sessions(
        conn,
        args.days,
        watermark,
        args.batch,
        args.all,
        cursor_session_id=cursor_session_id,
    )
    if not sessions:
        print(json.dumps({"status": "noop", "count": 0}))
        conn.close()
        return 0
    sys.stderr.write(f"Found {len(sessions)} sessions\n")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "count": len(sessions),
                    "sessions": [
                        {
                            "id": session["id"][:20],
                            "date": datetime.datetime.fromtimestamp(session["started_at"]).isoformat(),
                            "source": session["source"],
                            "msgs": session["message_count"],
                        }
                        for session in sessions
                    ],
                },
                ensure_ascii=False,
            )
        )
        conn.close()
        return 0
    ok, pages, max_ts = publish_sessions(conn, sessions)
    if not ok:
        print(
            json.dumps(
                {
                    "status": "error",
                    "count": len(pages),
                    "error": "gbrain publish failed; watermark was not advanced",
                },
                ensure_ascii=False,
            )
        )
        conn.close()
        return 1
    set_archive_cursor(conn, max_ts, sessions[-1]["id"])
    print(json.dumps({"status": "success", "count": len(pages), "pages": pages, "watermark": max_ts}, ensure_ascii=False))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
