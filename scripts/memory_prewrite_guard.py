#!/usr/bin/env python3
"""
Legacy pre-write guard for local memory.json workflows.

Not part of the portable sidecar runtime, but kept compatible with AGENT_HOME
so it does not assume a Hermes-only directory layout.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

AGENT_HOME = Path(
    os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))
).expanduser()
MEMORY_LIMIT = int(os.environ.get("MEMORY_PREWRITE_LIMIT", "2200"))
BLOCK = 0.85
MEMORY_FILE = AGENT_HOME / "memory.json"

CONTRADICTION_PAIRS = [
    (r"withdraw.*unavailable", r"phone broken|device damaged"),
    (r"5/12.*withdraw", r"5/12.*corrected|5/12.*updated"),
]


def check_cap(entries: list[str]) -> dict:
    total = sum(len(entry) for entry in entries)
    pct = total / MEMORY_LIMIT if MEMORY_LIMIT else 0
    return {"usage_pct": round(pct * 100, 1), "blocked": pct >= BLOCK, "remaining": MEMORY_LIMIT - total}


def detect(new_content: str, entries: list[str]) -> dict | None:
    for idx, entry in enumerate(entries):
        for old_pat, new_pat in CONTRADICTION_PAIRS:
            if re.search(old_pat, entry, re.I) and re.search(new_pat, new_content, re.I):
                return {"old_idx": idx, "old_entry": entry[:120]}
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('{"error": "usage: memory_prewrite_guard.py <new_content>"}')
        sys.exit(1)
    new = sys.argv[1]
    try:
        if MEMORY_FILE.exists():
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
        else:
            entries = []
    except Exception:
        entries = []
    cap = check_cap(entries)
    contra = detect(new, entries)
    result = {"allowed": not cap["blocked"], "capacity": cap, "contradiction": contra}
    if cap["blocked"]:
        result["reason"] = f"capacity {cap['usage_pct']}% exceeds block threshold"
    elif contra:
        result["reason"] = f"contradiction with entry #{contra['old_idx']}; replace recommended"
    print(json.dumps(result, ensure_ascii=False))
