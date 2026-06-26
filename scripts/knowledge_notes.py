#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

import yaml


def resolve_knowledge_notes_dir(agent_home: Path, configured_dir: Path) -> Path:
    candidates = [
        configured_dir,
        agent_home / "knowledge" / "notes",
        agent_home / "knowledge" / "wiki" / "wiki",
        agent_home / "knowledge" / "wiki",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return configured_dir


def _strip_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    try:
        meta = yaml.safe_load(raw_meta) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    return meta, body


def _normalize_note_title(path: Path, body: str, meta: dict) -> str:
    title = str(meta.get("title") or "").strip()
    if title:
        return title
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            candidate = stripped.lstrip("#").strip()
            if candidate:
                return candidate
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or path.stem


def _summarize_note_body(body: str) -> str:
    lines = []
    in_code = False
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        lines.append(stripped)
    summary = " ".join(lines)
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:1200]


def parse_knowledge_note(path: Path, root_dir: Path) -> dict | None:
    if path.suffix.lower() != ".md" or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _strip_frontmatter(text)
    title = _normalize_note_title(path, body, meta)
    summary = _summarize_note_body(body)
    if not summary:
        summary = title
    raw_tags = meta.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    source_path = str(path.relative_to(root_dir)).replace("\\", "/")
    note_id = f"note:{source_path}"
    search_text = " ".join(part for part in [title, summary, ", ".join(tags), source_path] if part)
    return {
        "note_id": note_id,
        "source_path": source_path,
        "title": title[:200],
        "summary": summary,
        "tags": tags,
        "search_text": search_text[:4000],
        "modified_at": float(path.stat().st_mtime),
    }


def build_knowledge_note_rows(notes_dir: Path, indexed_at: float) -> tuple[list[tuple], list[tuple]]:
    rows: list[tuple] = []
    fts_rows: list[tuple] = []
    if not notes_dir.exists():
        return rows, fts_rows
    for path in sorted(notes_dir.rglob("*.md")):
        parsed = parse_knowledge_note(path, notes_dir)
        if not parsed:
            continue
        tags_text = ", ".join(parsed["tags"])
        row = (
            parsed["note_id"],
            parsed["source_path"],
            parsed["title"],
            parsed["summary"],
            tags_text,
            parsed["search_text"],
            indexed_at,
            parsed["modified_at"],
        )
        rows.append(row)
        fts_rows.append(
            (
                parsed["note_id"],
                parsed["source_path"],
                parsed["title"],
                parsed["summary"],
                tags_text,
                parsed["search_text"],
            )
        )
    return rows, fts_rows


def compute_knowledge_notes_signature(notes_dir: Path) -> str:
    if not notes_dir.exists() or not notes_dir.is_dir():
        return "missing"
    parts = []
    for path in sorted(notes_dir.rglob("*.md")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(notes_dir)).replace("\\", "/")
        content_hash = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                content_hash.update(chunk)
        parts.append(f"{rel}:{content_hash.hexdigest()}")
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()


def governance_meta_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM governance_meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def refresh_knowledge_note_index(
    conn: sqlite3.Connection,
    *,
    notes_dir: Path,
    indexed_at: float,
    force: bool = False,
) -> dict:
    signature = compute_knowledge_notes_signature(notes_dir)
    previous_signature = governance_meta_value(conn, "knowledge_notes_signature")
    if not force and signature == previous_signature:
        count = conn.execute("SELECT COUNT(*) FROM knowledge_note_index").fetchone()[0]
        return {"reused": True, "count": int(count), "signature": signature}

    rows, fts_rows = build_knowledge_note_rows(notes_dir, indexed_at)
    conn.execute("DELETE FROM knowledge_note_index")
    conn.execute("DELETE FROM knowledge_note_index_fts")
    conn.executemany(
        """
        INSERT INTO knowledge_note_index (
            note_id, source_path, title, summary, tags, search_text, indexed_at, modified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.executemany(
        """
        INSERT INTO knowledge_note_index_fts (
            note_id, source_path, title, summary, tags, search_text
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        fts_rows,
    )
    conn.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('knowledge_notes_signature', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (signature,),
    )
    conn.execute(
        """
        INSERT INTO governance_meta (key, value) VALUES ('knowledge_notes_root', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(notes_dir),),
    )
    return {"reused": False, "count": len(rows), "signature": signature}
