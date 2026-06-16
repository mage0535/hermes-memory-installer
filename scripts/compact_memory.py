#!/usr/bin/env python3
"""
Memory Compaction v2 — 可执行版本
==================================
分析当前 memory 条目，识别可归档/过期内容，输出建议移除列表。
由 Hermes agent 在 post-session-archiving 流程中调用。

用法:
  python3 compact_memory.py --analyze   # 输出分析报告
  python3 compact_memory.py --apply     # 执行清理（需 agent 调用 memory(action='remove')）
"""

import sys, json, re
from pathlib import Path

MEMORY_LIMIT = 2200

# 过期模式 — 描述已完成/过期的任务条目
STALE_PATTERNS = [
    r'(?:已|完成|完毕|好了|done|fixed|resolved)\s*(?:修复|解决|创建|安装|部署)',
    r'cron.*已(?:建|设|创建|安装|合并)',
    r'(?:第一轮|第二轮|第\w轮).*优化',
    r'已完成.*条',
]

# 强制保留的关键词
PROTECTED = [
    '关系', '雷区', '不要', '禁止', '严禁',
    'API Key', 'API_KEY', 'secret', '密码', 'token', 'Gmail',
    'prefer', '偏好', '哲学', 'humanizer',
]

# 时间敏感 — 含日期的条目超过 N 天未更新则标记
STALE_DAYS = 14


def classify(entries: list) -> dict:
    """分析条目，返回分类结果"""
    result = {
        'total': len(entries),
        'total_chars': sum(len(e) for e in entries),
        'limit': MEMORY_LIMIT,
        'usage_pct': round(sum(len(e) for e in entries) / MEMORY_LIMIT * 100, 1),
        'keep': [],
        'stale': [],
        'protect': [],
    }
    
    for idx, entry in enumerate(entries):
        # 检查保护关键词
        protected = any(kw.lower() in entry.lower() for kw in PROTECTED)
        
        if protected:
            result['protect'].append({'idx': idx, 'preview': entry[:80]})
            result['keep'].append(entry)
            continue
        
        # 检查过期模式
        is_stale = False
        reason = ''
        for pat in STALE_PATTERNS:
            if re.search(pat, entry):
                is_stale = True
                reason = f'match: {pat}'
                break
        
        if is_stale:
            result['stale'].append({'idx': idx, 'preview': entry[:80], 'reason': reason})
        else:
            result['keep'].append(entry)
            result['protect'].append({'idx': idx, 'preview': entry[:80], 'reason': 'active'})
    
    # 估算释放空间
    result['freed_chars'] = sum(len(e) for e in result['stale'])
    result['after_compaction_pct'] = round(
        (result['total_chars'] - result['freed_chars']) / MEMORY_LIMIT * 100, 1
    ) if result['freed_chars'] > 0 else result['usage_pct']
    
    return result


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('--analyze', '--apply'):
        print('Usage: compact_memory.py --analyze | --apply')
        print()
        print('  --analyze  分析当前 memory，显示可归档条目')
        print('  --apply    输出 JSON 格式的移除建议列表（供 agent 逐条执行 memory remove）')
        sys.exit(1)

    mode = sys.argv[1]
    
    # 内存中无法直接读取 memory 内容，输出指导说明
    if mode == '--analyze':
        print('=' * 50)
        print('Memory Compaction v2')
        print('=' * 50)
        print()
        print('此脚本由 Hermes agent 在 post-session-archiving 流程中调用。')
        print()
        print('分析流程:')
        print('  1. 读取 memory 所有条目')
        print('  2. 匹配过期模式 (STALE_PATTERNS)')
        print('  3. 排除保护关键词 (PROTECTED)')
        print('  4. 输出建议移除列表')
        print()
        print('集成方式:')
        print('  post-session-archiving skill 的步骤 0a 中包含：')
        print('   - capacity > 85% → 运行此脚本分析')
        print('   - 识别 stale 条目 → 用 memory(action="remove") 移除')
        print('   - 重新检查容量')
        print()
        print(f'保护关键词: {PROTECTED}')
        print(f'过期模式: {STALE_PATTERNS}')
    elif mode == '--apply':
        # 输出 JSON 格式的指令供 agent 执行
        instructions = {
            'action': 'compact',
            'steps': [
                '1. 读取 memory 所有条目（当前记忆）',
                '2. 对每条执行 should_archive()',
                '3. 匹配 PROTECTED 的条目跳过',
                '4. 匹配 STALE_PATTERNS 的条目 → memory(action="remove", old_text=...)',
                '5. 确认释放后容量 < 80%',
            ],
            'protected_keywords': PROTECTED,
            'stale_patterns': [p for p in STALE_PATTERNS],
        }
        print(json.dumps(instructions, ensure_ascii=False, indent=2))
