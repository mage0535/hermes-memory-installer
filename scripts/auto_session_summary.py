#!/usr/bin/env python3
"""Auto session summarizer for Memory 2.0

Generates LLM-powered summaries for finished sessions.
Runs every 12h, processes 2 sessions per batch with 45s timeout.

Uses _summary_worker.py as a subprocess per session to isolate failures
and avoid loading Hermes Agent internals.

Usage:
  python3 auto_session_summary.py [--limit 2] [--timeout 45] [--dry-run]
"""
import argparse
import datetime
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
STATE_DB = HERMES_HOME / "state.db"
WORKER_SCRIPT = HERMES_HOME / "scripts" / "_summary_worker.py"
SUMMARY_WATERMARK_KEY = "summary_last_run"


def get_candidates(conn, limit):
    """Find sessions that need summaries."""
    cur = conn.execute(
        """
        SELECT id FROM sessions
        WHERE ended_at IS NOT NULL
          AND (summary IS NULL OR summary = '')
          AND id NOT LIKE 'cron_%%'
          AND (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) > 1
        ORDER BY ended_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    return [r[0] for r in rows]


def update_watermark(conn):
    """Record when summarization last ran."""
    now = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO state_meta (key, value) VALUES (?, ?)",
        (SUMMARY_WATERMARK_KEY, now),
    )
    conn.commit()


def ensure_state_meta_table(conn):
    """Ensure state_meta exists for watermark."""
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS state_meta ("
            "key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"Could not create state_meta: {e}")


def main():
    parser = argparse.ArgumentParser(description="Auto-summarize finished sessions")
    parser.add_argument("--limit", type=int, default=2, help="Max sessions per run")
    parser.add_argument("--timeout", type=int, default=45, help="Seconds per session")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't save")
    args = parser.parse_args()

    # Check worker exists
    if not WORKER_SCRIPT.exists():
        logger.error(f"Worker script not found: {WORKER_SCRIPT}")
        logger.error("Run: cp scripts/_summary_worker.py ~/.hermes/scripts/")
        sys.exit(1)

    if not STATE_DB.exists():
        logger.error(f"state.db not found at {STATE_DB}")
        sys.exit(1)

    conn = sqlite3.connect(str(STATE_DB))
    ensure_state_meta_table(conn)

    candidates = get_candidates(conn, args.limit)
    if not candidates:
        logger.info("No sessions to summarize")
        conn.close()
        update_watermark(conn)
        return

    logger.info(f"Found {len(candidates)} session(s) to summarize")

    success = 0
    failed = 0
    dry_flag = " --dry-run" if args.dry_run else ""

    for sid in candidates:
        dry_flag = " --dry-run" if args.dry_run else ""
        cmd = [
            sys.executable,
            str(WORKER_SCRIPT),
            sid,
        ]
        if args.dry_run:
            cmd.append("--dry-run")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
            if result.returncode == 0:
                summary_preview = result.stdout.strip()[:100]
                logger.info(f"Summarized {sid}: {summary_preview}...")
                success += 1
            else:
                err = result.stderr.strip()[:200]
                logger.warning(f"Failed {sid}: {err}")
                failed += 1

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout {sid} after {args.timeout}s")
            failed += 1

    conn.close()
    update_watermark(sqlite3.connect(str(STATE_DB)))

    logger.info(f"Summary: {success} succeeded, {failed} failed of {len(candidates)}")


if __name__ == "__main__":
    main()
