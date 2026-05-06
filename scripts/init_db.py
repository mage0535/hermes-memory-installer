#!/usr/bin/env python3
"""Initialize/upgrade memory databases for Memory 2.0"""
import sqlite3
from pathlib import Path

HERMES_HOME = Path.home() / '.hermes'

def init_pool_db():
    db_path = HERMES_HOME / 'pool.db'
    conn = sqlite3.connect(str(db_path))
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
    print(f'✅ pool.db ready at {db_path}')

def init_state_db_schema():
    state_db = HERMES_HOME / 'state.db'
    if not state_db.exists():
        print('ℹ️  state.db not found')
        return
    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
        print('✅ Added summary column to sessions')
    except sqlite3.OperationalError:
        pass
    conn.close()

def main():
    print('=== Memory 2.0 Database Init ===')
    init_pool_db()
    init_state_db_schema()
    print('Done.')

if __name__ == '__main__':
    main()
