#!/usr/bin/env python3
"""
Hermes Memory Installer - 数据库初始化脚本
创建 pool.db ，包含 P6-1 级别的索引结构。

功能：
1. 创建对话归档表 (conversations)
2. 创建档案索引表 (archives)
3. 创建 FTS5 全文检索索引
4. 创建触发器自动维护索引
5. 验证索引健康状态
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

SCHEMA_SQL = """
-- 对话归档表
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    timestamp   REAL DEFAULT (julianday('now')),
    role        TEXT NOT NULL,        -- 'user' / 'assistant' / 'system'
    content     TEXT NOT NULL,
    topic_tags  TEXT,                 -- JSON 数组，主题标签
    archived    INTEGER DEFAULT 0,    -- 是否已归档
    
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 会话表（简单版）
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    start_time  REAL DEFAULT (julianday('now')),
    title       TEXT,                 -- 自动生成的标题
    summary     TEXT,                 -- 对话摘要
    archived    INTEGER DEFAULT 0
);

-- 档案索引表
CREATE TABLE IF NOT EXISTS archives (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL UNIQUE,  -- 相对于 ~/.hermes/archives/ 的路径
    type        TEXT NOT NULL,         -- 'person' / 'project' / 'knowledge'
    title       TEXT,
    summary     TEXT,                  -- 档案摘要
    tags        TEXT,                  -- JSON 数组
    last_read   REAL,                  -- 最后被读取时间
    priority    INTEGER DEFAULT 0,     -- 优先级，高的先加载
    
    CHECK (type IN ('person', 'project', 'knowledge'))
);

-- FTS5 全文检索索引
CREATE VIRTUAL TABLE IF NOT EXISTS archives_fts USING fts5(
    title,
    summary,
    tags,
    content=archives,
    content_rowid=id
);

-- 触发器：archives 变更时自动更新 FTS5
CREATE TRIGGER IF NOT EXISTS archives_ai AFTER INSERT ON archives BEGIN
    INSERT INTO archives_fts(rowid, title, summary, tags)
    VALUES (new.id, new.title, new.summary, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS archives_ad AFTER DELETE ON archives BEGIN
    INSERT INTO archives_fts(archives_fts, rowid, title, summary, tags)
    VALUES ('delete', old.id, old.title, old.summary, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS archives_au AFTER UPDATE ON archives BEGIN
    INSERT INTO archives_fts(archives_fts, rowid, title, summary, tags)
    VALUES ('delete', old.id, old.title, old.summary, old.tags);
    INSERT INTO archives_fts(rowid, title, summary, tags)
    VALUES (new.id, new.title, new.summary, new.tags);
END;

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_conversations_session 
    ON conversations(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_archives_type 
    ON archives(type, priority DESC);
CREATE INDEX IF NOT EXISTS idx_archives_tags 
    ON archives(json_extract(tags, '$'));
"""


def init_db(db_path: Optional[str] = None) -> bool:
    """初始化数据库"""
    if db_path is None:
        db_path = str(Path.home() / ".hermes" / "pool.db")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        
        # 验证
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required = ["conversations", "sessions", "archives", "archives_fts"]
        for table in required:
            if table not in tables:
                print(f"❌ 缺少表: {table}")
                return False
        
        print(f"✅ 数据库初始化成功: {db_path}")
        print(f"   表: {', '.join(tables)}")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    success = init_db(db_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
