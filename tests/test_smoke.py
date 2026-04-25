#!/usr/bin/env python3
"""
Smoke Test - 验证安装是否成功
快速检查关键文件和目录是否存在。
"""

import sys
from pathlib import Path


def test():
    hermes_dir = Path.home() / ".hermes"
    checks = [
        ("config.yaml", hermes_dir / "config.yaml"),
        ("archives dir", hermes_dir / "archives"),
        ("pool.db", hermes_dir / "pool.db"),
        ("memory-starter-kit", hermes_dir / "skills" / "memory-starter-kit"),
        ("memory-archivist", hermes_dir / "skills" / "memory-archivist"),
    ]
    
    all_ok = True
    for name, path in checks:
        exists = path.exists()
        status = "✅" if exists else "❌"
        print(f"{status} {name}: {path}")
        if not exists:
            all_ok = False
    
    return all_ok


if __name__ == "__main__":
    ok = test()
    sys.exit(0 if ok else 1)
