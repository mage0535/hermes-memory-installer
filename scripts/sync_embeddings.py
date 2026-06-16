#!/usr/bin/env python3
"""
统一 embedding 同步脚本
双向增量同步 semantics.db ↔ state.db message_embeddings

模型分工（不可合并）：
- semantics.db      : all-MiniLM-L6-v2 (384维, 英文为主)
- state.db embed.  : text2vec-base-chinese (768维, 中文为主)

增量策略：
1. 以 state.db messages 为基准，补全两边缺失（各自用独立模型编码）
2. 各自独立增量写入，避免重复编码
3. 运行一次即可；之后 session_search_tool 写 state.db，
   EmbeddingStore.build_incremental_index 写 semantics.db

用法：
  python3 sync_embeddings.py --stats      # 仅查看统计
  python3 sync_embeddings.py --dry-run    # 预览需同步量
  python3 sync_embeddings.py              # 执行同步
"""

import argparse
import sqlite3
import struct
import sys
import time
from pathlib import Path

STATE_DB = Path.home() / ".hermes" / "state.db"
SEMANTICS_DB = Path.home() / ".hermes" / "semantics.db"
BATCH_SIZE = 50

# ── 向量序列化 ──────────────────────────────────────────────────────────────

def deserialize(blob: bytes) -> list:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def serialize(vec: list) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


# ── 统计 ────────────────────────────────────────────────────────────────────

def get_stats():
    sc = sqlite3.connect(STATE_DB)
    ec = sqlite3.connect(SEMANTICS_DB)

    s_emb = sc.execute("SELECT COUNT(*) FROM message_embeddings").fetchone()[0]
    e_emb = ec.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    s_msg = sc.execute(
        "SELECT COUNT(*) FROM messages WHERE content IS NOT NULL AND length(content) > 20"
    ).fetchone()[0]

    # 跨库 gap 查询：semantics.db embeddings 表不在 state.db，需 ATTACH
    ec.execute("ATTACH DATABASE ? AS sdb", (str(STATE_DB),))
    e_gap = ec.execute("""
        SELECT COUNT(*) FROM sdb.messages m
        WHERE m.content IS NOT NULL AND length(m.content) > 20
          AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.message_id = m.id)
    """).fetchone()[0]
    s_gap = sc.execute("""
        SELECT COUNT(*) FROM messages m
        WHERE m.content IS NOT NULL AND length(m.content) > 20
          AND NOT EXISTS (SELECT 1 FROM message_embeddings me WHERE me.message_id = m.id)
    """).fetchone()[0]

    print(f"state.db message_embeddings : {s_emb:,} 条  (text2vec-base-chinese 768维, 中文)")
    print(f"semantics.db embeddings     : {e_emb:,} 条  (all-MiniLM-L6-v2 384维, 英文)")
    print(f"有效 messages (>20字)        : {s_msg:,} 条")
    print(f"semantics.db gap (缺索引)   : {e_gap} 条")
    print(f"state.db gap (缺索引)       : {s_gap} 条")

    sc.close()
    ec.close()


# ── 增量同步 semantics.db ────────────────────────────────────────────────────

def sync_semantics(dry_run: bool = False):
    """对 state.db 中有文本但无 semantics 索引的消息补建索引"""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    ec = sqlite3.connect(SEMANTICS_DB)
    # semantics.db ATTACH state.db 以跨库查询 messages
    ec.execute("ATTACH DATABASE ? AS sdb", (str(STATE_DB),))

    rows = ec.execute("""
        SELECT m.id, m.session_id, m.role, m.content, m.timestamp
        FROM sdb.messages m
        WHERE m.content IS NOT NULL AND length(m.content) > 20
          AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.message_id = m.id)
        ORDER BY m.id
    """).fetchall()

    total = len(rows)
    if total == 0:
        print("semantics.db 已是最优状态，无 gap 需要填充")
        ec.close()
        return

    print(f"semantics.db: 补建 {total} 条缺失索引...")
    t0 = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        texts = [r[3][:2000] for r in batch]
        vecs = model.encode(texts, convert_to_numpy=True).tolist()

        for r, vec in zip(batch, vecs):
            emb_blob = serialize(vec)
            content_hash = str(hash(r[3]))
            ec.execute("""
                INSERT OR IGNORE INTO embeddings
                (message_id, session_id, role, content_hash, embedding, content_len, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (r[0], r[1], r[2], content_hash, emb_blob, len(r[3]), time.time()))

        if not dry_run:
            ec.commit()

        done = min(i + BATCH_SIZE, total)
        elapsed = time.time() - t0
        speed = done / elapsed if elapsed > 0 else 0
        print(f"  {done}/{total} ({done/total*100:.1f}%) — {speed:.0f} msg/s")

    if dry_run:
        ec.rollback()
        print(f"[dry-run] 原本将写入 {total} 条")

    ec.close()


# ── 主入口 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="同步两套 embedding 数据库")
    parser.add_argument("--stats", action="store_true", help="仅打印统计")
    parser.add_argument("--dry-run", action="store_true", help="仅报告不写入")
    args = parser.parse_args()

    print(f"=== Embedding Sync ===")
    print(f"state.db    : {STATE_DB}")
    print(f"semantics.db: {SEMANTICS_DB}")
    print()
    get_stats()
    print()

    if args.stats:
        print("统计完毕。")
        sys.exit(0)

    if args.dry_run:
        print("[dry-run 模式，仅预览]")
        sync_semantics(dry_run=True)
        sys.exit(0)

    print("开始同步 semantics.db...")
    sync_semantics()
    print()
    print("=== 同步后统计 ===")
    get_stats()
    print("同步完成。")
