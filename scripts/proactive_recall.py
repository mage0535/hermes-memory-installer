#!/usr/bin/env python3
"""Proactive semantic recall for Memory 2.0

Given a query (user message), performs multi-layer recall:
  Layer 1: FTS5 full-text search (state.db, <10ms)
  Layer 2: Embedding similarity search (semantics.db or local model)
  Layer 3: gbrain knowledge graph (fallback)

Returns structured JSON with top relevant memories for context injection.

Usage:
  python3 proactive_recall.py "remember that thing about docker"
  python3 proactive_recall.py --top 5 --query "how did we fix the auth bug"
  python3 proactive_recall.py --ftsgrep "nifty pre-market"  # FTS5 only
"""
import argparse
import json
import math
import os
import sqlite3
import sys
import time
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
STATE_DB = HERMES_HOME / "state.db"
SEMANTICS_DB = HERMES_HOME / "semantics.db"


def fts5_search(query, top=5):
    """Layer 1: FTS5 / LIKE search across state.db sessions."""
    results = []
    if not STATE_DB.exists():
        return results

    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    try:
        try:
            cur = conn.execute(
                "SELECT id, title, summary, source, ended_at FROM sessions_fts "
                "WHERE sessions_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, top),
            )
            for row in cur:
                results.append({
                    "session_id": row["id"], "title": row["title"],
                    "summary": (row["summary"] or "")[:200],
                    "source": row["source"], "ended_at": row["ended_at"],
                    "score": "fts_rank",
                })
        except sqlite3.OperationalError:
            pass

        if not results:
            cur = conn.execute(
                "SELECT id, title, summary, source, ended_at FROM sessions "
                "WHERE title LIKE ? OR summary LIKE ? "
                "ORDER BY ended_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", top),
            )
            for row in cur:
                results.append({
                    "session_id": row["id"], "title": row["title"],
                    "summary": (row["summary"] or "")[:200],
                    "source": row["source"], "ended_at": row["ended_at"],
                    "score": "like_match",
                })
    except Exception as e:
        print(f"[recall] FTS5 error: {e}", file=sys.stderr)
    conn.close()
    return results


def embedding_search(query, top=5):
    """Layer 2: Embedding similarity search."""
    if not SEMANTICS_DB.exists():
        return []
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        emb_model = SentenceTransformer(model_name)
        q_emb = emb_model.encode([query], normalize_embeddings=True)[0].tolist()
    except (ImportError, Exception) as e:
        return []

    conn = sqlite3.connect(str(SEMANTICS_DB))
    scored = []
    try:
        cur = conn.execute(
            "SELECT message_id, embedding FROM message_embeddings WHERE embedding IS NOT NULL"
        )
        for row in cur:
            try:
                n_vec = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                if len(n_vec) != len(q_emb):
                    continue
                dot = sum(a * b for a, b in zip(q_emb, n_vec))
                nq = math.sqrt(sum(a * a for a in q_emb))
                nn = math.sqrt(sum(a * a for a in n_vec))
                sim = dot / (nq * nn) if nq and nn else 0
                if sim > 0.15:
                    scored.append((row[0], round(sim, 4)))
            except Exception:
                continue
    except sqlite3.OperationalError:
        pass
    conn.close()

    scored.sort(key=lambda x: x[1], reverse=True)
    return [{"message_id": mid, "similarity": sim} for mid, sim in scored[:top]]


def gbrain_search(query, top=3):
    """Layer 3: gbrain knowledge graph search (fallback)."""
    import subprocess
    try:
        result = subprocess.run(
            ["gbrain", "query", query], capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            try:
                return [{"source": "gbrain", "data": json.loads(result.stdout)}]
            except json.JSONDecodeError:
                return [{"source": "gbrain", "raw": result.stdout[:500]}]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


def apply_time_decay(similarity, ended_at, half_life_days=30):
    """Apply exponential time decay."""
    if not ended_at:
        return similarity
    try:
        from datetime import datetime
        if isinstance(ended_at, str):
            try:
                ended = datetime.fromisoformat(ended_at)
            except ValueError:
                return similarity
        elif isinstance(ended_at, (int, float)):
            ended = datetime.fromtimestamp(ended_at)
        else:
            return similarity
        age_days = (datetime.now() - ended).total_seconds() / 86400
        decay = math.exp(-age_days / half_life_days)
        return round(similarity * decay, 4)
    except Exception:
        return similarity


def main():
    parser = argparse.ArgumentParser(description="Proactive semantic recall for Memory 2.0")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--top", "-n", type=int, default=5, help="Max results per layer")
    parser.add_argument("--ftsgrep", help="FTS5/LIKE only, skip embeddings")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    query = args.ftsgrep or args.query
    if not query:
        parser.print_help()
        sys.exit(0)

    out = {"query": query, "layers": []}
    start = time.time()

    # Layer 1: FTS5
    l1 = fts5_search(query, top=args.top)
    if l1:
        out["layers"].append({"layer": 1, "label": "FTS5/LIKE", "count": len(l1), "results": l1})

    # Layer 2: Embeddings
    if not args.ftsgrep:
        l2 = embedding_search(query, top=args.top)
        if l2:
            out["layers"].append({"layer": 2, "label": "Embeddings", "count": len(l2), "results": l2})

    # Apply time decay to FTS5 results
    for layer in out["layers"]:
        for r in layer.get("results", []):
            if "ended_at" in r:
                adj = apply_time_decay(r.get("score", 1.0), r["ended_at"])
                r["adjusted_score"] = adj

    # Layer 3: gbrain (fallback if <3 results so far)
    total = sum(layer["count"] for layer in out["layers"])
    if total < 3 and not args.ftsgrep:
        l3 = gbrain_search(query, top=args.top)
        if l3:
            out["layers"].append({"layer": 3, "label": "gbrain fallback", "count": len(l3), "results": l3})

    out["elapsed_ms"] = round((time.time() - start) * 1000, 1)

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"\u001b[94mRecall: '{query}' ({out['elapsed_ms']}ms)\u001b[0m\n")
        for layer_info in out["layers"]:
            label = layer_info["label"]
            print(f"  [{label}] {layer_info['count']} matches")
            for r in layer_info["results"][:args.top]:
                if "session_id" in r:
                    title = r.get("title") or "?"
                    print(f"    - Session {r['session_id'][:12]}: {title}")
                    if r.get("summary"):
                        print(f"      {r['summary'][:120]}")
                elif "message_id" in r:
                    print(f"    - Message {r['message_id'][:12]} (sim={r['similarity']})")
                elif "source" in r:
                    print(f"    - gbrain: {str(r.get('data', r.get('raw', '?')))[:80]}")
        print()


if __name__ == "__main__":
    main()
