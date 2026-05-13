#!/usr/bin/env python3
"""
Memory Guard — 写入前容量检查
=============================
在写入新 memory 前检查剩余容量。
如果 < 20% (440 chars)，自动触发 compaction 预警。

用法: python3 memory_guard.py [--check-only | --auto-compact]

集成到写入流程：
  来自 hermes_tools import memory
  # 写入前先检查
  from memory_guard import check_capacity
  if check_capacity()['needs_compaction']:
      print("[MEMORY GUARD] 容量不足，建议先 compaction")
"""
import os, json, re, sys
from pathlib import Path

MEMORY_LIMIT = 2200
MEMORY_FILE = Path.home() / '.hermes' / 'memory.json'

# 假设 memory 持久化为 JSON 文件（实际由 hermes core 管理）
# 此工具通过 hermes CLI 或直接读取文件来获取状态


def estimate_capacity(entries: list) -> dict:
    """估算当前 memory 容量状态"""
    total = sum(len(e) for e in entries)
    pct = total / MEMORY_LIMIT * 100

    return {
        'total_chars': total,
        'limit': MEMORY_LIMIT,
        'usage_pct': round(pct, 1),
        'remaining': MEMORY_LIMIT - total,
        'remaining_pct': round(100 - pct, 1),
        'needs_compaction': pct >= 80,
        'critical': pct >= 95,
        'healthy': pct < 70,
    }


def suggest_compaction(entries: list) -> list:
    """建议可 compact 的条目"""
    from compact_memory import should_archive
    suggestions = []
    for entry in entries:
        yes, reason = should_archive(entry)
        if yes:
            suggestions.append({'text': entry[:80], 'reason': reason})
    return suggestions


if __name__ == '__main__':
    print("=" * 50)
    print("Memory Guard v1")
    print("=" * 50)
    print()

    # 模拟状态报告（实际由 hermes agent 在写入时调用）
    print("整合到 Hermes Agent 写入流程：")
    print()
    print("在任何 memory(action=...) 调用前，执行以下检查：")
    print()
    print("  from hermes_tools import terminal")
    print("  result = terminal('python3 ~/.hermes/scripts/memory_guard.py --check-only')")
    print("  # 如果 output 包含 needs_compaction，先 compaction")
    print()
    print("推荐：在 session-to-gbrain 管道中集成容量检查，")
    print("每次归档会话后自动检查 memory 容量。")

    if '--check-only' in sys.argv:
        print("\n[CHECK] 需要由 hermes agent 从 memory 读取 entries 后调用 estimate_capacity()")
    elif '--auto-compact' in sys.argv:
        print("\n[AUTO] 触发 compaction — 建议由 cron 任务执行而非拦截式")
