# Hermes Memory Installer 2.0 --- Architecture Document

*Version: v2.0.0 | Target: Developers / Technical Decision Makers*

---

## 1. Product Positioning

Empower any Hermes user to deploy a production-grade memory management system in under 5 minutes.

**Not**:
- A replacement for Hermes' native memory mechanisms
- A system requiring core code modifications
- A cloud service needing external API keys

**Is**:
- A three-layer architecture leveraging Hermes' existing capabilities
- A one-click environment setup tool
- An automated pipeline for memory maintenance

---

## 2. Three-Layer Architecture

### Dialog Layer (Gateway)

The Hermes Gateway handles all user interactions. Every message triggers the memory recall pipeline before reaching the LLM:

1. **Layer 1 (FTS5)**: Search state.db session transcripts using FTS5 full-text index --- millisecond latency, precise keyword matching
2. **Layer 2 (Semantic)**: Embedding similarity search using `paraphrase-multilingual-MiniLM-L12-v2` --- agent-local first, cross-platform fallback
3. **Layer 3 (Graph)**: gbrain knowledge graph vector search --- semantic and graph traversal, triggered when Layer 1-2 results are insufficient

### Skill Layer (Hermes Skills)

| Skill | Required | Function |
|-------|----------|----------|
| **memory-starter-kit** | Yes Required | Archive templates, directory structure, usage guide |
| **memory-archivist** | Yes Recommended | Auto-archive cron jobs, FTS5 indexing, retention management |
| **memory-proactive** | No Optional | Context routing, topic detection, semantic recall injection |
| **curator** | Self-evolve | Knowledge governance, insight extraction, skill refinement |

### Data Layer

| Store | Technology | Purpose |
|-------|-----------|---------|
| `state.db` | SQLite + FTS5 | Real-time session store with full-text search |
| `pool.db` | SQLite + FTS5 | Archive index for long-term reference |
| `archives/` | Markdown files | Human-readable archive library |
| `semantics.db` | SQLite + vectors | Embedding storage for semantic search |
| **gbrain** (new) | Postgres/PGlite + pgvector | Knowledge graph with vector + keyword search |

---

## 3. Data Flow

```
+-----------------------------------------------------------+
|                    Online Path                             |
|  User Message                                              |
|     |                                                      |
|  +-----------------------------------------------+        |
|  | Layer 1: FTS5 Recall (state.db, ms level)     |        |
|  | - Full-text search across all past sessions   |        |
|  | - Returns exact keyword matches               |        |
|  +------------------+----------------------------+        |
|                     |                                      |
|  +-----------------------------------------------+        |
|  | Layer 2: Semantic Recall (embeddings)          |        |
|  | - Agent-local: filter by source:user_id        |        |
|  | - Cross-platform: global fallback              |        |
|  | - Time decay: adjusted_score = sim x exp(-d/30)|       |
|  +------------------+----------------------------+        |
|                     |                                      |
|  +-----------------------------------------------+        |
|  | Layer 3: gbrain Knowledge Graph (fallback)    |        |
|  | - Vector similarity search                     |        |
|  | - Graph traversal for related entities         |        |
|  | - Hybrid: vector + keyword                     |        |
|  +------------------+----------------------------+        |
|                     |                                      |
|  AI Response with memory context                           |
+-------------------+---------------------------------------+
|                   |                                        |
|                    Offline Pipeline                         |
|                                                              |
|  Finished Sessions                                           |
|     |                                                        |
|  +--------------------------------------------+             |
|  | auto_session_summary.py (every 12h)        |             |
|  | - Batch process 2 sessions per run         |             |
|  | - LLM-generated concise summaries          |             |
|  | - Writes to sessions.summary column        |             |
|  +------------------+-------------------------+             |
|                     |                                        |
|  +--------------------------------------------+             |
|  | archive_sessions.py (daily 3AM)            |             |
|  | - Reads state.db finished sessions         |             |
|  | - Creates gbrain pages + timeline          |             |
|  | - Watermark-based incremental              |             |
|  | - Configurable batch (15/run)              |             |
|  +------------------+-------------------------+             |
|                     |                                        |
|  +--------------------------------------------+             |
|  | curator_runner.py (daily)                  |             |
|  | - Knowledge governance and refactoring     |             |
|  | - Insight extraction from archives         |             |
|  | - Skill improvement recommendations        |             |
|  +--------------------------------------------+             |
+-----------------------------------------------------------+
```

---

## 4. Dual-Path Search Engine

### Path A: SQLite FTS5 (state.db)
- **Latency**: < 10ms
- **Strengths**: Exact keyword match, handles Chinese names/projects well
- **Trigger**: Session search tool, auto-loaded by session-search-tool skill
- **Scales to**: Millions of messages

### Path B: gbrain Vector + Hybrid
- **Latency**: ~500ms - 3s
- **Strengths**: Semantic understanding, graph traversal, cross-entity discovery
- **Trigger**: Fallback when Path A returns < 3 relevant results
- **Storage**: Postgres/PGlite + pgvector

### Fallback Chain
```
User query -> Path A (FTS5) -> results >= 3? -> YES -> return
                                           -> NO  -> Path B (gbrain) -> return merged results
```

---

## 5. Pipeline Components

### archive_sessions.py
Reads finished sessions from Hermes' `state.db`, creates structured pages in gbrain with timeline entries. Uses a watermark cursor for incremental processing --- each run picks up where the last left off.

### auto_session_summary.py
Generates LLM-powered summaries for finished sessions. Runs every 12 hours, processes 2 sessions per batch with 45s timeout each. ThreadPoolExecutor + asyncio in a fresh event loop per call.

### sync_embeddings.py
Bidirectional sync between `semantics.db` and `state.db` embedding tables. Two independent models: `all-MiniLM-L6-v2` (384-dim, English) and `text2vec-base-chinese` (768-dim, Chinese).

### curator_runner.py
Daily self-evolution cycle. Triggers the curator skill to review recent archives, extract insights, refactor knowledge, and improve the skill library.

---

## 6. Self-Evolution Cycle

```
Collect -> Summarize -> Archive -> Curate -> Learn -> Repeat
   |             |              |            |           |
   v             v              v            v           v
 sessions    summaries      gbrain      knowledge    skill
 harvested    generated     pages       refactored   improved
```

The cycle runs daily via cron. Each phase feeds into the next, creating a continuous improvement loop.

---

## 7. Directory Structure

```
~/.hermes/
|-- config.yaml              # Main config (with skills added)
|-- state.db                 # Session store (Hermes native + Memory 2.0 enhancements)
|-- pool.db                  # Archive index (FTS5)
|-- semantics.db             # Embedding storage
|-- archives/                # Markdown archive library
|   |-- people/              # People profiles
|   |-- projects/            # Project archives
|   |-- knowledge/           # Knowledge base
|   |-- _index/              # Index metadata
|-- skills/
|   |-- memory-starter-kit/  # Required: templates + guide
|   |-- memory-archivist/    # Recommended: auto archive
|   |-- memory-proactive/    # Optional: context routing
|-- scripts/                 # Automation scripts
    |-- archive_sessions.py
    |-- auto_session_summary.py
    |-- sync_embeddings.py
    |-- archive_daily.sh
    |-- curator_runner.py
```

---

## 8. Memory 2.0 vs Memory 1.0

| Aspect | Memory 1.0 | Memory 2.0 |
|--------|-----------|-----------|
| Search | FTS5 only | FTS5 + Vector + Graph (triple path) |
| Knowledge Engine | None | gbrain (pgvector) |
| Summarization | None | auto_session_summary.py (LLM) |
| Self-Evolution | None | curator + skill autopilot |
| Cross-Platform | Same platform only | Agent-local + cross-platform recall |
| Automation | Basic cron | Cron + watermark + incremental |
| Embedding | None | sentence-transformers dual model |
| Observability | File system | gbrain health + dashboard |

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| gbrain not installed | Layer 3 unavailable | Graceful fallback to FTS5 only |
| state.db schema migration | Data loss | ALTER TABLE with try/except |
| Embedding model download | Slow first run | Cached in ~/.cache/huggingface/ |
| Cron job collision | Resource contention | Configurable time windows |
| Token exhaustion | Archives fail | Per-session timeout + batch limits |

---

## 10. Roadmap

| Phase | Deliverable |
|-------|------------|
| v1.0 | FTS5 retrieval, 3 skills, one-click install |
| v2.0 | gbrain integration, dual-path search, auto-summary, curator |
| v2.1 (upcoming) | Multi-agent shared memory, conflict resolution |
| v2.2 (upcoming) | Real-time embedding sync, graph visualization |
| v3.0 (upcoming) | Distributed memory, federation protocol |

---

*Last updated: 2026-05-06*


## 11. Credits and References

Memory 2.0 builds upon ideas and code from the following projects:

| Project | What We Used |
|---------|-------------|
| **[mem0](https://github.com/mem0ai/mem0)** | Memory layering concept (user/session/system) |
| **[LangChain Memory](https://python.langchain.com/docs/modules/memory/)** | Hybrid retrieval strategy (buffer + vector store) |
| **[Obsidian](https://obsidian.md/)** | Local-first Markdown archive philosophy |
| **[SQLite FTS5](https://sqlite.org/fts5.html)** | Embedded full-text search engine |
| **[Karpathy's llm-wiki](https://github.com/karpathy/llm-wiki)** | Personal knowledge base organization |
| **[gbrain](https://github.com/garrytan/gbrain)** | Knowledge graph engine (MCP-based, pgvector) |
| **[sentence-transformers](https://sbert.net/)** | Embedding models for semantic search |

**Special thanks** to the Hermes Agent team at Nous Research for the native memory,
skill, and MCP extension APIs that make zero-intrusion deployment possible.

*Memory 2.0 was developed iteratively on a production Hermes Agent instance running
on Linux, processing 700+ sessions and 10,000+ messages in daily operation.*
