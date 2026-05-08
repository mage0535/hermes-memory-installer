#!/usr/bin/env python3
"""Weekly index rebuild + expired data cleanup for Memory 2.0."""
import argparse, sqlite3, subprocess, time
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
HERMES = HOME / '.hermes'

def reindex_fts5(conn, table, dry_run=False):
    try:
        if not dry_run: conn.execute(f"INSERT INTO {table}_fts({table}) VALUES('rebuild')")
        conn.commit()
        return f"Reindexed {table}_fts"
    except: return f"{table}_fts N/A"

def cleanup_expired(conn, retention=90, dry_run=False):
    cutoff = (datetime.now() - timedelta(days=retention)).timestamp()
    cur = conn.execute("SELECT COUNT(*) FROM sessions WHERE start_time < ?", (cutoff,))
    n = cur.fetchone()[0]
    if not dry_run and n > 0:
        conn.execute("DELETE FROM sessions WHERE start_time < ?", (cutoff,))
        conn.commit()
    return f"Removed {n} expired sessions" if n > 0 else "None expired"

def check_orphans():
    r = subprocess.run('gbrain find-orphans --no-pseudo 2>/dev/null',
        shell=True, capture_output=True, text=True, timeout=30)
    if r.returncode != 0: return "gbrain N/A"
    lines = r.stdout.strip().split('\n')
    return f"{len(lines)} orphan pages" if r.stdout.strip() else "Clean"

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--retention', type=int, default=90)
    args = p.parse_args()
    
    start = time.time()
    print(f"[weekly_cleanup] v2.1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    for db, tables in [(HERMES/'state.db', ['archives','conversations']),
                        (HERMES/'pool.db', ['archives'])]:
        if db.exists():
            conn = sqlite3.connect(str(db))
            for t in tables: print(f"  {reindex_fts5(conn, t, args.dry_run)}")
            if 'state' in str(db): print(f"  {cleanup_expired(conn, args.retention, args.dry_run)}")
            conn.close()
    
    print(f"  Orphans: {check_orphans()}")
    print(f"[weekly_cleanup] Done in {time.time()-start:.1f}s")

