#!/usr/bin/env python3
"""
Domain Memory Manager v1
========================
在 flat memory 之上提供领域隔离层。

领域列表和各自配额:
  kiki: 300   — Kiki 关系状态
  astock: 400  — A 股配置/模型/因子
  promo: 300   — 推广运营
  system: 300  — 系统配置/哲学
  misc: 300    — 通用/其他

每个领域的条目用 @domain: 前缀标记。
add/replace/remove 时自动路由到对应领域。

用法 (由 agent 在归档流程中调用):
  python3 domain_memory.py list                    # 列出所有领域
  python3 domain_memory.py status                  # 各领域容量状态
  python3 domain_memory.py check <domain> <content> # 检查某领域能否写入
"""

import sys, json, re
from pathlib import Path

DOMAIN_CONFIG = {
    'kiki':   {'limit': 300,  'desc': 'Kiki 关系状态'},
    'astock': {'limit': 400, 'desc': 'A股配置/模型/因子'},
    'promo':  {'limit': 300,  'desc': '推广运营'},
    'system': {'limit': 300,  'desc': '系统配置/哲学'},
    'misc':   {'limit': 400,  'desc': '通用/其他'},
}
TOTAL_LIMIT = 1700  # sum of domains + buffer

# Known prefixes that map to domains
DOMAIN_PREFIXES = {
    'Kiki': 'kiki',
    'Hermes自审': 'system',
    '配置哲学': 'system',
    'Yfinance': 'astock',
    'A股': 'astock',
    'factor_weights': 'astock',
    '推广': 'promo',
    'ScrapeGraphAI': 'promo',
    '工具清单': 'promo',
    '归档': 'system',
    'humanizer': 'system',
    'Two Gmail': 'system',
}


def detect_domain(content: str) -> str:
    """Automatically detect domain from content prefix."""
    for prefix, domain in DOMAIN_PREFIXES.items():
        if content.startswith(prefix):
            return domain
    # Check if already tagged
    m = re.match(r'^@(\w+):', content)
    if m and m.group(1) in DOMAIN_CONFIG:
        return m.group(1)
    return 'misc'


def validate_domain(domain: str) -> bool:
    return domain in DOMAIN_CONFIG


def entries_by_domain(entries: list) -> dict:
    """Group entries by detected domain."""
    domains = {d: [] for d in DOMAIN_CONFIG}
    for e in entries:
        d = detect_domain(e)
        domains[d].append(e)
    return domains


def domain_status(entries: list) -> dict:
    """Return capacity status per domain."""
    grouped = entries_by_domain(entries)
    status = {}
    for domain, config in DOMAIN_CONFIG.items():
        domain_entries = grouped.get(domain, [])
        used = sum(len(e) + 3 for e in domain_entries)  # +3 for delimiter
        status[domain] = {
            'desc': config['desc'],
            'limit': config['limit'],
            'used': used,
            'entries': len(domain_entries),
            'pct': round(used / config['limit'] * 100, 1) if config['limit'] > 0 else 0,
        }
    return status


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: domain_memory.py list|status|check <domain> <content>')
        sys.exit(0)

    action = sys.argv[1]
    
    if action == 'list':
        print('领域\t\t限额\t说明')
        print('-' * 50)
        for d, c in DOMAIN_CONFIG.items():
            print(f'{d:<15} {c["limit"]:<6} {c["desc"]}')
        print()
        print('前缀映射:')
        for p, d in sorted(DOMAIN_PREFIXES.items(), key=lambda x: x[1]):
            print(f'  {p}... → @{d}')
    
    elif action == 'status':
        # Note: can't read memory directly, so output guidance
        result = {
            'domains': {d: {
                'limit': c['limit'],
                'desc': c['desc'],
            } for d, c in DOMAIN_CONFIG.items()},
            'total_limit': TOTAL_LIMIT,
            'total_used': 'N/A (run within session to read memory)',
            'usage_pct': 'N/A',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif action == 'check' and len(sys.argv) >= 4:
        domain = sys.argv[2]
        content = sys.argv[3]
        
        if not validate_domain(domain):
            print(json.dumps({'allowed': False, 'error': f'Unknown domain: {domain}'}))
            sys.exit(0)
        
        auto = detect_domain(content)
        if auto != domain:
            print(json.dumps({
                'allowed': True,
                'warning': f'内容看起来属于 @{auto} 而不是 @{domain}（确认前缀）',
                'auto_domain': auto,
            }))
        else:
            print(json.dumps({'allowed': True}))
    
    else:
        print(f'Unknown action: {action}')
        sys.exit(1)
