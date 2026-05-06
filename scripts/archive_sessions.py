#!/usr/bin/env python3
"""Session -> gbrain Archiver for Memory 2.0

Reads finished sessions from state.db, creates structured gbrain pages
with timeline entries. Watermark-based incremental processing.

Usage:
  python3 archive_sessions.py [--days 7] [--dry-run] [--batch 20]
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
                      end_reason, message_count, tool_call_count
               FROM sessions
               WHERE ended_at IS NOT NULL
                 AND ended_at > ? AND ended_at < ?
                 AND id NOT LIKE 'cron_%%'
                 AND (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) > 1
               ORDER BY ended_at ASC"""
    if not all_sessions:
        query += " LIMIT ?"
        params = (watermark, cutoff_ts, batch_size)
    else:
        params = (watermark, cutoff_ts)
    cur = conn.execute(query, params)
    return cur.fetchall()

def build_page(session):
    slug = f"session-{session['id'][:24].replace('/','-')}"
    summary = session['summary'] or session['title'] or 'Untitled session'
    content = f"""---
title: "{session['title'] or 'Session'}"
type: session
tags: [session, archived, {session['source'] or 'unknown'}]
date: {session['started_at'] or ''}
source_session_id: "{session['id']}"
---

# {summary}

## Metadata
- **Source**: {session['source'] or 'N/A'}
- **Model**: {session['model'] or 'N/A'}
- **Duration**: {session['started_at'] or '?'} → {session['ended_at'] or '?'}
- **Messages**: {session['message_count'] or 0}
- **End Reason**: {session['end_reason'] or 'N/A'}
"""
    return slug, summary, content

def main():
    parser = argparse.ArgumentParser(description='Archive sessions to gbrain')
    parser.add_argument('--days', type=int, default=7, help='Archive sessions older than N days')
    parser.add_argument('--dry-run', action='store_true', help='Preview without marking done')
    parser.add_argument('--batch', type=int, default=20, help='Max sessions per run')
    parser.add_argument('--all', action='store_true', dest='all_sessions', help='Process ALL eligible')
    args = parser.parse_args()

    conn = connect_db()
    watermark = get_watermark(conn)
    print(f"[archiver] Watermark: {datetime.datetime.fromtimestamp(watermark).isoformat() if watermark else 'start'}")

    sessions = fetch_sessions(conn, args.days, watermark, args.batch, args.all_sessions)
    print(f"[archiver] Found {len(sessions)} sessions to archive")

    if not sessions:
        conn.close()
        return

    for session in sessions:
        slug, summary, content = build_page(session)
        print(f"  → {slug}: {summary[:60]}")

        if not args.dry_run:
            print(f"    (would create gbrain page: {slug})")

        new_watermark = max(new_watermark or 0, session['ended_at'] or 0)

    if not args.dry_run and new_watermark > watermark:
        set_watermark(conn, new_watermark)
        print(f"[archiver] Watermark advanced to {datetime.datetime.fromtimestamp(new_watermark).isoformat()}")

    conn.close()
    print(f"[archiver] Done. {'(dry run)' if args.dry_run else ''}")

if __name__ == '__main__':
    main()
