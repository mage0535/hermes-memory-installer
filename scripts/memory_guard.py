#!/usr/bin/env python3
"""
Legacy memory guard helper.

This helper is not part of the production sidecar install set, but it should
still respect the shared AGENT_HOME contract so teammates can run it safely in
different agent runtimes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

AGENT_HOME = Path(
    os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))
).expanduser()
MEMORY_LIMIT = int(os.environ.get("MEMORY_GUARD_LIMIT", "2200"))
MEMORY_FILE = AGENT_HOME / "memory.json"


def estimate_capacity(entries: list[str]) -> dict:
    total = sum(len(entry) for entry in entries)
    pct = total / MEMORY_LIMIT * 100 if MEMORY_LIMIT else 0
    return {
        "total_chars": total,
        "limit": MEMORY_LIMIT,
        "usage_pct": round(pct, 1),
        "remaining": MEMORY_LIMIT - total,
        "remaining_pct": round(100 - pct, 1),
        "needs_compaction": pct >= 80,
        "critical": pct >= 95,
        "healthy": pct < 70,
    }


def suggest_compaction(entries: list[str]) -> list[dict]:
    from compact_memory import should_archive

    suggestions = []
    for entry in entries:
        should_compact, reason = should_archive(entry)
        if should_compact:
            suggestions.append({"text": entry[:80], "reason": reason})
    return suggestions


if __name__ == "__main__":
    print("=" * 50)
    print("Memory Guard v1")
    print("=" * 50)
    print()
    print("Legacy helper for pre-write capacity checks.")
    print(f"Agent home: {AGENT_HOME}")
    print(f"Memory file: {MEMORY_FILE}")
    print()
    print("Run this helper before writing large memory payloads if you still use")
    print("the old local-memory.json workflow.")
    print()
    print(f"  python3 {AGENT_HOME / 'scripts' / 'memory_guard.py'} --check-only")
    print()
    if "--check-only" in sys.argv:
        print("[CHECK] Load entries from memory.json, then call estimate_capacity(entries).")
    elif "--auto-compact" in sys.argv:
        print("[AUTO] Run compaction from a scheduled task rather than blocking writes inline.")
