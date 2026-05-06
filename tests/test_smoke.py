#!/usr/bin/env python3
"""Smoke tests for Memory 2.0"""
import sys
from pathlib import Path

HERMES_HOME = Path.home() / '.hermes'
REPO = Path('/tmp/memory-repo')
all_ok = True

def check(desc, cond):
    print(f'{"✅" if cond else "❌"} {desc}')
    return cond

all_ok &= check('Hermes home', HERMES_HOME.exists())
all_ok &= check('config.yaml', (HERMES_HOME / 'config.yaml').exists())
all_ok &= check('pool.db', (HERMES_HOME / 'pool.db').exists())
all_ok &= check('archives/', (HERMES_HOME / 'archives').exists())
all_ok &= check('memory-starter-kit', (HERMES_HOME / 'skills/memory-starter-kit').exists())
all_ok &= check('install.sh', (REPO / 'install.sh').exists())
all_ok &= check('install.py', (REPO / 'installer/install.py').exists())
all_ok &= check('archive_sessions.py', (REPO / 'scripts/archive_sessions.py').exists())

sys.exit(0 if all_ok else 1)
