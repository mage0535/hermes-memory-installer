#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

import memory_governance_rebuild as governance_rebuild
import tiered_context_injector as injector

DEFAULT_MAX_ATTEMPTS = 3


def open_governance_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(governance_rebuild.GOVERNANCE_DB), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def ensure_schema_when_unlocked(conn: sqlite3.Connection) -> bool:
    for attempt in range(3):
        try:
            governance_rebuild.ensure_schema(conn)
            return True
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= 2:
                return False
            time.sleep(0.5 * (attempt + 1))
    return False


def _json_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    return str(value or "")


def fetch_live_hindsight(query: str, timeout_s: float) -> list[dict]:
    payload = json.dumps(
        {
            "query": query,
            "types": ["world", "experience", "observation"],
            "budget": "low",
            "max_tokens": 1200,
            "trace": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        injector.HINDSIGHT_RECALL_URL,
        data=payload,
        method="POST",
        headers=injector.hindsight_headers(content_type=True),
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        body = json.loads(response.read().decode("utf-8"))
    return [item for item in body.get("results", []) if isinstance(item, dict)]


def cache_hindsight_results(conn: sqlite3.Connection, query_hash: str, results: list[dict]) -> int:
    if not ensure_schema_when_unlocked(conn):
        raise sqlite3.OperationalError("database is locked")
    now = time.time()
    inserted = 0
    for idx, item in enumerate(results):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        memory_id = str(item.get("id") or "").strip()
        if not memory_id:
            digest = hashlib.sha256(f"{query_hash}:{idx}:{text}".encode("utf-8", errors="replace")).hexdigest()[:24]
            memory_id = f"async-live:{digest}"
        fact_type = str(item.get("type") or item.get("fact_type") or "observation")
        context = str(item.get("context") or "")
        entities = _json_text(item.get("entities"))
        tags = _json_text(item.get("tags"))
        tags = f"{tags} async-live query:{query_hash[:12]}".strip()
        mentioned_at = str(item.get("mentioned_at") or item.get("created_at") or "")
        search_text = " ".join(part for part in (text, context, entities, tags) if part)
        row = (
            memory_id,
            fact_type,
            text,
            context,
            entities,
            tags,
            str(item.get("source_session_id") or ""),
            mentioned_at,
            str(item.get("occurred_start") or ""),
            str(item.get("occurred_end") or ""),
            search_text,
            now,
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO hindsight_index (
                memory_id, fact_type, text, context, entities, tags,
                source_session_id, mentioned_at, occurred_start, occurred_end,
                search_text, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        conn.execute("DELETE FROM hindsight_index_fts WHERE memory_id = ?", (memory_id,))
        conn.execute(
            """
            INSERT INTO hindsight_index_fts (
                memory_id, fact_type, text, context, entities, tags,
                source_session_id, mentioned_at, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, fact_type, text, context, entities, tags, str(item.get("source_session_id") or ""), mentioned_at, search_text),
        )
        inserted += 1
    return inserted


def classify_failure(exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timed out" in text or "timeout" in text:
        return "timeout"
    if "connection refused" in text or "connection reset" in text or "connection aborted" in text:
        return "connection"
    if "database is locked" in text or "locked" in text:
        return "database_locked"
    return "other"


def expire_exhausted_failures(conn: sqlite3.Connection, max_attempts: int) -> int:
    cursor = conn.execute(
        """
        UPDATE recall_refresh_queue
        SET updated_at = ?, status = 'expired', last_error = 'max_attempts_exhausted'
        WHERE status = 'failed'
          AND attempts >= ?
        """,
        (time.time(), max(1, int(max_attempts))),
    )
    return int(cursor.rowcount or 0)


def summarize_queue(conn: sqlite3.Connection, max_attempts: int) -> dict:
    rows = conn.execute(
        """
        SELECT status, attempts, COUNT(*) AS count
        FROM recall_refresh_queue
        GROUP BY status, attempts
        """
    ).fetchall()
    pending = 0
    retryable_failed = 0
    exhausted_failed = 0
    expired = 0
    done = 0
    other = 0
    max_attempts = max(1, int(max_attempts))
    for row in rows:
        status = str(row["status"] or "")
        attempts = int(row["attempts"] or 0)
        count = int(row["count"] or 0)
        if status == "pending":
            pending += count
        elif status == "failed" and attempts < max_attempts:
            retryable_failed += count
        elif status == "failed":
            exhausted_failed += count
        elif status == "expired":
            expired += count
        elif status == "done":
            done += count
        else:
            other += count
    return {
        "pending": pending,
        "retryable_failed": retryable_failed,
        "exhausted_failed": exhausted_failed,
        "expired": expired,
        "done": done,
        "other": other,
    }


def run_once(limit: int, timeout_s: float, max_attempts: int = 3) -> dict:
    gov_db = governance_rebuild.GOVERNANCE_DB
    conn = open_governance_connection()
    processed = 0
    cached = 0
    failed = 0
    expired = 0
    failure_buckets: dict[str, int] = {}
    try:
        if not ensure_schema_when_unlocked(conn):
            return {
                "ok": True,
                "status": "healthy",
                "processed": 0,
                "cached": 0,
                "failed": 0,
                "expired": 0,
                "failure_buckets": {},
                "queue": {},
                "skipped": "database_locked",
            }
        injector.ensure_recall_refresh_queue_table(conn)
        expired = expire_exhausted_failures(conn, max_attempts)
        rows = conn.execute(
            """
            SELECT id, query_hash, query, attempts
            FROM recall_refresh_queue
            WHERE status = 'pending'
               OR (status = 'failed' AND attempts < ?)
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (max(1, int(max_attempts)), max(1, int(limit))),
        ).fetchall()
        for row in rows:
            processed += 1
            try:
                results = fetch_live_hindsight(str(row["query"]), timeout_s=timeout_s)
                inserted = cache_hindsight_results(conn, str(row["query_hash"]), results)
                cached += inserted
                conn.execute(
                    """
                    UPDATE recall_refresh_queue
                    SET updated_at = ?, status = 'done', attempts = attempts + 1, last_error = NULL, candidate_count = ?
                    WHERE id = ?
                    """,
                    (time.time(), inserted, row["id"]),
                )
            except Exception as exc:
                failed += 1
                bucket = classify_failure(exc)
                failure_buckets[bucket] = failure_buckets.get(bucket, 0) + 1
                conn.execute(
                    """
                    UPDATE recall_refresh_queue
                    SET updated_at = ?, status = 'failed', attempts = attempts + 1, last_error = ?
                    WHERE id = ?
                    """,
                    (time.time(), str(exc)[:300], row["id"]),
                )
        conn.commit()
        queue = summarize_queue(conn, max_attempts)
    finally:
        conn.close()
    status = "healthy"
    if queue.get("pending", 0) or queue.get("retryable_failed", 0) or failed:
        status = "degraded"
    if queue.get("exhausted_failed", 0):
        status = "action-needed"
    return {
        "ok": status != "action-needed" and failed == 0,
        "status": status,
        "processed": processed,
        "cached": cached,
        "failed": failed,
        "expired": expired,
        "failure_buckets": failure_buckets,
        "queue": queue,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh weak recall queries from live Hindsight into the local cache")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args(argv)

    payload = run_once(limit=args.limit, timeout_s=args.timeout, max_attempts=args.max_attempts)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
