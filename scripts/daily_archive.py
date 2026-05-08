#!/usr/bin/env python3
"""Daily session archival + DB backup for Memory 2.0.
Usage: python3 scripts/daily_archive.py [--days 7] [--dry-run] [--backup-only]
"""
import argparse, json, os, shutil, sqlite3, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
HERMES = HOME / '.hermes'
STATE_DB = HERMES / 'state.db'

def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return "FAILED", -1

def backup_dbs(dry_run=False):
    backups = []
    for db in ['state.db', 'pool.db', 'semantics.db']:
        src = HERMES / db
        if not src.exists(): continue
        dest = HERMES / 'backups' / f"{db}.{datetime.now().strftime('%Y%m%d')}"
        if dry_run: print(f"[dry-run] Would backup {db}")
        else:
            HERMES.joinpath('backups').mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            backups.append(str(dest))
    # Rotate >14 days
    if not dry_run:
        cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y%m%d')
        for f in (HERMES / 'backups').glob('*.db.*'):
            parts = f.name.rsplit('.', 1)
            if len(parts) > 1 and parts[1].isdigit() and parts[1] < cutoff:
                f.unlink()
    return backups

def archive_sessions(days=1, batch=15, dry_run=False):
    if not STATE_DB.exists(): return 0
    conn = sqlite3.connect(str(STATE_DB))
    since = (datetime.now() - timedelta(days=days)).timestamp()
    cur = conn.execute("SELECT id, start_time, title, summary FROM sessions WHERE start_time > ? AND id NOT LIKE 'cron_%' ORDER BY start_time ASC LIMIT ?", (since, batch))
    sessions = cur.fetchall()
    conn.close()
    if not sessions: return 0
    
    count = 0
    for sid, ts, title, summary in sessions:
        title = title or f"Session {sid[:12]}"
        summary = summary or "(no summary)"
        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        if dry_run:
            print(f"[dry-run] Would archive: {sid[:20]}... ({title[:60]})")
            count += 1
            continue
        r = run(f'echo "---\ntype: session\ntitle: {title[:100]}\nsummary: {summary[:200]}\ndate: {date_str}\nsession_id: {sid}\n---\n\n# {title}\n\n{summary[:500]}" | gbrain put_page {sid.replace("_","-")[:64]} --title "{title[:100]}" --content - 2>/dev/null', timeout=30)
        if r[1] == 0:
            print(f"✅ {sid[:20]}... archived")
            count += 1
        else:
            print(f"⚠️ {sid[:20]}... skipped")
    return count

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--days', type=int, default=1)
    p.add_argument('--batch', type=int, default=15)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--backup-only', action='store_true')
    args = p.parse_args()
    
    start = time.time()
    print(f"[daily_archive] v2.1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"[daily_archive] {'DRY-RUN' if args.dry_run else 'LIVE'}, {args.days}d lookback")
    
    backups = backup_dbs(args.dry_run)
    print(f"[backup] {len(backups)} DBs backed up")
    
    if not args.backup_only:
        n = archive_sessions(args.days, args.batch, args.dry_run)
        print(f"[archive] {n} sessions archived")
    
    print(f"[daily_archive] Done in {time.time()-start:.1f}s")
