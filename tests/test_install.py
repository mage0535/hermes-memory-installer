#!/usr/bin/env python3
"""Installation test"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'installer'))
from install import check_hermes, check_python, check_sqlite_fts5
check_hermes()
check_python()
check_sqlite_fts5()
print('All checks passed')
