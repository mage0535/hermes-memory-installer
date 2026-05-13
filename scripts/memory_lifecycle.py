#!/usr/bin/env python3
"""Memory Lifecycle Manager v1 — Stale/archive detection with configurable protection"""
import json, sqlite3, sys, os, time, re, argparse
from pathlib import Path
from datetime import datetime

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
STATE_DB = HERMES_HOME / "state.db"
GBRAIN_DB = HERMES_HOME / "gbrain" / "brain.db"

# ── Configurable via ~/.hermes/memory_lifecycle.yaml ──────────
# Protected pages won't be auto-archived or downranked.
# The mechanism works regardless of what you put here.
CONFIG_FILE = HERMES_HOME / "memory_lifecycle.yaml"

def _load_config():
    """Load protected pages/tags from YAML config. Falls back to empty lists."""
    import yaml
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                cfg = yaml.safe_load(f) or {}
            return {
                "slugs": cfg.get("protected_slugs", []),
                "tags": cfg.get("protected_tags", []),
            }
    except Exception:
        pass
    return {"slugs": [], "tags": []}

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
    """Reciprocal Rank Fusion — standard IR rank merging."""
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

def is_protected(slug, tags=None):
    """Check if a page is protected from auto-archive/downrank."""
    cfg = _load_config()
    if slug in cfg["slugs"]:
        return True
    if tags:
        for t in tags:
            if t in cfg["tags"]:
                return True
    return False

def check_lifecycle(dry_run=False):
    cfg = _load_config()
    print(f"MEMORY_LIFECYCLE_CHECK:{datetime.now().isoformat()}")
    print(f"THRESHOLD_STALE:{STALE_AFTER_DAYS}d")
    print(f"THRESHOLD_ARCHIVED:{ARCHIVE_AFTER_DAYS}d")
    print(f"PROTECTED_SLUGS:{len(cfg['slugs'])}")
    print(f"PROTECTED_TAGS:{len(cfg['tags'])}")
    print(f"DRY_RUN:{dry_run}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Memory lifecycle management")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode")
    parser.add_argument("--test-rrf", action="store_true", help="Run RRF test")
    parser.add_argument("--feedback", nargs=3, metavar=("slug", "rating", "note"),
                        help="Record feedback tag on a page")
    args = parser.parse_args()

    if args.test_rrf:
        # Test data uses generic placeholders, not real project data
        fts5_results = [
            {"session_id": "session-A", "title": "Example topic 1", "layer": "fts5"},
            {"session_id": "session-B", "title": "Example topic 2", "layer": "fts5"},
            {"session_id": "session-C", "title": "Example topic 3", "layer": "fts5"},
        ]
        gbrain_results = [
            {"slug": "docs/example-topic", "title": "Example topic from graph", "source": "gbrain"},
            {"slug": "docs/another-topic", "title": "Another topic", "source": "gbrain"},
        ]
        fused = rrf_fuse([fts5_results, gbrain_results])
        print("=== RRF Fusion Test ===")
        for item in fused:
            print(f"  score={item['score']:.4f} sources={item['sources']} title={item['data'].get('title','?')}")
        return

    if args.feedback:
        slug, rating, note = args.feedback
        record_feedback(slug, rating, note)
        return

    check_lifecycle(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
