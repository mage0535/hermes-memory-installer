"""Hermes Memory Installer v3.0 — 4-tier memory system"""
import argparse
import os, sys, shutil, subprocess
parser = argparse.ArgumentParser()
parser.add_argument('--engine', choices=['auto','postgresql','elasticsearch','lightweight'], default='auto', help='Retrieval engine to use')
parser.add_argument('--lang', choices=['auto','en','zh'], default='auto', help='Primary language for tuning')
args = parser.parse_args()
from pathlib import Path

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
    s = '✅' if ok else '❌'
    print(f'  {s} {msg}')
    return ok

def main():
    print('╔══════════════════════════════════╗')
    print('║ Hermes Memory Installer v3.0    ║')
    print('║ 4-tier: Hot → Hindsight →      ║')
    print('║ agentmemory → gbrain           ║')
    print('╚══════════════════════════════════╝')

    # 1. Check Hermes
    step('Checking Hermes Agent')
    ok = HERMES.exists()
    check('~/.hermes directory', ok)
    if not ok:
        print('\n  Install Hermes Agent first: https://hermes-agent.nousresearch.com')
        sys.exit(1)

    # 2. Check prerequisites
    step('Checking prerequisites')
    ok_py = sys.version_info >= (3, 9)
    check(f'Python {sys.version_info.major}.{sys.version_info.minor}', ok_py)

    ok_psql = os.system('which psql >/dev/null 2>&1') == 0
    check('PostgreSQL client', ok_psql)

    ok_docker = os.system('docker ps >/dev/null 2>&1') == 0
    check('Docker (agentmemory)', ok_docker)

    ok_bun = os.system(f'test -f {TIERS["gbrain"]["bin"]}') == 0
    check('Bun (gbrain)', ok_bun)

    # 3. Install scripts
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

    # 4. Install skills
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

    # 5. Install templates
    step('Installing templates')
    dst_templates = HERMES / 'templates'
    dst_templates.mkdir(parents=True, exist_ok=True)
    src_templates = SRC / 'templates'
    if src_templates.exists():
        for tf in src_templates.glob('*.j2'):
            shutil.copy2(str(tf), str(dst_templates / tf.name))
            print(f'  ✅ {tf.name}')

    # 6. Patch config.yaml
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

    # 7. Verify
    step('Verifying installation')
    checks = [
        (dst_scripts / 'tiered_context_injector.py', 'tiered_context_injector'),
        (dst_scripts / 'hindsight-service.py', 'hindsight-service'),
        (dst_scripts / 'memory_guardian.py', 'memory_guardian'),
        (dst_skills / 'memory-starter-kit' / 'SKILL.md', 'memory-starter-kit'),
        (dst_templates, 'templates dir'),
    ]
    all_ok = True
    for p, label in checks:
        ok = p.exists()
        check(label, ok)
        if not ok:
            all_ok = False

    print(f'\n{"✅ Installation complete!" if all_ok else "⚠️  Some checks failed. Review above."}')
    print('Restart Hermes Gateway to activate all changes: systemctl restart hermes-gateway')

if __name__ == '__main__':
    main()
