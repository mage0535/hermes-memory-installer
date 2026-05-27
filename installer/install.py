"""Hermes Memory Installer v3.0 — 4-tier memory system with model selection"""

import argparse, json, os, sys, shutil, subprocess
from pathlib import Path

# ── Model registry ──────────────────────────────────────────────────
EMBEDDING_MODELS = {
    '1':  ('BAAI/bge-base-en-v1.5',          'English',              '768d',    '133MB',  '⭐ EN default'),
    '2':  ('BAAI/bge-small-en',               'English',              '384d',    '33MB',   'Lightweight EN'),
    '3':  ('BAAI/bge-large-en-v1.5',          'English',              '1024d',   '1.34GB', 'Max EN accuracy'),
    '4':  ('all-MiniLM-L6-v2',                'English',              '384d',    '23MB',   'Tiniest EN'),
    '5':  ('BAAI/bge-large-zh-v1.5',          'Chinese',              '1024d',   '1.34GB', '⭐ CN best'),
    '6':  ('BAAI/bge-small-zh-v1.5',          'Chinese',              '512d',    '45MB',   'Lightweight CN'),
    '7':  ('text2vec-large-chinese',          'Chinese',              '768d',    '1.2GB',  'CN FAQ'),
    '8':  ('paraphrase-multilingual-MiniLM-L12-v2', '50+ languages',  '768d',    '470MB',  'Multi 50lang'),
    '9':  ('intfloat/multilingual-e5-small',  '100+ languages',       '384d',    '118MB',  '⭐ Multi budget'),
    '10': ('intfloat/multilingual-e5-base',   '100+ languages',       '768d',    '278MB',  '⭐ Multi enterprise'),
}

LANG_MODEL_MAP = {
    'en':  'BAAI/bge-base-en-v1.5',
    'zh':  'BAAI/bge-large-zh-v1.5',
    'auto': 'BAAI/bge-small-en',
}

parser = argparse.ArgumentParser(description='Hermes Memory Installer v3.0')
parser.add_argument('--engine', choices=['auto','postgresql','elasticsearch','lightweight'],
                    default='auto', help='Retrieval engine to use')
parser.add_argument('--lang', choices=['auto','en','zh'], default='auto',
                    help='Primary language for tuning')
parser.add_argument('--embedding', default=None,
                    help='HuggingFace model ID (e.g. BAAI/bge-large-zh-v1.5). '
                         'Omit for interactive picker.')
parser.add_argument('--noninteractive', action='store_true',
                    help='Skip interactive prompts (use --embedding or default)')
args = parser.parse_args()

HERMES = Path.home() / '.hermes'
SRC = Path(__file__).resolve().parent.parent

TIERS = {
    'hindsight': {
        'desc': 'Hindsight Memory Server (PostgreSQL PG16)',
        'bin': '/usr/bin/pg_isready',
        'install': 'apt install -y postgresql-16',
        'service': 'hindsight',
        'env_var': 'DATABASE_URL',
    },
    'agentmemory': {
        'desc': 'agentmemory MCP Server (Docker)',
        'bin': '/usr/bin/docker',
        'install': None,
        'service': 'docker',
        'port': 3111,
    },
    'gbrain': {
        'desc': 'gbrain Knowledge Graph (Bun + PostgreSQL)',
        'bin': '/root/.bun/bin/bun',
        'install': 'curl -fsSL https://bun.sh/install | bash',
        'service': 'gbrain-embed',
    },
}


def step(msg):
    print(f'\n  → {msg}')

def check(msg, ok):
    print(f'  {"✅" if ok else "❌"} {msg}')
    return ok

def detect_ai_assistant():
    """Detect if running under an AI assistant (non-interactive TTY)."""
    return not sys.stdin.isatty() or os.environ.get('AI_ASSISTED') == '1'

def select_embedding_model():
    """Interactive model picker (v2.1.1-style). Returns model ID string."""

    if args.embedding:
        print(f'  📦 Model specified via --embedding: {args.embedding}')
        return args.embedding

    if args.noninteractive:
        model = LANG_MODEL_MAP.get(args.lang, LANG_MODEL_MAP['auto'])
        print(f'  🤖 Non-interactive mode → {model}')
        return model

    # AI assistant guard (v2.1.1 feature)
    if detect_ai_assistant():
        print()
        print('  ╔══════════════════════════════════════════════════════╗')
        print('  ║  ⚠️  AI assistant detected                        ║')
        print('  ║                                                    ║')
        print('  ║  Please confirm with the user:                     ║')
        print('  ║  1. What language(s) does the user need?           ║')
        print('  ║  2. Available disk space and RAM on the server?    ║')
        print('  ║  3. Select the matching model number below         ║')
        print('  ║                                                    ║')
        print('  ║  After confirmation, set env var and re-run:       ║')
        print('  ║  export EMBEDDING_MODEL=<model-id>                 ║')
        print('  ║  python3 installer/install.py                     ║')
        print('  ║                                                    ║')
        print('  ║  If user already specified, press Enter to continue ║')
        print('  ╚══════════════════════════════════════════════════════╝')
        input('  Press Enter to confirm model choice with user, or Ctrl+C to abort: ')

        env_model = os.environ.get('EMBEDDING_MODEL')
        if env_model:
            print(f'  📦 Using EMBEDDING_MODEL from env: {env_model}')
            return env_model

    # Show menu
    print()
    print('  ╔══════════════════════════════════════════════════════╗')
    print('  ║  📊 Select Embedding Model                          ║')
    print('  ╠══════════════════════════════════════════════════════╣')
    print('  ║  Different models vary in language support,         ║')
    print('  ║  accuracy, and resource usage.                      ║')
    print('  ║  If unsure, choose 1 (recommended default).         ║')
    print('  ╚══════════════════════════════════════════════════════╝')
    print()

    for key in sorted(EMBEDDING_MODELS.keys(), key=int):
        name, lang, dim, size, tag = EMBEDDING_MODELS[key]
        star = '⭐ ' if '⭐' in tag else '   '
        print(f'  {key:>2}) {star}{name}')
        print(f'     {dim} | {lang} | {size}  |  {tag.replace("⭐ ","")}')
        print()

    print('  c) Custom — enter any HuggingFace model ID')
    print()

    choice = input('  Please select [1-10/c] (default: 1): ').strip()
    choice = choice or '1'

    if choice.lower() == 'c':
        custom = input('  Enter HuggingFace model ID (e.g. Alibaba-NLP/gte-multilingual-base): ').strip()
        return custom or 'BAAI/bge-base-en-v1.5'

    if choice in EMBEDDING_MODELS:
        return EMBEDDING_MODELS[choice][0]

    print(f'  ⚠️  Invalid choice "{choice}", using default')
    return EMBEDDING_MODELS['1'][0]


def main():
    print('╔══════════════════════════════════════════════════╗')
    print('║     🧠  Hermes Memory Installer v3.0            ║')
    print('║     4-tier: Hot → Hindsight →                   ║')
    print('║     agentmemory → gbrain                        ║')
    print('╚══════════════════════════════════════════════════╝')

    # ── 0. Select embedding model ──────────────────────────────
    step('Selecting embedding model')
    embed_model = select_embedding_model()
    check(f'Embedding model: {embed_model}', True)

    # ── 1. Check Hermes ────────────────────────────────────────
    step('Checking Hermes Agent')
    ok = HERMES.exists()
    check('~/.hermes directory', ok)
    if not ok:
        print('\n  Install Hermes Agent first: https://hermes-agent.nousresearch.com')
        sys.exit(1)

    # ── 2. Check prerequisites ────────────────────────────────
    step('Checking prerequisites')
    ok_py = sys.version_info >= (3, 9)
    check(f'Python {sys.version_info.major}.{sys.version_info.minor}', ok_py)

    ok_psql = os.system('which psql >/dev/null 2>&1') == 0
    check('PostgreSQL client', ok_psql)

    ok_docker = os.system('docker ps >/dev/null 2>&1') == 0
    check('Docker (agentmemory)', ok_docker)

    ok_bun = os.system(f'test -f {TIERS["gbrain"]["bin"]}') == 0
    check('Bun (gbrain)', ok_bun)

    # ── 3. Install scripts ────────────────────────────────────
    step('Installing runtime scripts')
    dst_scripts = HERMES / 'scripts'
    dst_scripts.mkdir(parents=True, exist_ok=True)
    src_scripts = SRC / 'scripts'
    installed = 0
    for f in sorted(src_scripts.glob('*.py')):
        dst = dst_scripts / f.name
        shutil.copy2(str(f), str(dst))
        if os.access(str(f), os.X_OK):
            dst.chmod(0o755)
        installed += 1
    print(f'  ✅ {installed} scripts installed to {dst_scripts}')

    # ── 4. Install skills ─────────────────────────────────────
    step('Installing skills')
    dst_skills = HERMES / 'skills'
    dst_skills.mkdir(parents=True, exist_ok=True)
    src_skills = SRC / 'skills'
    for skill_dir in sorted(src_skills.iterdir()):
        if skill_dir.is_dir() and (skill_dir / 'SKILL.md').exists():
            dst = dst_skills / skill_dir.name
            if not dst.exists():
                shutil.copytree(str(skill_dir), str(dst))
            else:
                shutil.copy2(str(skill_dir / 'SKILL.md'), str(dst / 'SKILL.md'))
                for sub in ['references', 'templates', 'scripts', 'assets']:
                    sd = skill_dir / sub
                    if sd.exists():
                        dd = dst / sub
                        dd.mkdir(exist_ok=True)
                        for sf in sd.iterdir():
                            shutil.copy2(str(sf), str(dd / sf.name))
            print(f'  ✅ {skill_dir.name}')

    # ── 5. Install templates ─────────────────────────────────
    step('Installing templates')
    dst_templates = HERMES / 'templates'
    dst_templates.mkdir(parents=True, exist_ok=True)
    src_templates = SRC / 'templates'
    if src_templates.exists():
        for tf in src_templates.glob('*.j2'):
            shutil.copy2(str(tf), str(dst_templates / tf.name))
            print(f'  ✅ {tf.name}')

    # ── 6. Patch config.yaml ────────────────────────────────
    step('Patching config.yaml')
    cfg = HERMES / 'config.yaml'
    if cfg.exists():
        try:
            from ruamel.yaml import YAML
            yaml = YAML(); yaml.preserve_quotes = True
            with open(str(cfg)) as f:
                data = yaml.load(f) or {}
        except ImportError:
            import yaml
            with open(str(cfg)) as f:
                data = yaml.safe_load(f) or {}

        if 'memory' not in data:
            data['memory'] = {}
        data['memory']['provider'] = 'hindsight'

        if 'skills' not in data:
            data['skills'] = []
        existing = set(data.get('skills', []))
        for skill in ['memory-starter-kit', 'memory-archivist', 'memory-proactive']:
            if skill not in existing:
                data['skills'].append(skill)

        if 'mcp_servers' not in data:
            data['mcp_servers'] = {}
        if 'agentmemory' not in data['mcp_servers']:
            data['mcp_servers']['agentmemory'] = {
                'command': 'npx',
                'args': ['-y', '@agentmemory/mcp'],
                'env': {'AGENTMEMORY_URL': 'http://localhost:3111'},
                'timeout': 120,
                'connect_timeout': 30,
            }

        try:
            from ruamel.yaml import YAML
            yaml = YAML(); yaml.default_flow_style = False
            with open(str(cfg), 'w') as f:
                yaml.dump(data, f)
        except ImportError:
            import yaml
            with open(str(cfg), 'w') as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        print('  ✅ config.yaml updated')

    # ── 7. Write embedding config ────────────────────────────
    step('Writing embedding model config')
    embed_cfg = HERMES / 'scripts' / 'embedding_config.json'
    with open(str(embed_cfg), 'w') as f:
        json.dump({'model': embed_model, 'device': 'cpu'}, f, indent=2)
    check(f'embedding_config.json → {embed_model}', embed_cfg.exists())

    # Chinese-specific hints
    is_zh = (args.lang == 'zh' or
             args.lang == 'auto' and 'zh' in embed_model.lower())
    if is_zh:
        print('  💡 Chinese language detected: consider installing zhparser')
        print('     apt install postgresql-16-zhparser')
        print('     CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);')

    # ── 8. Verify ────────────────────────────────────────────
    step('Verifying installation')
    checks = [
        (dst_scripts / 'tiered_context_injector.py', 'tiered_context_injector'),
        (dst_scripts / 'hindsight-service.py', 'hindsight-service'),
        (dst_scripts / 'memory_guardian.py', 'memory_guardian'),
        (dst_skills / 'memory-starter-kit' / 'SKILL.md', 'memory-starter-kit'),
        (dst_templates, 'templates dir'),
        (embed_cfg, f'embedding config ({embed_model})'),
    ]
    all_ok = True
    for p, label in checks:
        ok = p.exists()
        check(label, ok)
        if not ok:
            all_ok = False

    # Summary
    print()
    print('  ╔══════════════════════════════════════════════════╗')
    print(f'  ║  {"✅ Installation complete!" if all_ok else "⚠️  Some checks failed"}  ║')
    print(f'  ║  Embedding model: {embed_model[:38]:38s}║')
    print('  ╠══════════════════════════════════════════════════╣')
    print('  ║  Restart Gateway to activate:                    ║')
    print('  ║  systemctl restart hermes-gateway                ║')
    print('  ╚══════════════════════════════════════════════════╝')


if __name__ == '__main__':
    main()
