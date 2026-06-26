#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import sqlite3


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.OperationalError:
        return set()


def first_present(columns: set[str], *candidates: str, default: str = "") -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return default


def validate_state_schema(conn: sqlite3.Connection) -> None:
    session_columns = table_columns(conn, "sessions")
    message_columns = table_columns(conn, "messages")
    errors = []
    if not session_columns:
        errors.append("missing sessions table")
    elif "id" not in session_columns:
        errors.append("sessions table requires id")
    if not message_columns:
        errors.append("missing messages table")
    else:
        if "id" not in message_columns:
            errors.append("messages table requires id")
        if "session_id" not in message_columns:
            errors.append("messages table requires session_id")
        if not first_present(message_columns, "content", "text", "body"):
            errors.append("messages table requires content, text, or body")
        if "role" not in message_columns:
            errors.append("messages table requires role")
    if errors:
        raise ValueError("incompatible agent state database: " + "; ".join(errors))


@dataclass(frozen=True)
class StateSchema:
    session_source: str
    session_ended_at: str
    session_started_at: str
    session_summary: str
    session_title: str
    session_message_count: str
    session_input_tokens: str
    session_output_tokens: str
    session_model: str
    session_tool_call_count: str
    session_parent_id: str
    session_end_reason: str
    message_content: str
    message_timestamp: str
    message_role: str
    message_tool_name: str


def sql_expr(column: str, fallback_sql: str, alias: str | None = None, table_alias: str = "") -> str:
    source = f"{table_alias}{column}" if column else fallback_sql
    if alias:
        return f"{source} AS {alias}"
    return source


def detect_state_schema(conn: sqlite3.Connection) -> StateSchema:
    validate_state_schema(conn)
    session_columns = table_columns(conn, "sessions")
    message_columns = table_columns(conn, "messages")
    return StateSchema(
        session_source=first_present(session_columns, "source", "origin"),
        session_ended_at=first_present(session_columns, "ended_at", "updated_at", "finished_at"),
        session_started_at=first_present(session_columns, "started_at", "created_at"),
        session_summary=first_present(session_columns, "summary"),
        session_title=first_present(session_columns, "title", "name"),
        session_message_count=first_present(session_columns, "message_count", "messages_count"),
        session_input_tokens=first_present(session_columns, "input_tokens", "prompt_tokens"),
        session_output_tokens=first_present(session_columns, "output_tokens", "completion_tokens"),
        session_model=first_present(session_columns, "model"),
        session_tool_call_count=first_present(session_columns, "tool_call_count"),
        session_parent_id=first_present(session_columns, "parent_session_id"),
        session_end_reason=first_present(session_columns, "end_reason"),
        message_content=first_present(message_columns, "content", "text", "body", default="content"),
        message_timestamp=first_present(message_columns, "timestamp", "created_at", "time"),
        message_role=first_present(message_columns, "role", default="role"),
        message_tool_name=first_present(message_columns, "tool_name"),
    )
