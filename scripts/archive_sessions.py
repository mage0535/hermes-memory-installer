#!/usr/bin/env python3
"""
Hermes Session -> gbrain Archiver

Reads finished sessions from state.db, outputs structured JSON for
gbrain ingestion via MCP tools. Designed for both one-time bulk archive
and daily incremental runs.

Usage:
  python3 archive_sessions.py [--days 7] [--dry-run] [--batch 20]
    --days N    : archive sessions older than N days (default: 7)
    --dry-run   : show what would be archived, don't mark done
    --batch N   : max sessions per run (default: 20)
    --all       : process ALL eligible sessions
"""

import sqlite3, json, sys, os, argparse, datetime

STATE_DB = os.path.expanduser("~/.hermes/state.db")
MARKER_KEY = "gbrain_archive_watermark"

def connect_db():
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_watermark(conn):
    cur = conn.execute("SELECT value FROM state_meta WHERE key = ?", (MARKER_KEY,))
    row = cur.fetchone()
    return float(row[0]) if row else 0

def set_watermark(conn, ts):
    conn.execute("INSERT OR REPLACE INTO state_meta (key, value) VALUES (?, ?)", (MARKER_KEY, str(ts)))
    conn.commit()

def fetch_sessions(conn, older_than_days, watermark, batch_size, all_sessions):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=older_than_days)
    cutoff_ts = cutoff.timestamp()
    query = """SELECT id, source, user_id, model, title, started_at, ended_at,
                      end_reason, message_count, tool_call_count,
                      input_tokens, output_tokens
               FROM sessions
               WHERE ended_at IS NOT NULL AND started_at < ? AND started_at > ?
               ORDER BY started_at ASC"""
    if not all_sessions and batch_size:
        query += f" LIMIT {batch_size}"
    cur = conn.execute(query, (cutoff_ts, watermark))
    return [dict(row) for row in cur.fetchall()]

def fetch_messages(conn, session_id, max_samples=10):
    cur = conn.execute(
        "SELECT role, content, timestamp, tool_name FROM messages WHERE session_id = ? ORDER BY timestamp",
        (session_id,))
    rows = cur.fetchall()
    total = len(rows)
    if total <= max_samples:
        indices = list(range(total))
    else:
        indices = list(range(3)) + list(range(total - (max_samples - 3), total))
    sampled = []
    for i in indices:
        if i < total:
            r = rows[i]
            content = (r[1] or "")[:500]
            sampled.append({"role": r[0], "content": content, "timestamp": r[2], "tool_name": r[3], "index": i + 1})
    return sampled, total

def build_page(session, messages, msg_total):
    started = datetime.datetime.fromtimestamp(session["started_at"])
    ended = datetime.datetime.fromtimestamp(session["ended_at"]) if session.get("ended_at") else started
    duration_min = int((ended - started).total_seconds() / 60) if session.get("ended_at") else 0
    source = session.get("source", "unknown")
    title_str = session.get("title", "") or "无主题"
    user_msgs = [m["content"] for m in messages if m["role"] == "user" and m["content"]]
    summary = user_msgs[0][:200] if user_msgs else title_str
    page_title = f"{source.capitalize()} 会话 - {started.strftime('%Y-%m-%d %H:%M')}"
    timeline = []
    for m in messages:
        ts = datetime.datetime.fromtimestamp(m["timestamp"]).strftime("%H:%M")
        role_mark = "U" if m["role"] == "user" else "A"
        content_preview = (m["content"] or "")[:200]
        timeline.append(f"- **{ts}** [{role_mark}] {content_preview}")
    content = f"""---
title: "{page_title}"
tags: [session, {source}, archived]
---

## 会话信息
- **来源**: {source}
- **时间**: {started.strftime('%Y-%m-%d %H:%M')} -> {ended.strftime('%H:%M')} ({duration_min}分钟)
- **模型**: {session.get('model', 'N/A')}
- **消息数**: {msg_total}
- **API调用**: {session.get('tool_call_count', 0)}
- **Tokens**: {session.get('input_tokens', 0):,} in / {session.get('output_tokens', 0):,} out

## 会话摘要
{summary}

## 关键对话节点
""" + "\n".join(timeline)
    return {
        "slug": f"session-{session['id'][:20]}",
        "content": content,
        "tags": ["session", source, "archived"],
        "timeline": {
            "date": started.strftime("%Y-%m-%d"),
            "summary": f"{source}会话 - {msg_total}条消息",
            "detail": summary[:500]
        },
        "session_id": session["id"]
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch", type=int, default=20)
    p.add_argument("--all", action="store_true")
    args = p.parse_args()
    conn = connect_db()
    watermark = get_watermark(conn)
    sys.stderr.write(f"Watermark: {datetime.datetime.fromtimestamp(watermark).isoformat() if watermark > 0 else 'never'}\n")
    sessions = fetch_sessions(conn, args.days, watermark, args.batch, args.all)
    if not sessions:
        print(json.dumps({"status": "noop", "count": 0}))
        return
    sys.stderr.write(f"Found {len(sessions)} sessions\n")
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "count": len(sessions),
            "sessions": [{"id": s["id"][:20], "date": datetime.datetime.fromtimestamp(s["started_at"]).isoformat(),
                          "source": s["source"], "msgs": s["message_count"]} for s in sessions]},
            ensure_ascii=False))
        return
    pages = []
    max_ts = watermark
    for session in sessions:
        msgs, total = fetch_messages(conn, session["id"])
        page = build_page(session, msgs, total)
        pages.append(page)
        if session["started_at"] > max_ts:
            max_ts = session["started_at"]
    set_watermark(conn, max_ts)
    print(json.dumps({"status": "success", "count": len(pages), "pages": pages, "watermark": max_ts}, ensure_ascii=False))
    conn.close()

if __name__ == "__main__":
    main()
