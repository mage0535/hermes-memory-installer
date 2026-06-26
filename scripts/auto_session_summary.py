#!/usr/bin/env python3
"""Generate lightweight summaries for completed sessions from state.db.

This implementation is agent-agnostic: it reads the shared session/message
schema directly from ``state.db`` and does not depend on Hermes private modules.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from state_db_schema import detect_state_schema, sql_expr

AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
STATE_DB = AGENT_HOME / "state.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_LIMIT = 2
MIN_MESSAGES = 3
MIN_TOKENS = 100
MAX_SUMMARY_LEN = 600
TRIVIAL_PATTERNS = {"ok", "thanks", "okay", "received", "好的", "谢谢", "知道了", "明白"}


def should_summarize(message_count: int, total_tokens: int, title: str = "") -> bool:
    if message_count < MIN_MESSAGES:
        return False
    if total_tokens < MIN_TOKENS:
        return False
    if title and title.strip().lower() in TRIVIAL_PATTERNS:
        return False
    return True


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_candidate_sessions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    schema = detect_state_schema(conn)
    return conn.execute(
        f"""
        SELECT s.id,
               COALESCE({sql_expr(schema.session_message_count, "0", table_alias="s.")}, 0) AS message_count,
               COALESCE({sql_expr(schema.session_input_tokens, "0", table_alias="s.")}, 0) + COALESCE({sql_expr(schema.session_output_tokens, "0", table_alias="s.")}, 0) AS total_tokens,
               COALESCE({sql_expr(schema.session_title, "''", table_alias="s.")}, '') AS title
        FROM sessions s
        WHERE {sql_expr(schema.session_ended_at, "NULL", table_alias="s.")} IS NOT NULL
          AND s.summary IS NULL
          AND s.id NOT LIKE 'cron_%'
          AND COALESCE({sql_expr(schema.session_message_count, "0", table_alias="s.")}, 0) >= ?
          AND (COALESCE({sql_expr(schema.session_input_tokens, "0", table_alias="s.")}, 0) + COALESCE({sql_expr(schema.session_output_tokens, "0", table_alias="s.")}, 0)) >= ?
        ORDER BY {sql_expr(schema.session_ended_at, "0", table_alias="s.")} DESC
        LIMIT ?
        """,
        (MIN_MESSAGES, MIN_TOKENS, BATCH_LIMIT),
    ).fetchall()


def fetch_messages(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    schema = detect_state_schema(conn)
    return conn.execute(
        f"""
        SELECT {sql_expr(schema.message_role, "'assistant'", "role")},
               {sql_expr(schema.message_content, "''", "content")},
               {sql_expr(schema.message_timestamp, "0", "timestamp")}
        FROM messages
        WHERE session_id = ?
          AND {sql_expr(schema.message_content, "NULL")} IS NOT NULL
          AND trim({sql_expr(schema.message_content, "''")}) <> ''
        ORDER BY {sql_expr(schema.message_timestamp, "0")} ASC, id ASC
        """,
        (session_id,),
    ).fetchall()


def build_summary(title: str, messages: list[sqlite3.Row]) -> str:
    user_messages = [str(row["content"]).strip() for row in messages if row["role"] == "user"]
    assistant_messages = [str(row["content"]).strip() for row in messages if row["role"] == "assistant"]

    opener = user_messages[0][:180] if user_messages else (title.strip()[:180] if title else "Completed session")
    closer = assistant_messages[-1][:220] if assistant_messages else ""
    summary = f"Session recap: {opener}"
    if closer:
        summary += f" | Latest assistant response: {closer}"
    return summary[:MAX_SUMMARY_LEN]


def update_summary(conn: sqlite3.Connection, session_id: str, summary: str) -> None:
    conn.execute("UPDATE sessions SET summary = ? WHERE id = ?", (summary, session_id))


def main() -> int:
    if not STATE_DB.exists():
        logger.warning("state.db not found: %s", STATE_DB)
        print("[SILENT]")
        return 0

    conn = connect_db()
    try:
        candidates = fetch_candidate_sessions(conn)
        written = 0
        for row in candidates:
            if not should_summarize(int(row["message_count"] or 0), int(row["total_tokens"] or 0), str(row["title"] or "")):
                continue
            messages = fetch_messages(conn, str(row["id"]))
            summary = build_summary(str(row["title"] or ""), messages)
            if not summary.strip():
                continue
            update_summary(conn, str(row["id"]), summary)
            written += 1
        conn.commit()
        if written == 0:
            print("[SILENT]")
        else:
            print(f"Updated summaries: {written}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
