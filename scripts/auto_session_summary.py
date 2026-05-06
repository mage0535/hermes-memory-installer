#!/usr/bin/env python3
"""Auto session summarizer for Memory 2.0

Generates LLM-powered summaries for finished sessions.
Runs every 12h, processes 2 sessions per batch with 45s timeout.
"""
import sys, os, subprocess, logging
from pathlib import Path

sys.path.insert(0, '/root/.hermes/hermes-agent')
from dotenv import dotenv_values
env_vals = dotenv_values('/root/.hermes/.env')
for k, v in env_vals.items():
    if k.endswith('_API_KEY') or k.endswith('_BASE_URL'):
        os.environ[k] = v
from hermes_state import SessionDB

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BATCH_LIMIT = 2
PER_SESSION_TIMEOUT = 45
WORKER_SCRIPT = '/root/.hermes/scripts/_summary_worker.py'

def get_candidates(db):
    import sqlite3
    conn = sqlite3.connect(str(db.state_db_path))
    cur = conn.execute("""
        SELECT id FROM sessions
        WHERE ended_at IS NOT NULL
          AND summary IS NULL
          AND id NOT LIKE 'cron_%%'
          AND (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) > 0
        ORDER BY ended_at DESC
        LIMIT ?
    """, (BATCH_LIMIT,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def main():
    db_path = Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes'))) / 'state.db'
    if not db_path.exists():
        logger.error(f"state.db not found at {db_path}")
        return
    db = SessionDB(db_path)
    candidates = get_candidates(db)
    logger.info(f"Found {len(candidates)} sessions to summarize")
    for sid in candidates:
        try:
            result = subprocess.run(
                [sys.executable, WORKER_SCRIPT, sid],
                capture_output=True, text=True, timeout=PER_SESSION_TIMEOUT
            )
            if result.returncode == 0:
                logger.info(f"Summarized {sid}")
            else:
                logger.warning(f"Failed {sid}: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout {sid}")

if __name__ == '__main__':
    main()
