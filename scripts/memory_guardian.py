#!/usr/bin/env python3
"""
Memory Guardian v3.0 — 智能记忆生命周期管理系统
=============================================
数据流: Hindsight (Hot Graph) -> 分类 -> gbrain (Cold) + index.db -> Stub

Usage:
  python3 memory_guardian.py              # 自动检测容量，按需执行
  python3 memory_guardian.py --force      # 强制执行全周期
  python3 memory_guardian.py --dry-run    # 预览模式
  python3 memory_guardian.py --status     # 仅报告状态
  python3 memory_guardian.py --drain-consolidation  # 排空 consolidation backlog
"""

import os, sys, json, re, sqlite3, subprocess, time, hashlib, shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from memory_family_registry import active_focus_profiles

# ─── Constants ──────────────────────────────────────────────────────────
AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
HINDSIGHT_BANK = os.environ.get("HINDSIGHT_BANK", "hermes")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_BASE_URL", "http://127.0.0.1:8890") + f"/v1/default/banks/{HINDSIGHT_BANK}"
DEFAULT_MEMORY_LIMIT = 20000  # Default Hindsight node budget for multi-agent installs
WARN = 0.75       # 75% — 开始分类预备
ACTION = 0.85     # 85% — 执行转移+压缩
CRITICAL = 0.95   # 95% — 强制紧急处理

INDEX_DB = AGENT_HOME / 'memory_index.db'
GOVERNANCE_DB = AGENT_HOME / 'memory_governance.db'
SCRIPTS_DIR = AGENT_HOME / 'scripts'
GBRAIN = shutil.which('gbrain') or os.environ.get('GBRAIN_BIN', 'gbrain')
METRICS_DIR = AGENT_HOME / 'metrics'
GUARDIAN_HISTORY = METRICS_DIR / 'guardian_status_history.jsonl'

# ─── Domain Classifiers (keyword + regex) ───────────────────────────────
CLASSIFIERS = {
    'user-profile': {
        'kws': ['user', 'preferences', 'profile', 'settings', 'config'],
        'prio': 80, 'slug': 'hub-user-profile',
        'stub': 'User [{date}] {s} → gbrain:{slug}'
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


def merge_focus_profile_classifiers(classifiers):
    merged = dict(classifiers)
    for profile_id, profile in active_focus_profiles().items():
        keywords = list(profile.get('keywords', ()) or profile.get('aliases', ()))
        if not keywords:
            continue
        merged[profile_id] = {
            'kws': keywords,
            'prio': int(profile.get('priority', 80)),
            'slug': profile.get('slug') or f'hub-{profile_id}',
            'stub': f"{profile.get('title', profile_id)} [{{date}}] {{s}} → gbrain:{{slug}}",
        }
    return merged


CLASSIFIERS = merge_focus_profile_classifiers(CLASSIFIERS)

PRESERVE_DOMAINS = {'preference'}  # Never compact user preferences

# Consolidation backlog drain defaults (safe, low-frequency)
CONSOLIDATION_DRAIN_MIN_PENDING = 20
CONSOLIDATION_DRAIN_MIN_AGE_SECONDS = 1800
CONSOLIDATION_DRAIN_MAX_CYCLES = 2
CONSOLIDATION_DRAIN_POLL_SECONDS = 8
CONSOLIDATION_STUCK_NONZERO_RUN = 8
HINDSIGHT_RESTART_COOLDOWN_SECONDS = 6 * 3600
HINDSIGHT_RESTART_GUARD = AGENT_HOME / '.hindsight_restart_guard.json'


def resolve_memory_limit() -> int:
    raw = os.environ.get("MEMORY_GUARDIAN_NODE_LIMIT", "").strip()
    if not raw:
        return DEFAULT_MEMORY_LIMIT
    try:
        value = int(raw)
    except ValueError:
        print(
            f"[memory_guardian] invalid MEMORY_GUARDIAN_NODE_LIMIT={raw!r}, using default {DEFAULT_MEMORY_LIMIT}",
            file=sys.stderr,
        )
        return DEFAULT_MEMORY_LIMIT
    if value <= 0:
        print(
            f"[memory_guardian] non-positive MEMORY_GUARDIAN_NODE_LIMIT={raw!r}, using default {DEFAULT_MEMORY_LIMIT}",
            file=sys.stderr,
        )
        return DEFAULT_MEMORY_LIMIT
    return value


MEMORY_LIMIT = resolve_memory_limit()

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
    except Exception:
        return None


def read_governance_meta() -> dict:
    if not GOVERNANCE_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(GOVERNANCE_DB))
        rows = conn.execute(
            "SELECT key, value FROM governance_meta WHERE key IN ('hindsight_items_total', 'hindsight_duplicate_count', 'hindsight_synced_at', 'last_rebuild_at')"
        ).fetchall()
        conn.close()
    except Exception as exc:
        print(f"[memory_guardian] failed to read governance meta: {exc}", file=sys.stderr)
        return {}
    payload = {key: value for key, value in rows}
    result = {}
    for field in ("hindsight_items_total", "hindsight_duplicate_count"):
        if field in payload:
            try:
                result[field] = int(float(payload[field]))
            except Exception:
                result[field] = payload[field]
    for field in ("hindsight_synced_at", "last_rebuild_at"):
        if field in payload:
            result[field] = payload[field]
    return result


def read_guardian_history(window: int = 12) -> list[dict]:
    if not GUARDIAN_HISTORY.exists():
        return []
    try:
        lines = [
            line.strip()
            for line in GUARDIAN_HISTORY.read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]
    except Exception as exc:
        print(f"[memory_guardian] failed to read guardian history: {exc}", file=sys.stderr)
        return []
    samples: list[dict] = []
    for line in lines[-window:]:
        try:
            payload = json.loads(line)
        except Exception:
            # skip corrupt JSON lines silently — may contain partial writes
            continue
        guardian = payload.get('guardian')
        if isinstance(guardian, dict):
            samples.append(guardian)
    return samples


def parse_iso_datetime(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def summarize_guardian_history(window: int = 12) -> dict:
    samples = read_guardian_history(window=window)
    if not samples:
        return {}
    pendings = []
    nodes = []
    timestamps = []
    for sample in samples:
        pending = sample.get('pending_consolidation')
        if isinstance(pending, (int, float)):
            pendings.append(int(pending))
        node_count = sample.get('nodes')
        if isinstance(node_count, (int, float)):
            nodes.append(int(node_count))
        ts = sample.get('last_consolidated_at')
        if isinstance(ts, str) and ts:
            timestamps.append(ts)
    if not pendings:
        return {'history_samples': len(samples)}
    latest = pendings[-1]
    earliest = pendings[0]
    delta = latest - earliest
    nonzero_run = 0
    for pending in reversed(pendings):
        if pending > 0:
            nonzero_run += 1
            continue
        break
    trending = 'flat'
    if delta > 0:
        trending = 'up'
    elif delta < 0:
        trending = 'down'
    latest_consolidated_dt = parse_iso_datetime(timestamps[-1]) if timestamps else None
    backlog_age_seconds = None
    if latest_consolidated_dt is not None:
        try:
            backlog_age_seconds = max(0, int((datetime.now(timezone.utc) - latest_consolidated_dt).total_seconds()))
        except Exception:
            backlog_age_seconds = None
    return {
        'history_samples': len(samples),
        'pending_consolidation_delta': delta,
        'pending_consolidation_trend': trending,
        'pending_consolidation_sticky': nonzero_run >= 3 and latest > 0,
        'pending_consolidation_nonzero_run': nonzero_run,
        'pending_consolidation_recent_max': max(pendings),
        'pending_consolidation_recent_min': min(pendings),
        'history_last_consolidated_at': timestamps[-1] if timestamps else None,
        'node_growth_delta': nodes[-1] - nodes[0] if len(nodes) >= 2 else 0,
        'backlog_age_seconds': backlog_age_seconds,
    }


def should_drain_consolidation(cap: dict, min_pending: int, min_age_seconds: int) -> tuple[bool, str]:
    pending = int(cap.get('pending_consolidation') or 0)
    failed = int(cap.get('failed_consolidation') or 0)
    sticky = bool(cap.get('pending_consolidation_sticky'))
    age = cap.get('backlog_age_seconds')
    age_ok = isinstance(age, (int, float)) and age >= min_age_seconds
    if pending < min_pending:
        return False, f"pending<{min_pending}"
    if failed > 0:
        return True, "failed_consolidation_present"
    if sticky and age_ok:
        return True, "sticky_and_aged"
    return False, "not_sticky_or_too_fresh"


def trigger_consolidation_cycle(poll_seconds: int = CONSOLIDATION_DRAIN_POLL_SECONDS) -> dict:
    trigger = hs('POST', '/consolidate', body={})
    if '_error' in trigger:
        # Some versions accept POST without body; retry empty body-less request.
        trigger = hs('POST', '/consolidate', body=None)
    time.sleep(max(1, int(poll_seconds)))
    stats = hs('GET', '/stats')
    return {'trigger': trigger, 'stats': stats}


def read_restart_guard() -> dict:
    if not HINDSIGHT_RESTART_GUARD.exists():
        return {}
    try:
        return json.loads(HINDSIGHT_RESTART_GUARD.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f"[memory_guardian] failed to read restart guard: {exc}", file=sys.stderr)
        return {}


def write_restart_guard(payload: dict) -> None:
    try:
        HINDSIGHT_RESTART_GUARD.parent.mkdir(parents=True, exist_ok=True)
        HINDSIGHT_RESTART_GUARD.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    except Exception as exc:
        print(f"[memory_guardian] failed to write restart guard: {exc}", file=sys.stderr)


def maybe_restart_hindsight_for_stuck_operation(stuck_operation_id: str, cooldown_seconds: int) -> dict:
    now = int(time.time())
    guard = read_restart_guard()
    last_ts = int(guard.get('last_restart_ts') or 0)
    if now - last_ts < cooldown_seconds:
        return {
            'restarted': False,
            'reason': 'cooldown_active',
            'seconds_until_retry': max(cooldown_seconds - (now - last_ts), 0),
        }
    cmd = ['systemctl', 'restart', 'hindsight.service']
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {
                'restarted': False,
                'reason': 'restart_failed',
                'returncode': proc.returncode,
                'stderr': (proc.stderr or '').strip()[:500],
            }
    except Exception as exc:
        return {'restarted': False, 'reason': 'restart_exception', 'error': str(exc)}
    write_restart_guard({
        'last_restart_ts': now,
        'operation_id': stuck_operation_id,
        'reason': 'stuck_consolidation_operation',
    })
    return {'restarted': True, 'reason': 'stuck_operation_restart'}


def drain_consolidation_if_needed(
    min_pending: int = CONSOLIDATION_DRAIN_MIN_PENDING,
    min_age_seconds: int = CONSOLIDATION_DRAIN_MIN_AGE_SECONDS,
    max_cycles: int = CONSOLIDATION_DRAIN_MAX_CYCLES,
    poll_seconds: int = CONSOLIDATION_DRAIN_POLL_SECONDS,
    force_restart_when_stuck: bool = False,
) -> dict:
    _, cap = monitor(verbose=False)
    if 'error' in cap:
        return {'ok': False, 'reason': 'monitor_error', 'error': cap.get('error')}
    should_drain, reason = should_drain_consolidation(cap, min_pending=min_pending, min_age_seconds=min_age_seconds)
    out = {
        'ok': True,
        'drain_requested': should_drain,
        'decision_reason': reason,
        'before': cap,
        'cycles': [],
    }
    if not should_drain:
        return out
    previous_pending = int(cap.get('pending_consolidation') or 0)
    operation_ids = []
    deduplicated_count = 0
    for cycle in range(max(1, int(max_cycles))):
        cycle_result = trigger_consolidation_cycle(poll_seconds=poll_seconds)
        stats = cycle_result.get('stats') or {}
        trigger = cycle_result.get('trigger') or {}
        op_id = trigger.get('operation_id')
        if isinstance(op_id, str) and op_id:
            operation_ids.append(op_id)
        if bool(trigger.get('deduplicated')):
            deduplicated_count += 1
        pending_after = int(stats.get('pending_consolidation') or previous_pending)
        cycle_result['pending_before'] = previous_pending
        cycle_result['pending_after'] = pending_after
        out['cycles'].append(cycle_result)
        previous_pending = pending_after
        if pending_after <= 0:
            break
    same_operation = len(set(operation_ids)) == 1 and len(operation_ids) >= 2
    unchanged_backlog = all(
        int(c.get('pending_before') or 0) == int(c.get('pending_after') or 0)
        for c in out['cycles']
    ) if out['cycles'] else False
    nonzero_run = int(cap.get('pending_consolidation_nonzero_run') or 0)
    out['stuck_operation_detected'] = bool(
        same_operation and unchanged_backlog and deduplicated_count >= 1 and nonzero_run >= CONSOLIDATION_STUCK_NONZERO_RUN
    )
    out['stuck_operation_id'] = operation_ids[0] if same_operation and operation_ids else None
    out['deduplicated_count'] = deduplicated_count
    out['restart_action'] = None
    if out['stuck_operation_detected'] and out['stuck_operation_id']:
        if force_restart_when_stuck:
            out['restart_action'] = maybe_restart_hindsight_for_stuck_operation(
                stuck_operation_id=out['stuck_operation_id'],
                cooldown_seconds=0,
            )
            out['restart_action']['forced'] = True
        else:
            out['restart_action'] = maybe_restart_hindsight_for_stuck_operation(
                stuck_operation_id=out['stuck_operation_id'],
                cooldown_seconds=HINDSIGHT_RESTART_COOLDOWN_SECONDS,
            )
        # If restart succeeded, retry one consolidation cycle once.
        if out['restart_action'].get('restarted'):
            time.sleep(4)
            retry_cycle = trigger_consolidation_cycle(poll_seconds=poll_seconds)
            retry_stats = retry_cycle.get('stats') or {}
            retry_cycle['pending_before'] = previous_pending
            retry_cycle['pending_after'] = int(retry_stats.get('pending_consolidation') or previous_pending)
            out['post_restart_cycle'] = retry_cycle
    _, after_cap = monitor(verbose=False)
    out['after'] = after_cap
    return out

# ─── Monitor — Query Hindsight for capacity ────────────────────────────
def monitor(verbose=True):
    stats = hs('GET', '/stats')
    entities = hs('GET', '/entities')
    
    if '_error' in stats:
        return [], {'error': stats['_error'], 'level': 'unknown'}
    
    docs = stats.get('total_documents', 0)
    nodes = stats.get('total_nodes', 0)
    obs = stats.get('total_observations', 0)
    pending = stats.get('pending_consolidation', 0)
    failed = stats.get('failed_consolidation', 0)
    pending_ops = stats.get('pending_operations', 0)
    failed_ops = stats.get('failed_operations', 0)
    last_consolidated_at = stats.get('last_consolidated_at')
    pct = min(100, round(nodes / MEMORY_LIMIT * 100, 1))
    
    cap = {
        'docs': docs, 'nodes': nodes, 'observations': obs,
        'pending_consolidation': pending,
        'failed_consolidation': failed,
        'pending_operations': pending_ops,
        'failed_operations': failed_ops,
        'last_consolidated_at': last_consolidated_at,
        'node_limit': MEMORY_LIMIT,
        'usage_pct': pct,
        'remaining': max(0, MEMORY_LIMIT - nodes),
        'level': 'ok' if pct < WARN*100 else ('warn' if pct < ACTION*100 else
                 'action' if pct < CRITICAL*100 else 'critical')
    }
    cap.update(read_governance_meta())
    cap.update(summarize_guardian_history())
    synced_at = cap.get('hindsight_synced_at')
    if synced_at is not None:
        try:
            cap['hindsight_sync_lag_seconds'] = max(0, int(time.time() - float(synced_at)))
        except Exception as exc:
            print(f"[memory_guardian] sync lag calculation failed: {exc}", file=sys.stderr)
    
    # Extract entity names as memory entry candidates
    entries = entities.get('items', [])
    
    if verbose:
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
            except Exception as exc:
                print(f"[memory_guardian] gbrain put failed for {item['slug']}: {exc}", file=sys.stderr)
            
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
    parser = argparse.ArgumentParser(description='Memory Guardian v3.0')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--drain-consolidation', action='store_true', help='Attempt to drain sticky consolidation backlog safely')
    parser.add_argument('--min-pending', type=int, default=CONSOLIDATION_DRAIN_MIN_PENDING)
    parser.add_argument('--min-age-seconds', type=int, default=CONSOLIDATION_DRAIN_MIN_AGE_SECONDS)
    parser.add_argument('--max-cycles', type=int, default=CONSOLIDATION_DRAIN_MAX_CYCLES)
    parser.add_argument('--poll-seconds', type=int, default=CONSOLIDATION_DRAIN_POLL_SECONDS)
    parser.add_argument('--force-restart-when-stuck', action='store_true', help='Bypass cooldown once when validating stuck-operation recovery')
    args = parser.parse_args()
    
    if args.status:
        entries, cap = monitor(verbose=False)
        print(json.dumps(cap, ensure_ascii=False))
        return
    if args.drain_consolidation:
        payload = drain_consolidation_if_needed(
            min_pending=args.min_pending,
            min_age_seconds=args.min_age_seconds,
            max_cycles=args.max_cycles,
            poll_seconds=args.poll_seconds,
            force_restart_when_stuck=args.force_restart_when_stuck,
        )
        print(json.dumps(payload, ensure_ascii=False))
        if payload.get('ok'):
            return
        sys.exit(1)

    print(f"🧠 Memory Guardian v3.0 — {datetime.now().isoformat()}")
    print("=" * 50)
    
    entries, cap = monitor()
    if 'error' in cap:
        print(f"\n❌ Hindsight unavailable: {cap['error']}")
        sys.exit(1)

    action = 'force' if args.force else (
        'full' if cap['level'] in ('action','critical') else
        'classify' if cap['level'] == 'warn' else 'none')

    if action == 'none':
        if cap['level'] == 'unknown':
            print("\n⚠️  Hindsight status unknown — skipping lifecycle actions")
            sys.exit(1)
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
