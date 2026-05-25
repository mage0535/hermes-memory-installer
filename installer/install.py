"""Hermes Memory Installer 2.2 – Main installer"""
import os, sys, shutil, subprocess
from pathlib import Path

HERMES_HOME = Path.home() / '.hermes'
SKILLS_DIR = HERMES_HOME / 'skills'
ARCHIVES_DIR = HERMES_HOME / 'archives'
POOL_DB = HERMES_HOME / 'pool.db'
CONFIG_PATH = HERMES_HOME / 'config.yaml'
REPO_ROOT = Path(__file__).resolve().parent.parent

def check_hermes():
    if not HERMES_HOME.exists():
        print('❌ ~/.hermes not found. Install Hermes Agent first.')
        sys.exit(1)
    print('✅ Hermes found')

def check_python():
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 9):
        print(f'❌ Python >= 3.9 required, got {v.major}.{v.minor}')
        sys.exit(1)
    print(f'✅ Python {v.major}.{v.minor}.{v.micro}')

def check_sqlite_fts5():
    import sqlite3
    try:
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE VIRTUAL TABLE test USING fts5(content)')
        conn.close()
        print('✅ SQLite FTS5 supported')
    except Exception as e:
        print(f'⚠️  SQLite FTS5 not available: {e}')

def backup_config():
    if CONFIG_PATH.exists():
        import datetime
        bk = CONFIG_PATH.with_name(f'config.yaml.pre-memory-{datetime.date.today().isoformat()}')
        if not bk.exists():
            shutil.copy2(str(CONFIG_PATH), str(bk))
            print(f'✅ Config backed up to {bk.name}')

def create_archives():
    for sub in ['people','projects','knowledge','_index']:
        (ARCHIVES_DIR / sub).mkdir(parents=True, exist_ok=True)
    print('✅ Archive directories created')

def init_pool_db():
    import sqlite3
    conn = sqlite3.connect(str(POOL_DB))
    conn.executescript("""CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY, session_id TEXT,
  timestamp REAL DEFAULT (julianday("now")),
  role TEXT, content TEXT, topic_tags TEXT,
  archived INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  start_time REAL DEFAULT (julianday("now")),
  title TEXT, summary TEXT,
  archived INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS archives (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE,
  type TEXT, title TEXT, summary TEXT,
  tags TEXT, last_read REAL, priority INTEGER DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS archives_fts USING fts5(
  title, summary, tags, content=archives, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS archives_ai AFTER INSERT ON archives BEGIN
  INSERT INTO archives_fts(rowid, title, summary, tags)
  VALUES (new.id, new.title, new.summary, new.tags);
END;
CREATE INDEX IF NOT EXISTS idx_archives_type ON archives(type, priority DESC);
""")
    conn.commit()
    conn.close()
    print('✅ pool.db initialized with FTS5')

def install_skills():
    src_skills = REPO_ROOT / 'skills'
    if src_skills.exists():
        for skill_dir in ['memory-starter-kit','memory-archivist','memory-proactive']:
            src = src_skills / skill_dir
            dst = SKILLS_DIR / skill_dir
            if src.exists() and not dst.exists():
                shutil.copytree(str(src), str(dst))
                print(f'✅ Installed skill: {skill_dir}')

def patch_config():
    try:
        from ruamel.yaml import YAML
        yaml = YAML(); yaml.preserve_quotes = True
        with open(str(CONFIG_PATH)) as f: data = yaml.load(f) or {}
    except ImportError:
        import yaml
        with open(str(CONFIG_PATH)) as f: data = yaml.safe_load(f) or {}
    if 'skills' not in data or not isinstance(data['skills'], list):
        data['skills'] = []
    existing = set(data['skills'])
    for s in ['memory-starter-kit','memory-archivist']:
        if s not in existing:
            data['skills'].append(s)
    try:
        from ruamel.yaml import YAML
        yaml = YAML(); yaml.default_flow_style = False
        with open(str(CONFIG_PATH), 'w') as f: yaml.dump(data, f)
    except ImportError:
        import yaml
        with open(str(CONFIG_PATH), 'w') as f: yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
    print('✅ Config patched')

def setup_memory_consolidation_cron():
    """Optional every-6-hours memory consolidation cron."""
    enabled = os.getenv('ENABLE_MEMORY_CONSOLIDATION_CRON', '1').lower() not in ('0', 'false', 'no')
    if not enabled:
        print('ℹ️  Skip memory consolidation cron (ENABLE_MEMORY_CONSOLIDATION_CRON disabled)')
        return

    if shutil.which('hermes') is None:
        print('ℹ️  Hermes CLI not found, skip memory consolidation cron setup')
        return

    try:
        subprocess.run(['hermes', 'cron', 'list'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print('ℹ️  Hermes cron unavailable, skip memory consolidation cron setup')
        return

    cron_name = 'memory-consolidation-6h'
    prompt = (
        'Scan recent conversation transcripts (last 6 hours). '
        'Extract durable facts not already in memory or fact_store. '
        'Save genuinely new facts only (no duplicates). '
        'Skip task progress, PR numbers, and commit SHAs. '
        'Keep only facts likely useful in 30 days, then check MEMORY.md capacity and prune stale entries if needed.'
    )

    try:
        listed = subprocess.run(
            ['hermes', 'cron', 'list'],
            check=True,
            capture_output=True,
            text=True
        )
        if cron_name in (listed.stdout or ''):
            print(f'✅ Cron already exists: {cron_name}')
            return

        subprocess.run([
            'hermes', 'cron', 'create', 'every 6h',
            '--name', cron_name,
            '--prompt', prompt,
            '--deliver', 'origin',
        ], check=True)
        print(f'✅ Created optional cron: {cron_name}')
    except Exception as e:
        print(f'⚠️  Failed to create optional memory consolidation cron: {e}')

def verify():
    checks = [ARCHIVES_DIR, POOL_DB, SKILLS_DIR/'memory-starter-kit']
    for c in checks:
        print(f'  {"✅" if c.exists() else "❌"} {c.name}')

def main():
    print('=== Hermes Memory Installer 2.2 ===')
    check_hermes()
    check_python()
    check_sqlite_fts5()
    backup_config()
    create_archives()
    init_pool_db()
    install_skills()
    patch_config()
    setup_memory_consolidation_cron()
    print()
    verify()
    print()
    print('✅ Installation complete. Restart Hermes Gateway to activate.')

if __name__ == '__main__':
    main()
