#!/usr/bin/env python3
"""
Memory Pre-Write Guard v1
=========================
Pre-write guard that checks:
1. Capacity (blocks if >85%)
2. Contradiction detection (suggests replace)
3. Returns structured JSON for agent decision

Call: python3 memory_prewrite_guard.py <new_content>
"""

import sys, json, re
from pathlib import Path

MEMORY_LIMIT = 2200
WARN = 0.80
BLOCK = 0.85

CONTRADICTION_PAIRS = [
    (r'撤回.*用不了', r'摩手机|跟爸吵架|砸了|碎了'),
    (r'5/12.*撤回', r'5/12.*摩|更正|纠正'),
]

def check_cap(entries):
    total = sum(len(e) for e in entries)
    pct = total / MEMORY_LIMIT
    return {'usage_pct': round(pct*100, 1), 'blocked': pct >= BLOCK, 'remaining': MEMORY_LIMIT - total}

def detect(new_content, entries):
    for idx, entry in enumerate(entries):
        for old_pat, new_pat in CONTRADICTION_PAIRS:
            if re.search(old_pat, entry, re.I) and re.search(new_pat, new_content, re.I):
                return {'old_idx': idx, 'old_entry': entry[:120]}
    return None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('{"error": "usage: memory_prewrite_guard.py <new_content>"}')
        sys.exit(1)
    new = sys.argv[1]
    mf = Path.home() / '.hermes' / 'memory.json'
    try:
        if mf.exists():
            data = json.loads(mf.read_text())
            entries = data.get('entries', [])
        else:
            entries = []
    except:
        entries = []
    cap = check_cap(entries)
    contra = detect(new, entries)
    result = {'allowed': not cap['blocked'], 'capacity': cap, 'contradiction': contra}
    if cap['blocked']:
        result['reason'] = f'容量 {cap["usage_pct"]}% 超过阻止线'
    elif contra:
        result['reason'] = f'矛盾: 新内容与条目#{contra["old_idx"]}冲突, 建议replace'
    print(json.dumps(result, ensure_ascii=False))
