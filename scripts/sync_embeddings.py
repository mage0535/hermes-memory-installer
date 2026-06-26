#!/usr/bin/env python3
"""
Legacy helper to backfill semantics.db embeddings from state.db messages.

This tool is kept for historical workflows and is not part of the default
multi-agent install set. It still honors AGENT_HOME so it can be used safely in
shared runtimes.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import struct
import sys
import time
from pathlib import Path

AGENT_HOME = Path(
    os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))
).expanduser()
STATE_DB = AGENT_HOME / "state.db"
SEMANTICS_DB = AGENT_HOME / "semantics.db"
BATCH_SIZE = 50


def deserialize(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def serialize(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def get_stats() -> None:
    sc = sqlite3.connect(STATE_DB)
    ec = sqlite3.connect(SEMANTICS_DB)

    s_emb = sc.execute("SELECT COUNT(*) FROM message_embeddings").fetchone()[0]
    e_emb = ec.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    s_msg = sc.execute(
        "SELECT COUNT(*) FROM messages WHERE content IS NOT NULL AND length(content) > 20"
    ).fetchone()[0]

    ec.execute("ATTACH DATABASE ? AS sdb", (str(STATE_DB),))
    e_gap = ec.execute(
        """
        SELECT COUNT(*) FROM sdb.messages m
        WHERE m.content IS NOT NULL AND length(m.content) > 20
          AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.message_id = m.id)
        """
    ).fetchone()[0]
    s_gap = sc.execute(
        """
        SELECT COUNT(*) FROM messages m
        WHERE m.content IS NOT NULL AND length(m.content) > 20
          AND NOT EXISTS (SELECT 1 FROM message_embeddings me WHERE me.message_id = m.id)
        """
    ).fetchone()[0]

    print(f"state.db message_embeddings: {s_emb:,}")
    print(f"semantics.db embeddings:     {e_emb:,}")
    print(f"eligible messages (>20):     {s_msg:,}")
    print(f"semantics.db gap:            {e_gap}")
    print(f"state.db gap:                {s_gap}")

    sc.close()
    ec.close()


def sync_semantics(dry_run: bool = False) -> None:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    ec = sqlite3.connect(SEMANTICS_DB)
    ec.execute("ATTACH DATABASE ? AS sdb", (str(STATE_DB),))

    rows = ec.execute(
        """
        SELECT m.id, m.session_id, m.role, m.content, m.timestamp
        FROM sdb.messages m
        WHERE m.content IS NOT NULL AND length(m.content) > 20
          AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.message_id = m.id)
        ORDER BY m.id
        """
    ).fetchall()

    total = len(rows)
    if total == 0:
        print("semantics.db is already up to date.")
        ec.close()
        return

    print(f"Backfilling {total} semantics.db embeddings...")
    t0 = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        texts = [row[3][:2000] for row in batch]
        vecs = model.encode(texts, convert_to_numpy=True).tolist()

        for row, vec in zip(batch, vecs):
            emb_blob = serialize(vec)
            content_hash = str(hash(row[3]))
            ec.execute(
                """
                INSERT OR IGNORE INTO embeddings
                (message_id, session_id, role, content_hash, embedding, content_len, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[2], content_hash, emb_blob, len(row[3]), time.time()),
            )

        if not dry_run:
            ec.commit()

        done = min(i + BATCH_SIZE, total)
        elapsed = time.time() - t0
        speed = done / elapsed if elapsed > 0 else 0
        print(f"  {done}/{total} ({done/total*100:.1f}%) - {speed:.0f} msg/s")

    if dry_run:
        ec.rollback()
        print(f"[dry-run] would have written {total} rows")

    ec.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill semantics.db embeddings from AGENT_HOME state.")
    parser.add_argument("--stats", action="store_true", help="Only print current stats")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    print("=== Embedding Sync ===")
    print(f"state.db:     {STATE_DB}")
    print(f"semantics.db: {SEMANTICS_DB}")
    print()
    get_stats()
    print()

    if args.stats:
        sys.exit(0)

    if args.dry_run:
        print("[dry-run]")
        sync_semantics(dry_run=True)
        sys.exit(0)

    print("Starting semantics.db sync...")
    sync_semantics()
    print()
    print("=== Post-sync stats ===")
    get_stats()
