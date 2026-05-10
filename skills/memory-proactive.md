---
description: "Proactive semantic recall: multi-layer memory retrieval (FTS5 → embeddings → gbrain) with time decay, context routing, and cross-session injection."
---

# memory-proactive: Proactive Semantic Recall

## Triggers

Load this skill when:
- The user references past work ("remember when we...", "last time we...")
- The user mentions a topic that might have prior context
- The agent needs to check if a problem was already solved before
- Cross-session continuity is needed
- The user asks "what did we do about X?" or "how did we fix Y?"

## Architecture

Three-layer recall with progressively richer (but slower) retrieval:

| Layer | Method | Latency | Strengths |
|-------|--------|---------|-----------|
| 1 | FTS5 / LIKE on `state.db` | <10ms | Exact keyword matches, session titles/summaries |
| 2 | Embedding similarity (`semantics.db`) | 50-200ms | Semantic matches, paraphrased queries |
| 3 | gbrain MCP fallback | 100-500ms | Knowledge graph connections, structured data |

All results are scored with exponential time decay (half-life: 30 days).

## Usage

### CLI

```bash
# Full 3-layer recall
python3 ~/.hermes/scripts/proactive_recall.py "nifty pre-market setup"

# FTS5 only (fastest)
python3 ~/.hermes/scripts/proactive_recall.py --ftsgrep "ollama embedding"

# JSON output for programmatic use
python3 ~/.hermes/scripts/proactive_recall.py --json "how did we fix auth"

# Limit results
python3 ~/.hermes/scripts/proactive_recall.py --top 3 "docker networking"
```

### In-session (agent use)

When the user references past context:

1. Extract key nouns/concepts from the user message
2. Run `proactive_recall.py --json --top 3 "<query>"`
3. If results have sessions with high adjusted_score (>0.3), inject relevant summaries
4. If zero results, fall back to `session_search` tool

### Time Decay Formula

```
adjusted_score = raw_score * exp(-age_days / half_life_days)
```

Default `half_life_days=30` — a session 30 days old scores at 50% of its original relevance.

## Context Routing Rules

1. If recall finds **≥2 high-scoring sessions** (adjusted > 0.5), inject ALL into context
2. If **1 moderate** (0.3–0.5), inject it + ask user for confirmation
3. If **zero relevant results**, use `session_search` as final fallback
4. Never inject more than 5 session summaries total (stays within context budget)

## Context Injection Format

When injecting recalled sessions, use this Compacted Auto-Recall format:

```
[Auto-recalled Session: <title>]
Session ID: <id> | Date: <date> | Relevance: <score>
Messages: <user_count>/<assistant_count>/<tool_count>
Summary: <summary_text>
Key Artifacts: <files/requests>

[Auto-recalled Session: ...]
```

## Pool State Integration

For completing old todos from stale archives, check pool.db:

```python
import sqlite3, json
conn = sqlite3.connect("~/.hermes/pool.db")
tasks = conn.execute("SELECT * FROM pool_tasks WHERE status='completed'").fetchall()
```

Cross-reference recalled sessions with pool.db entries to resurrect stale todos.

## File Locations

- Script: `~/.hermes/scripts/proactive_recall.py`
- State DB: `~/.hermes/state.db`
- Embeddings: `~/.hermes/semantics.db`
- Pool DB: `~/.hermes/pool.db`

## Pitfalls

- **FTS5 table may not exist**: Always catch `sqlite3.OperationalError` and fall back to LIKE
- **Embedding dimension mismatch**: If `semantics.db` has 384-dim vectors and you use a 768-dim model, skip silently
- **gbrain may not be installed**: Catch `FileNotFoundError` gracefully
- **Large state.db**: LIKE queries on 10k+ sessions can be slow — always include LIMIT
- **Time decay to zero**: Very old sessions (<0.01 score) are filtered out automatically
