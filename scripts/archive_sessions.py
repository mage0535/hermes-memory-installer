#!/usr/bin/env python3
"""Session -> gbrain Archiver for Memory 2.0 — 正式版

Reads finished sessions from Hermes state.db, creates structured gbrain pages
with timeline entries via MCP tools. Watermark-based incremental processing.

Usage:
  python3 archive_sessions.py [--days 7] [--dry-run] [--batch 15] [--all]
  python3 archive_sessions.py --reset-watermark  # 重置 watermark 重新归档

Requires:
  - Hermes state.db at ~/.hermes/state.db
  - gbrain MCP server running (part of Hermes Gateway)
"""
import sqlite3, json, sys, os, argparse, datetime, subprocess, time, re

STATE_DB = os.path.expanduser("~/.hermes/state.db")
MARKER_KEY = "gbrain_archive_watermark"
BATCH_SIZE = 15
DAYS_OLD = 7

def log(msg):
    print(f"[archiver] {msg}", flush=True)

def connect_db():
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_watermark(conn):
    cur = conn.execute("SELECT value FROM state_meta WHERE key = ?", (MARKER_KEY,))
    row = cur.fetchone()
    return float(row[0]) if row else 0

def set_watermark(conn, ts):
    conn.execute("INSERT OR REPLACE INTO state_meta (key, value) VALUES (?, ?)",
                 (MARKER_KEY, str(ts)))
    conn.commit()

def fetch_sessions(conn, older_than_days, watermark, batch_size, all_sessions):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=older_than_days)
    cutoff_ts = cutoff.timestamp()
    query = """SELECT s.id, s.source, s.user_id, s.model, s.title,
                      s.started_at, s.ended_at, s.end_reason,
                      s.message_count, s.tool_call_count, s.summary
               FROM sessions s
               WHERE s.ended_at IS NOT NULL
                 AND s.ended_at > ? AND s.ended_at < ?
                 AND s.id NOT LIKE 'cron_%%'
                 AND (SELECT COUNT(*) FROM messages WHERE session_id = s.id) > 1
               ORDER BY s.ended_at ASC"""
    if not all_sessions:
        query += " LIMIT ?"
        params = (watermark, cutoff_ts, batch_size)
    else:
        params = (watermark, cutoff_ts)
    cur = conn.execute(query, params)
    return cur.fetchall()

def get_session_messages(conn, session_id, max_msgs=30):
    """获取会话消息摘要"""
    cur = conn.execute(
        "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
        (session_id, max_msgs)
    )
    return cur.fetchall()

def make_slug(session_id):
    """生成 gbrain 页面 slug"""
    clean = re.sub(r'[^a-zA-Z0-9_-]', '-', session_id)[:24]
    return f"session-{clean}"

def build_page_content(session, messages):
    """构建 gbrain 页面 Markdown 内容"""
    title = session['title'] or f"Session {session['id'][:16]}"
    summary = session['summary'] or ''

    content = f"""---
title: "{title}"
type: session
tags:
  - session
  - archived
  - {session['source'] or 'unknown'}
date: {session['started_at'] or ''}
source_session_id: "{session['id']}"
---

# {title}

## 摘要

{summary or '*No summary generated*'}

## 元数据

| 字段 | 值 |
|------|-----|
| 来源 | {session['source'] or 'N/A'} |
| 模型 | {session['model'] or 'N/A'} |
| 开始 | {session['started_at'] or '?'} |
| 结束 | {session['ended_at'] or '?'} |
| 消息数 | {session['message_count'] or 0} |
| 工具调用 | {session['tool_call_count'] or 0} |
| 结束原因 | {session['end_reason'] or 'N/A'} |

## 对话片段

"""
    for msg in messages:
        role = msg['role']
        text = (msg['content'] or '')[:500]
        if role == 'user':
            content += f"> {text}\n\n"
        elif role == 'assistant':
            content += f"{text}\n\n"
    return content

def call_gbrain_mcp(action, params):
    """通过 gbrain CLI 调用 MCP 工具"""
    try:
        cmd = ["gbrain", "call", action, json.dumps(params)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        else:
            log(f"  ⚠️ gbrain call {action} failed: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        log(f"  ⚠️ gbrain call {action} timed out")
        return None
    except Exception as e:
        log(f"  ⚠️ gbrain call {action} error: {e}")
        return None

def archive_session(session, dry_run):
    """归档单个会话到 gbrain"""
    session_id = session['id']
    slug = make_slug(session_id)
    summary = session['summary'] or session['title'] or 'Untitled'
    log(f"  📦 {slug}: {summary[:60]}")

    if dry_run:
        return True

    # 获取消息
    conn = connect_db()
    messages = get_session_messages(conn, session_id)
    conn.close()

    # 构建页面内容
    content = build_page_content(session, messages)

    # Step 1: put_page — 创建/更新页面
    page_result = call_gbrain_mcp("put_page", {
        "slug": slug,
        "content": content
    })
    if page_result is None:
        log(f"  ❌ put_page 失败: {slug}")
        return False
    log(f"  ✅ put_page: {slug}")

    # Step 2: add_timeline_entry — 添加时间线条目
    timeline_result = call_gbrain_mcp("add_timeline_entry", {
        "slug": slug,
        "date": str(session['started_at'] or '')[:10],
        "summary": summary[:200],
        "detail": f"会话 {session_id[:16]} | 模型: {session['model']} | 消息: {session['message_count']}",
        "source": session['source'] or 'hermes'
    })
    if timeline_result is None:
        log(f"  ⚠️ add_timeline_entry 跳过（非致命）")
    else:
        log(f"  ✅ timeline 已添加")

    # Step 3: 添加标签
    call_gbrain_mcp("add_tag", {"slug": slug, "tag": "session"})
    if session['source']:
        call_gbrain_mcp("add_tag", {"slug": slug, "tag": session['source']})

    return True

def main():
    parser = argparse.ArgumentParser(description='Archive sessions to gbrain')
    parser.add_argument('--days', type=int, default=DAYS_OLD)
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--batch', type=int, default=BATCH_SIZE)
    parser.add_argument('--all', action='store_true', dest='all_sessions')
    parser.add_argument('--reset-watermark', action='store_true')
    args = parser.parse_args()

    if args.reset_watermark:
        conn = connect_db()
        set_watermark(conn, 0)
        conn.close()
        log("Watermark 已重置为 0，下次运行将重新归档所有会话")
        return

    conn = connect_db()
    watermark = get_watermark(conn)
    wm_time = datetime.datetime.fromtimestamp(watermark).isoformat() if watermark else 'start'
    log(f"Watermark: {wm_time}")

    sessions = fetch_sessions(conn, args.days, watermark, args.batch, args.all_sessions)
    log(f"发现 {len(sessions)} 个待归档会话")

    if not sessions:
        conn.close()
        return

    success_count = 0
    new_watermark = watermark

    for session in sessions:
        if archive_session(session, args.dry_run):
            success_count += 1
        ts = session['ended_at'] or 0
        if ts > new_watermark:
            new_watermark = ts

    if not args.dry_run and new_watermark > watermark:
        set_watermark(conn, new_watermark)
        log(f"Watermark 推进至 {datetime.datetime.fromtimestamp(new_watermark).isoformat()}")

    conn.close()
    tag = ' (dry-run)' if args.dry_run else ''
    log(f"完成: {success_count}/{len(sessions)} 成功{tag}")

if __name__ == '__main__':
    main()
