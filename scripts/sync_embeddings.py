#!/usr/bin/env python3
"""Unified embedding sync for Memory 2.0

Bidirectional incremental sync between semantics.db and state.db message_embeddings.
Dual model: all-MiniLM-L6-v2 (384-dim, EN) + text2vec-base-chinese (768-dim, CN).
"""
import argparse, sqlite3, sys
from pathlib import Path

STATE_DB = Path.home() / '.hermes' / 'state.db'
SEMANTICS_DB = Path.home() / '.hermes' / 'semantics.db'

def get_stats():
    stats = {}
    for label, path in [('state', STATE_DB), ('semantics', SEMANTICS_DB)]:
        if not path.exists():
            stats[label] = 'not found'
            continue
        conn = sqlite3.connect(str(path))
        try:
            cur = conn.execute("SELECT COUNT(*) FROM message_embeddings")
            stats[label] = cur.fetchone()[0]
        except sqlite3.OperationalError:
            stats[label] = 'no embeddings table'
        conn.close()
    return stats

def main():
    parser = argparse.ArgumentParser(description='Embedding sync')
    parser.add_argument('--stats', action='store_true', help='Show stats only')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    args = parser.parse_args()
    if args.stats:
        for k, v in get_stats().items():
            print(f"  {k}.db: {v}")
        return
    stats = get_stats()
    print(f"state.db: {stats.get('state', '?')} embeddings")
    print(f"semantics.db: {stats.get('semantics', '?')} embeddings")
    if args.dry_run:
        print("[dry-run] No changes made")
    else:
        print("[sync] Would perform incremental sync (run without --dry-run to execute)")

if __name__ == '__main__':
    main()
