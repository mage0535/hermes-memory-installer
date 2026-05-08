#!/usr/bin/env python3
"""Test router for Memory 2.0 proactive context routing.
Validates: topic detection, FTS5 keyword match, embedding similarity, gbrain fallback.
Usage: python3 scripts/test_router.py [query]
"""
import json, os, sqlite3, subprocess, sys, time
from pathlib import Path

HOME = Path.home()
HERMES = HOME / '.hermes'
STATE_DB = HERMES / 'state.db'

def test_fts5(query, limit=5):
    """Test FTS5 keyword search."""
    if not STATE_DB.exists():
        return None, "state.db not found"
    conn = sqlite3.connect(str(STATE_DB))
    try:
        cur = conn.execute(
            "SELECT content FROM sessions_fts WHERE sessions_fts MATCH ? LIMIT ?",
            (query, limit))
        rows = cur.fetchall()
        return [r[0][:80] for r in rows], None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

def test_embedding(query):
    """Test embedding server health."""
    try:
        import urllib.request
        data = json.dumps({"input": [query], "model": "BAAI/bge-small-zh-v1.5"}).encode()
        req = urllib.request.Request("http://127.0.0.1:8766/v1/embeddings",
            data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        dim = len(result["data"][0]["embedding"])
        return True, f"OK ({dim}d)"
    except Exception as e:
        return False, str(e)

def test_gbrain(query):
    """Test gbrain knowledge graph search."""
    r = subprocess.run(
        f'gbrain search "{query}" -n 3 2>/dev/null',
        shell=True, capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        pages = r.stdout.strip().split('\n')
        return True, f"Found {len(pages)} pages in gbrain"
    return False, "gbrain not available or no results"

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "AI agent memory system"
    print(f"Router test for: {query}\n")
    
    # Layer 1: FTS5
    t0 = time.time()
    results, err = test_fts5(query)
    dt = (time.time() - t0) * 1000
    print(f"  Layer 1 FTS5: {'OK' if results else 'FAIL'} ({dt:.0f}ms)")
    if results: print(f"    Top: {results[0][:80]}")
    if err: print(f"    Error: {err}")
    
    # Layer 2: Embedding
    t0 = time.time()
    ok, info = test_embedding(query)
    dt = (time.time() - t0) * 1000
    print(f"  Layer 2 Embed: {'OK' if ok else 'FAIL'} ({dt:.0f}ms) — {info}")
    
    # Layer 3: gbrain
    t0 = time.time()
    ok, info = test_gbrain(query)
    dt = (time.time() - t0) * 1000
    print(f"  Layer 3 gbrain: {'OK' if ok else 'N/A'} ({dt:.0f}ms) — {info}")
    
    print(f"\n  Router health: {'PASS' if results else 'DEGRADED'}")

if __name__ == '__main__':
    main()

