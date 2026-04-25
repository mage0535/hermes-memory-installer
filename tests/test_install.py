#!/usr/bin/env python3
"""
安装流程测试
在隔离环境中模拟完整安装流程。
"""

import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "installer"))
from check_env import EnvChecker
from config_patch import ConfigPatcher


def test_env_checker():
    """测试环境检测"""
    checker = EnvChecker()
    checker.check_all()
    assert checker.info.get("python"), "Python 版本未检测到"
    assert checker.info.get("sqlite"), "SQLite 未检测到"
    print("✅ 环境检测通过")


def test_config_patcher():
    """测试配置修改"""
    # 创建临时 config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("skills:\n  - existing-skill\n")
        temp_path = f.name
    
    try:
        patcher = ConfigPatcher(temp_path)
        data = patcher.load()
        data = patcher.patch(data)
        
        assert "memory-starter-kit" in data["skills"], "Skill 未追加"
        assert "existing-skill" in data["skills"], "原有 Skill 丢失"
        print("✅ 配置修改通过")
    finally:
        Path(temp_path).unlink()


def test_db_init():
    """测试数据库初始化"""
    import sqlite3
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from init_db import init_db
    
    try:
        assert init_db(db_path), "数据库初始化失败"
        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "archives_fts" in tables, "FTS5 索引未创建"
        conn.close()
        print("✅ 数据库初始化通过")
    finally:
        Path(db_path).unlink()


if __name__ == "__main__":
    test_env_checker()
    test_config_patcher()
    test_db_init()
    print("\n🎉 所有测试通过")
