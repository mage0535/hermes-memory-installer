#!/usr/bin/env python3
"""
Tiered Context Injector v3 — RRF Fusion + Feedback
===================================================
Layer 1 (L1): 最近 N 个会话摘要
Layer 2 (L2): FTS5 全文检索 × 30天半衰期
Layer 3 (L3): gbrain MCP query (与L2并行运行，非兜底)
RRF Fusion: 当L2+L3都有结果时，用Reciprocal Rank Fusion合并排序
Feedback: gbrain fb:helpful/fb:misleading/fb:outdated标签调整分数
"""

import json, math, sqlite3, os, sys, time, re
from pathlib import Path
from datetime import datetime

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
STATE_DB = HERMES_HOME / "state.db"
OUTPUT_CONTEXT = HERMES_HOME / "memories" / "TIERED_CONTEXT.md"
OUTPUT_RECALL = HERMES_HOME / "memories" / "PROACTIVE_RECALL.md"
HALF_LIFE_DAYS = 30
TOP_K_L1 = 5
TOP_K_L2 = 5
TOP_K_L3 = 3
RRF_K = 60
FEEDBACK_BOOST = 0.1
FEEDBACK_PENALTY = -0.5

# ── RRF Fusion ─────────────────────────────────────────────────────

def rrf_fuse(results_list, k=RRF_K):
    """Reciprocal Rank Fusion"""
    scores = {}
    for results in results_list:
        for i, r in enumerate(results):
            sid = r.get("session_id") or r.get("slug")
            if not sid:
                continue
            rank = i + 1
            if sid not in scores:
                scores[sid] = {"rrf_score": 0, "sources": [], "data": r.copy()}
            scores[sid]["rrf_score"] += 1.0 / (k + rank)
            scores[sid]["sources"].append(r.get("layer", "?"))
    fused = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    return fused

# ── L1: Recent Sessions ─────────────────────────────────────────────

def get_l1(limit=TOP_K_L1):
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT id, title, started_at, source, message_count
            FROM sessions WHERE parent_session_id IS NULL
            ORDER BY started_at DESC LIMIT ?
        """, (limit + 10,)).fetchall()
        results = []
        for row in rows:
            sid = row["id"]
            ts = row["started_at"]
            try:
                time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            except:
                time_str = str(ts)[:10]
            preview = "—"
            try:
                p = conn.execute("SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY timestamp ASC LIMIT 1", (sid,)).fetchone()
                if p and p["content"]:
                    preview = p["content"][:80]
            except:
                pass
            results.append({
                "session_id": sid, "time": time_str,
                "source": row["source"] or "?", "title": (row["title"] or "无主题")[:40],
                "preview": preview, "msgs": row["message_count"] or 0,
            })
            if len(results) >= limit:
                break
        return results
    finally:
        conn.close()


# ── L2: FTS5 ────────────────────────────────────────────────────────

def time_decay(ended_at, half_life=HALF_LIFE_DAYS):
    if not ended_at:
        return 1.0
    try:
        if isinstance(ended_at, (int, float)):
            ended = datetime.fromtimestamp(ended_at)
        elif isinstance(ended_at, str):
            ended = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        else:
            return 1.0
        age_days = (datetime.now() - ended).total_seconds() / 86400
        return round(math.exp(-age_days / half_life), 4) if age_days > 0 else 1.0
    except:
        return 1.0


def get_l2(query, top=TOP_K_L2):
    """FTS5 + LIKE fallback + time decay. Returns session-level results."""
    results = []
    if not STATE_DB.exists():
        return results
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    seen = set()
    try:
        fts_terms = " OR ".join(re.findall(r'\w+', query))
        if fts_terms:
            cur = conn.execute("""
                SELECT m.session_id, m.role, m.content, m.timestamp,
                       s.title, s.source, s.ended_at
                FROM messages_fts f
                JOIN messages m ON f.rowid = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE messages_fts MATCH ?
                  AND s.ended_at IS NOT NULL AND s.id NOT LIKE 'cron_%'
                ORDER BY rank LIMIT ?
            """, (fts_terms, top * 3))
            for row in cur:
                sid = row["session_id"]
                if sid in seen:
                    continue
                seen.add(sid)
                decay = time_decay(row["ended_at"])
                results.append({
                    "session_id": sid, "slug": sid,
                    "title": row["title"] or "(无标题)",
                    "snippet": (row["content"] or "")[:150],
                    "source": row["source"], "layer": "fts5",
                    "score": round(0.9 * decay, 4),
                })
                if len(results) >= top:
                    break
    except:
        pass
    if len(results) < top:
        try:
            like_pat = f"%{query}%"
            cur = conn.execute("""
                SELECT DISTINCT s.id, s.title, s.source, s.ended_at,
                       (SELECT content FROM messages WHERE session_id=s.id AND role='user' ORDER BY timestamp ASC LIMIT 1) as preview
                FROM sessions s WHERE s.ended_at IS NOT NULL AND s.id NOT LIKE 'cron_%'
                AND (s.title LIKE ? OR s.id LIKE ?)
                ORDER BY s.ended_at DESC LIMIT ?
            """, (like_pat, like_pat, top))
            for row in cur:
                sid = row["id"]
                if sid in seen:
                    continue
                seen.add(sid)
                decay = time_decay(row["ended_at"])
                results.append({
                    "session_id": sid, "slug": sid,
                    "title": row["title"] or "(无标题)",
                    "snippet": (row["preview"] or "")[:150],
                    "source": row["source"], "layer": "like",
                    "score": round(0.6 * decay, 4),
                })
                if len(results) >= top:
                    break
        except:
            pass
    conn.close()
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top]


# ── L3: gbrain Query ────────────────────────────────────────────────

def get_l3(query, top=TOP_K_L3):
    """
    L3: Multi-source semantic search.
    Source A: semantics.db (7.6k message embeddings, LIKE query)
    Source B: archives_fts (3k archive entries, FTS5 query)
    Returns fused results ranked by relevance.
    """
    results = []
    seen_slugs = set()

    # Source A: semantics.db content LIKE
    sem_db = HERMES_HOME / "semantics.db"
    if sem_db.exists():
        try:
            conn_a = sqlite3.connect(str(sem_db))
            cur_a = conn_a.execute("""
                SELECT session_id, content, content_len
                FROM embeddings WHERE content LIKE ?
                GROUP BY session_id ORDER BY MAX(indexed_at) DESC LIMIT ?
            """, (f'%{query}%', top * 2))
            for row in cur_a:
                sid = row[0]
                if sid in seen_slugs:
                    continue
                seen_slugs.add(sid)
                results.append({
                    "session_id": sid, "slug": sid,
                    "title": sid[:24] + ("..." if len(sid) > 24 else ""),
                    "snippet": (row[1] or "")[:150],
                    "source": "semantics", "layer": "semantics",
                    "score": 0.5,
                })
            conn_a.close()
        except:
            pass

    # Source B: archives_fts FTS5
    state_db = HERMES_HOME / "state.db"
    if state_db.exists():
        try:
            conn_b = sqlite3.connect(str(state_db))
            fts_terms = " OR ".join(re.findall(r'\w+', query))
            if fts_terms:
                cur_b = conn_b.execute("""
                    SELECT name, summary, category FROM archives_fts
                    WHERE archives_fts MATCH ?
                    ORDER BY rank LIMIT ?
                """, (fts_terms, top))
                for row in cur_b:
                    slug = f"archive:{row[0]}"
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    results.append({
                        "session_id": slug, "slug": slug,
                        "title": row[0][:40],
                        "snippet": (row[1] or "")[:150],
                        "source": f"archive:{row[2] or '?'}", "layer": "archive",
                        "score": 0.4,
                    })
            conn_b.close()
        except:
            pass

    # Sort by score (desc) and return top
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top]


# ── Feedback-Aware Score Adjustment ─────────────────────────────────

def adjust_with_feedback(fused_results):
    """
    Check gbrain pages for feedback tags and adjust scores.
    fb:helpful → boost score
    fb:misleading → penalize score
    fb:outdated → exclude (set score to 0)
    """
    db_path = HERMES_HOME / "gbrain" / "brain.db"
    if not db_path.exists():
        return fused_results

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        for item in fused_results:
            slug = item["data"].get("slug") or item["data"].get("session_id") or ""
            if not slug:
                continue
            try:
                row = conn.execute("SELECT tags FROM pages WHERE slug=? LIMIT 1", (slug,)).fetchone()
                if row and row["tags"]:
                    tags = row["tags"].split(",") if isinstance(row["tags"], str) else []
                    if "fb:outdated" in tags:
                        item["rrf_score"] = 0.0
                        item["feedback_note"] = "excluded (outdated)"
                    elif "fb:misleading" in tags:
                        item["rrf_score"] = max(0, item["rrf_score"] + FEEDBACK_PENALTY)
                        item["feedback_note"] = f"penalized (misleading, -{abs(FEEDBACK_PENALTY)})"
                    elif "fb:helpful" in tags:
                        item["rrf_score"] += FEEDBACK_BOOST
                        item["feedback_note"] = f"boosted (helpful, +{FEEDBACK_BOOST})"
            except:
                pass
    except:
        pass
    finally:
        conn.close()

    # Remove excluded items
    fused_results = [r for r in fused_results if r["rrf_score"] > 0]
    fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused_results


# ── Context Router ───────────────────────────────────────────────────

def route_context(fused_results, query):
    high = [r for r in fused_results if r["rrf_score"] > 0.025]
    mod = [r for r in fused_results if 0.01 <= r["rrf_score"] <= 0.025]

    if len(high) >= 2:
        return {"decision": "inject_all", "count": len(high), "sessions": high}
    elif len(mod) >= 1:
        return {"decision": "inject_one", "count": 1, "sessions": [mod[0]]}
    else:
        return {"decision": "fallback_session_search", "count": 0, "sessions": []}


# ── Generation ───────────────────────────────────────────────────────

def generate(recall_queries=None):
    OUTPUT_CONTEXT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_RECALL.parent.mkdir(parents=True, exist_ok=True)

    l1 = get_l1()
    lines = [
        "<!-- Auto-generated by tiered_context_injector.py v3 (RRF+Fusion+semantics+archives) -->",
        "",
        "## L1: 最近会话上下文",
        "",
        "| 时间 | 来源 | 主题 | 首条消息 |",
        "|------|------|------|---------|",
    ]
    for r in l1:
        lines.append(f"| {r['time']} | {r['source']} | {r['title']} | {r['preview']} |")

    if recall_queries:
        for q in recall_queries:
            lines.append(f"\n### 主动召回: {q}")

            # Run L2 + L3 in parallel, then RRF fuse
            l2 = get_l2(q)
            l3 = get_l3(q)

            if l2 or l3:
                fused = rrf_fuse([l2, l3]) if l2 and l3 else \
                        [{"rrf_score": r.pop("score", 0.5) if "score" in r else 0.5,
                          "sources": [r.get("layer","?")], "data": r} for r in (l2 or l3)]
                fused = adjust_with_feedback(fused)
                route = route_context(fused, q)

                lines.append(f"路由: {route['decision']} ({route['count']}条 | "
                             f"L2={len(l2)}条+L3={len(l3)}条"
                             f"{'→RRF' if l2 and l3 else ''})")
                for r in fused[:5]:
                    fb = r.get("feedback_note", "")
                    lines.append(
                        f"- [{r['sources']}] {r['data'].get('title','?')[:30]} | "
                        f"rrf={r['rrf_score']:.4f}{' ['+fb+']' if fb else ''}"
                    )

    lines.extend([
        "",
        "---",
        f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*L1: {len(l1)}条 | RRF: k={RRF_K} | Feedback: +{FEEDBACK_BOOST}/-{abs(FEEDBACK_PENALTY)}*",
    ])
    OUTPUT_CONTEXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tiered Context Injector v3")
    parser.add_argument("--recall", nargs="*", help="召回查询词")
    parser.add_argument("--test", help="测试单条查询并输出JSON")
    args = parser.parse_args()

    if args.test:
        l2 = get_l2(args.test)
        l3 = get_l3(args.test)
        fused = rrf_fuse([l2, l3]) if l2 and l3 else [{"rrf_score": 0, "sources": ["?"], "data": {"title": "no results"}}]
        fused = adjust_with_feedback(fused)
        print(json.dumps({
            "query": args.test,
            "l2_count": len(l2),
            "l3_count": len(l3),
            "fused": [{"slug": r["data"].get("slug",""), "rrf": r["rrf_score"],
                       "sources": r["sources"],
                       "fb": r.get("feedback_note","")} for r in fused[:5]],
        }, ensure_ascii=False, indent=2))
        return

    n = generate(recall_queries=args.recall)
    import sys
    sys.stderr.write(f"TIERED_CONTEXT.md updated ({n} lines)\n")
    print(f"TIERED_CONTEXT.md updated ({n} lines)")

if __name__ == "__main__":
    main()
