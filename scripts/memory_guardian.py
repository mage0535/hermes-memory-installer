#!/usr/bin/env python3
"""
Memory Guardian v2 — 智能记忆生命周期管理系统
=============================================
数据流: Hindsight (Hot Graph) → 分类 → gbrain (Cold) + index.db → Stub

架构:
  monitor() → classify() → transfer() → index() → compact() → report()

Usage:
  python3 memory_guardian.py              # 自动检测容量，按需执行
  python3 memory_guardian.py --force      # 强制执行全周期
  python3 memory_guardian.py --dry-run    # 预览模式
  python3 memory_guardian.py --status     # 仅报告状态
"""

import os, sys, json, re, sqlite3, subprocess, time, hashlib, shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Constants ──────────────────────────────────────────────────────────
HINDSIGHT_URL = "http://127.0.0.1:8890/v1/default/banks/hermes"
MEMORY_LIMIT = 5000
WARN = 0.75       # 75% — 开始分类预备
ACTION = 0.85     # 85% — 执行转移+压缩
CRITICAL = 0.95   # 95% — 强制紧急处理

INDEX_DB = Path.home() / '.hermes' / 'memory_index.db'
SCRIPTS_DIR = Path.home() / '.hermes' / 'scripts'
GBRAIN = shutil.which('gbrain') or '/root/.bun/bin/gbrain'

# ─── Domain Classifiers (keyword + regex) ───────────────────────────────
CLASSIFIERS = {
    'kiki': {
        'kws': ['kiki','王钰淇','御妹儿','手术','流血','医院','毓璜顶','信任链','吵架',
                '撤回','聊天','驻唱','昼夜颠倒','emoji信号','冷一下','盲区','雷区'],
        'prio': 80, 'slug': 'kiki-chat-archive',
        'stub': 'Kiki [{date}] {s} → gbrain:{slug}'
    },
    'system': {
        'kws': ['配置哲学','config.yaml','cron','部署','安装','注册','升级','迁移',
                '路由','代理','v2raya','配额','model','provider','atomgit','opencode',
                'fallback','memory分层','归档','guard'],
        'prio': 60, 'slug': 'hub-system-operations',
        'stub': 'Sys [{date}] {s} → gbrain:{slug}'
    },
    'tool': {
        'kws': ['MCP Server','skill.*创建','转换','工具清单','manifest','integrated',
                'agentskills','chrome-devtools','codegraph','security.*skills'],
        'prio': 70, 'slug': 'hub-system-operations',
        'stub': 'Tool [{date}] {s} → gbrain:{slug}'
    },
    'finance': {
        'kws': ['A股','股票','选股','交易','投资','宏观','晨报','HS300','ZZ500',
                'Baostock','china-macro'],
        'prio': 50, 'slug': 'hub-a-stock-trading',
        'stub': 'Fin [{date}] {s} → gbrain:{slug}'
    },
    'workflow': {
        'kws': ['workflow','流水线','协作','流程','模式','方法论','原则','prefer',
                '偏好','规范','铁律'],
        'prio': 40, 'slug': 'knowledge/hermes-workflows',
        'stub': 'WF [{date}] {s} → gbrain:{slug}'
    },
    'preference': {
        'kws': ['不要','禁止','必须','不允许','style','format','排版','changelog',
                '谢谢','感谢','设计原则','优先','不做','skip'],
        'prio': 90, 'slug': 'knowledge/user-preferences',
        'stub': 'Pref [{date}] {s} → gbrain:{slug}'
    },
}

PRESERVE_DOMAINS = {'preference'}  # Never compact user preferences

# ─── Hindsight API ──────────────────────────────────────────────────────
def hs(method, path, body=None, timeout=10):
    url = f"{HINDSIGHT_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method,
                  headers={'Content-Type':'application/json'} if data else {})
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        body = e.read().decode()[:200] if e.code != 404 else ''
        return {'_error': f'HTTP {e.code}', '_body': body}
    except Exception as e:
        return {'_error': str(e)}

# ─── Index Database ─────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(str(INDEX_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS idx (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_hash TEXT UNIQUE,
            domain TEXT, priority INTEGER,
            destination TEXT, dest_type TEXT,
            tags TEXT, archived_at TEXT,
            stub_active INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON idx(domain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tags ON idx(tags)")
    conn.commit()
    return conn

def record_index(conn, text, domain, prio, dest, dtype, tags=''):
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute("INSERT OR IGNORE INTO idx VALUES (NULL,?,?,?,?,?,?,?,1)",
                     (h, domain, prio, dest, dtype, tags, now))
        conn.commit()
        return h
    except: return None

# ─── Monitor — Query Hindsight for capacity ────────────────────────────
def monitor():
    stats = hs('GET', '/stats')
    entities = hs('GET', '/entities')
    
    if '_error' in stats:
        return [], {'error': stats['_error'], 'level': 'unknown'}
    
    # Estimate: total_documents * avg_doc_size (rough)
    docs = stats.get('total_documents', 0)
    nodes = stats.get('total_nodes', 0)
    obs = stats.get('total_observations', 0)
    
    # Weighted capacity estimation
    weighted = docs * 150 + nodes * 80 + obs * 60
    pct = min(100, round(weighted / MEMORY_LIMIT * 100, 1))
    
    cap = {
        'docs': docs, 'nodes': nodes, 'observations': obs,
        'usage_pct': pct, 'remaining': max(0, MEMORY_LIMIT - weighted),
        'level': 'ok' if pct < WARN*100 else ('warn' if pct < ACTION*100 else
                 'action' if pct < CRITICAL*100 else 'critical')
    }
    
    # Extract entity names as memory entry candidates
    entries = entities.get('items', [])
    
    print(f"📊 Hindsight Memory:")
    print(f"   Docs: {docs} | Nodes: {nodes} | Observations: {obs}")
    print(f"   Entities: {len(entries)}")
    print(f"   Estimated usage: {pct}% | Level: {cap['level'].upper()}")
    print(f"   Balance: {cap['remaining']} chars")
    
    return entries, cap

# ─── Classify — Determine domain for each entity ────────────────────────
def classify(text):
    text_l = text.lower()
    best = ('misc', 0, [], None)
    for domain, cfg in CLASSIFIERS.items():
        score = sum(1 for kw in cfg['kws'] if kw.lower() in text_l)
        if score > best[1]:
            best = (domain, score, [k for k in cfg['kws'] if k.lower() in text_l], cfg)
    return best  # (domain, score, matched_kws, config)

def classify_entries(entries, cap):
    """Classify all entries and group by domain."""
    print(f"\n🔍 Classification:")
    by_domain = {}
    for e in entries:
        name = e.get('canonical_name', e.get('id', ''))
        domain, score, kws, cfg = classify(name)
        by_domain.setdefault(domain, []).append({
            'name': name, 'score': score, 'kws': kws,
            'prio': cfg['prio'] if cfg else 0,
            'slug': cfg['slug'] if cfg else 'misc'
        })
    
    for d, items in sorted(by_domain.items()):
        c = CLASSIFIERS.get(d)
        print(f"   {d}: {len(items)} items (prio={c['prio'] if c else 0}, →{c['slug'] if c else 'misc'})")
        for item in items[:3]:
            print(f"     {item['name']}")
        if len(items) > 3:
            print(f"     ... +{len(items)-3} more")
    
    return by_domain

# ─── Transfer — Move to gbrain + Index ─────────────────────────────────
def transfer(by_domain, dry_run=False):
    print(f"\n🔄 Transfer {'(DRY RUN)' if dry_run else ''}:")
    conn = init_db()
    results = {'transferred': 0, 'indexed': 0}
    
    for domain, items in by_domain.items():
        if domain in PRESERVE_DOMAINS:
            print(f"   ⏭️  {domain}: preserved")
            continue
        
        for item in items:
            h = hashlib.sha256(item['name'].encode()).hexdigest()[:16]
            existing = conn.execute("SELECT id FROM idx WHERE entry_hash=?", (h,)).fetchone()
            if existing:
                print(f"   ⏭️  {item['name']}: already indexed")
                continue
            
            if dry_run:
                print(f"   📤 {item['name']} → gbrain:{item['slug']}")
                continue
            
            # Create archive content
            ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
            payload = f"\n\n### Auto-archived {ts}\nEntity: {item['name']}\nDomain: {domain}\n_By memory_guardian_"
            
            # Write to gbrain
            ok = False
            try:
                r = subprocess.run([GBRAIN, 'put', item['slug']], input=payload.encode(),
                                 capture_output=True, timeout=15)
                ok = r.returncode == 0
            except: pass
            
            if ok:
                rec = record_index(conn, item['name'], domain, item['prio'],
                                  item['slug'], 'gbrain', ','.join(item['kws'][:3]))
                results['transferred'] += 1
                results['indexed'] += 1
                print(f"   ✅ {item['name']} → {item['slug']} (idx:{rec})")
            else:
                print(f"   ⚠️  {item['name']}: gbrain write failed")
    
    conn.close()
    return results

# ─── Main ───────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Memory Guardian v2')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    
    print(f"🧠 Memory Guardian v2 — {datetime.now().isoformat()}")
    print("=" * 50)
    
    entries, cap = monitor()
    if '_error' in cap:
        print(f"\n❌ Hindsight unavailable: {cap['error']}")
        sys.exit(1)
    
    if args.status:
        print(json.dumps(cap, ensure_ascii=False))
        return
    
    action = 'force' if args.force else (
        'full' if cap['level'] in ('action','critical') else
        'classify' if cap['level'] == 'warn' else 'none')
    
    if action == 'none':
        print(f"\n✅ Capacity OK ({cap['usage_pct']}%) — no action")
        return
    
    by_domain = classify_entries(entries, cap)
    
    if action == 'classify':
        print(f"\n✅ Classification done — not yet at action threshold")
        return
    
    results = transfer(by_domain, dry_run=args.dry_run)
    
    print(f"\n📋 Summary:")
    print(f"   Transferred: {results['transferred']}")
    print(f"   Indexed: {results['indexed']}")
    print(f"   Capacity: {cap['usage_pct']}% ({cap['level']})")
    print(f"   Recommendations: {cap['level']}")

if __name__ == '__main__':
    main()
