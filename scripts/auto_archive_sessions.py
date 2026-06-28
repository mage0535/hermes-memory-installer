#!/usr/bin/env python3
import sqlite3, os, sys, time
from pathlib import Path

AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home() / ".hermes")))
STATE_DB = AGENT_HOME / "state.db"
RETENTION_DAYS = int(os.environ.get("MEMORY_ARCHIVE_RETENTION_DAYS", "30"))
BATCH_SIZE = int(os.environ.get("MEMORY_ARCHIVE_BATCH_SIZE", "500"))
DRY_RUN = os.environ.get("MEMORY_ARCHIVE_DRY_RUN", "") == "1"

def main():
    if not STATE_DB.exists():
        print(f"state.db not found at {STATE_DB}")
        return 1
    conn = sqlite3.connect(str(STATE_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    cur = conn.execute("SELECT COUNT(*) FROM sessions WHERE started_at < unixepoch('now', ?)", (f'-{RETENTION_DAYS} days',))
    old_count = cur.fetchone()[0]
    print(f"Sessions >={RETENTION_DAYS}d old: {old_count}")
    if old_count == 0:
        print("Nothing to archive.")
        conn.close()
        return 0
    if DRY_RUN:
        print(f"[DRY RUN] Would archive {old_count} sessions")
        conn.close()
        return 0
    archived = 0
    errors = 0
    while True:
        cur = conn.execute("SELECT id FROM sessions WHERE started_at < unixepoch('now', ?) LIMIT ?", (f'-{RETENTION_DAYS} days', BATCH_SIZE))
        batch = [row[0] for row in cur.fetchall()]
        if not batch:
            break
        placeholders = ','.join(['?'] * len(batch))
        try:
            conn.execute(f"INSERT OR IGNORE INTO archives SELECT * FROM sessions WHERE id IN ({placeholders})", batch)
            conn.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", batch)
            conn.commit()
            archived += len(batch)
            print(f"  Archived batch: {len(batch)} sessions (total: {archived})")
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            conn.rollback()
            errors += 1
            if errors > 3:
                break
            time.sleep(1)
    if archived > 0:
        print(f"Total archived: {archived}. Running VACUUM...")
        conn.execute("PRAGMA optimize")
        conn.execute("VACUUM")
        print("Done.")
    conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
