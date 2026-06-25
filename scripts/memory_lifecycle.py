#!/usr/bin/env python3
"""Memory Lifecycle Manager v1"""
import json, sqlite3, sys, os, time, re, argparse
from pathlib import Path
from datetime import datetime
HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.environ.get("AGENT_HOME", "~/.agent"))).expanduser()
STATE_DB = HERMES_HOME / "state.db"
GBRAIN_DB = HERMES_HOME / "gbrain" / "brain.db"
PROTECTED_SLUGS = ["hub-system-operations", "hub-stock-analysis", "hub-promotion-matrix"]
PROTECTED_TAGS = ["archive", "hub", "config", "protected"]
STALE_AFTER_DAYS = 90
ARCHIVE_AFTER_DAYS = 180
ACTIVE_TAG = "state:active"
STALE_TAG = "state:stale"
SUPERSEDED_TAG = "state:superseded"
ARCHIVED_TAG = "state:archived"
FEEDBACK_TAGS = {"helpful": "fb:helpful", "misleading": "fb:misleading", "outdated": "fb:outdated"}

def record_feedback(page_slug, rating, note=""):
    if rating not in FEEDBACK_TAGS:
        print(f"INVALID_RATING:{rating}")
        return False
    tag = FEEDBACK_TAGS[rating]
    print(f"FEEDBACK:{page_slug}->{tag}")
    if note:
        print(f"NOTE:{note}")
    return True

def rrf_fuse(results_list, k=60):
    scores = {}
    for results in results_list:
        for i, r in enumerate(results):
            sid = r.get("session_id") or r.get("slug") or str(hash(str(r)))
            rank = i + 1
            if sid not in scores:
                scores[sid] = {"score": 0, "sources": [], "data": r}
            scores[sid]["score"] += 1.0 / (k + rank)
            scores[sid]["sources"].append(r.get("layer", r.get("source", "?")))
    return sorted(scores.values(), key=lambda x: x["score"], reverse=True)

def test_rrf():
    fts5_results = [
        {"session_id": "A", "title": "Kiki chat", "layer": "fts5"},
        {"session_id": "B", "title": "Memory design", "layer": "fts5"},
        {"session_id": "C", "title": "Stock analysis", "layer": "fts5"},
        {"session_id": "D", "title": "Docker setup", "layer": "fts5"},
    ]
    gbrain_results = [
        {"slug": "B", "title": "Memory design", "source": "gbrain"},
        {"slug": "E", "title": "System hub", "source": "gbrain"},
        {"slug": "A", "title": "Kiki chat", "source": "gbrain"},
    ]
    fused = rrf_fuse([fts5_results, gbrain_results])
    print("=== RRF Fusion Test ===")
    for item in fused:
        print(f"  score={item['score']:.4f} sources={item['sources']} title={item['data'].get('title','?')}")
    return fused

def check_lifecycle(dry_run=False):
    print(f"MEMORY_LIFECYCLE_CHECK:{datetime.now().isoformat()}")
    print(f"THRESHOLD_STALE:{STALE_AFTER_DAYS}d")
    print(f"THRESHOLD_ARCHIVED:{ARCHIVE_AFTER_DAYS}d")
    print(f"PROTECTED_PAGES:{len(PROTECTED_SLUGS)}")
    print(f"DRY_RUN:{dry_run}")
    test_rrf()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-rrf", action="store_true")
    parser.add_argument("--feedback", nargs=3, metavar=("slug", "rating", "note"))
    args = parser.parse_args()
    if args.test_rrf:
        test_rrf()
        return
    if args.feedback:
        slug, rating, note = args.feedback
        record_feedback(slug, rating, note)
        return
    check_lifecycle(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
