#!/usr/bin/env python3
"""Unified embedding sync for Memory 2.0

Bidirectional incremental sync between semantics.db and state.db message_embeddings.
Uses BAAI/bge-small-zh-v1.5 (512-dim) — single model for both Chinese and English.
Production best practice: deploy via scripts/embedding_server.py for persistent service.
"""
import argparse, sqlite3, sys, os
from pathlib import Path

STATE_DB = Path.home() / '.hermes' / 'state.db'
SEMANTICS_DB = Path.home() / '.hermes' / 'semantics.db'
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DIM = 512

def get_embedder():
    """Lazy-load embedding model (supports both EN and CN)."""
    try:
        from sentence_transformers import SentenceTransformer
        print(f"[embed] Loading {EMBEDDING_MODEL} (512d, multilingual, ~33MB)...", flush=True)
        return SentenceTransformer(EMBEDDING_MODEL)
    except ImportError:
        print("[embed] sentence-transformers not installed. Install: pip install sentence-transformers")
        print("[embed] Attempting remote embedding server at localhost:8766...")
        return None

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

def embed_texts(texts, via_api=False):
    """Get embeddings—local model or remote server."""
    if via_api:
        import urllib.request, json
        data = json.dumps({"input": texts, "model": EMBEDDING_MODEL}).encode()
        req = urllib.request.Request("http://127.0.0.1:8766/v1/embeddings",
            data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return [d["embedding"] for d in resp["data"]]
    else:
        model = get_embedder()
        if model is None:
            return embed_texts(texts, via_api=True)
        return model.encode(texts, normalize_embeddings=True).tolist()

def sync_semantics_to_state(batch_size=50):
    """Sync semantics.db embeddings → state.db (incremental)."""
    if not SEMANTICS_DB.exists():
        print("[sync] semantics.db not found, skipping")
        return 0
    conn_sem = sqlite3.connect(str(SEMANTICS_DB))
    conn_state = sqlite3.connect(str(STATE_DB))
    
    # Check what needs syncing
    cur_sem = conn_sem.execute("SELECT message_id, embedding FROM message_embeddings")
    existing = set()
    try:
        cur_existing = conn_state.execute("SELECT message_id FROM message_embeddings")
        existing = {row[0] for row in cur_existing}
    except sqlite3.OperationalError:
        conn_state.execute("CREATE TABLE IF NOT EXISTS message_embeddings (message_id TEXT PRIMARY KEY, embedding BLOB)")
        conn_state.commit()
    
    to_sync = [(mid, emb) for mid, emb in cur_sem if mid not in existing]
    if not to_sync:
        print("[sync] Already in sync")
        return 0
    
    for mid, emb in to_sync:
        conn_state.execute("INSERT OR REPLACE INTO message_embeddings (message_id, embedding) VALUES (?, ?)",
                          (mid, emb))
    conn_state.commit()
    conn_sem.close()
    conn_state.close()
    print(f"[sync] Synced {len(to_sync)} embeddings")
    return len(to_sync)

def main():
    parser = argparse.ArgumentParser(description='Multi-language embedding sync (BAAI/bge-small-zh-v1.5)')
    parser.add_argument('--stats', action='store_true', help='Show embedding stats')
    parser.add_argument('--sync', action='store_true', help='Sync semantics → state')
    parser.add_argument('--batch-size', type=int, default=50)
    parser.add_argument('--via-api', action='store_true', help='Use remote embedding server (port 8766)')
    args = parser.parse_args()
    
    if args.stats:
        stats = get_stats()
        print(f"[stats] state.db: {stats.get('state', '?')} embeddings")
        print(f"[stats] semantics.db: {stats.get('semantics', '?')} embeddings")
        return
    
    if args.sync:
        sync_semantics_to_state(batch_size=args.batch_size)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
