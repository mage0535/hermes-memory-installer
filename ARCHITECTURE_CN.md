# Hermes Memory Installer 2.0 --- Architecture Design Document (Chinese)

*Version: v2.0.0 | Target Audience: Developers / Technical Decision Makers*

---

## 1. Product Positioning

Let any Hermes user deploy a production-grade memory management system in 5 minutes.

**Not**:
- A replacement for Hermes native memory mechanism
- A solution requiring core code modifications
- A cloud service needing external servers or API keys

**Is**:
- A three-layer architecture leveraging Hermes' existing capabilities
- A one-click environment setup tool
- An automated memory maintenance pipeline

---

## 2. Three-Layer Architecture

### Dialog Layer (Gateway)

Hermes Gateway handles all user interactions. Each message triggers the memory recall pipeline before reaching the LLM:

1. **Layer 1 (FTS5)**: Full-text search in state.db session records --- millisecond latency, precise keyword matching, friendly to Chinese names/projects
2. **Layer 2 (Semantic)**: Embedding similarity search based on paraphrase-multilingual-MiniLM-L12-v2 --- agent-local first, cross-platform fallback
3. **Layer 3 (Graph)**: gbrain knowledge graph vector search --- semantic understanding + graph traversal, triggered when first two layers have insufficient results

### Skill Layer (Hermes Skills)

| Skill | Required | Function |
|-------|----------|----------|
| **memory-starter-kit** | Yes Required | Archive templates, directory structure, usage guide |
| **memory-archivist** | Yes Recommended | Auto-archive cron, FTS5 indexing, retention policy |
| **memory-proactive** | No Optional | Context routing, topic detection, semantic recall injection |
| **curator** | Self-evolve | Knowledge governance, insight extraction, skill optimization |

### Data Layer

| Store | Technology | Purpose |
|-------|-----------|---------|
| `state.db` | SQLite + FTS5 | Real-time session storage + full-text search |
| `pool.db` | SQLite + FTS5 | Archive index |
| `archives/` | Markdown files | Human-readable archive library |
| `semantics.db` | SQLite + vectors | Embedding storage |
| **gbrain** (new) | Postgres/PGlite + pgvector | Knowledge graph + hybrid search |

---

## 3. Data Flow

### Online Path (Real-time retrieval)

```
User Message arrives at Gateway
  |
  +- Layer 1: FTS5 (state.db, <10ms)
  +- Layer 2: Semantic (embeddings, ~50-200ms)
  +- Layer 3: gbrain Knowledge Graph (~500ms-3s)
  |
  v
AI Response with enriched memory context
```

### Offline Pipeline (Background processing)

```
Finished Sessions (state.db)
  +-- auto_session_summary.py (every 12h)
  +-- archive_sessions.py (daily 3AM)
  +-- gbrain_maintain.sh (daily 4AM)
  +-- gbrain_search.py (on-demand, concurrent)
```

See ARCHITECTURE.md for full details.

## 4. Dual-Path Search Engine

### Path A: SQLite FTS5 (state.db)
- **Latency**: < 10ms
- **Advantage**: Precise keyword matching, friendly to Chinese names/projects
- **Trigger**: session_search tool, auto-loaded by session-search-tool skill
- **Scale**: Supports millions of messages

### Path B: gbrain Vector + Hybrid Search
- **Latency**: ~500ms - 3s
- **Advantage**: Semantic understanding, graph traversal, cross-entity discovery
- **Trigger**: Falls back when Path A returns < 3 relevant results
- **Storage**: Postgres/PGlite + pgvector

---

## 5. Pipeline Components

### archive_sessions.py
Reads completed sessions from state.db, creates structured pages and timeline entries in gbrain. Uses watermark cursor for incremental processing.

### auto_session_summary.py
Generates LLM-driven summaries for completed sessions. Runs every 12 hours, processes 2 sessions per batch (45s timeout). Uses ThreadPoolExecutor + asyncio.

### sync_embeddings.py
Bidirectional sync of semantics.db and state.db embedding tables. Dual model: all-MiniLM-L6-v2 (English) + text2vec-base-chinese (Chinese).

### curator_runner.py
Daily self-evolution cycle. Triggers curator skill to review recent archives, extract insights, refactor knowledge, and improve skill library.

---

## 6. Self-Evolution Cycle

```
Collect -> Summarize -> Archive -> Curate -> Learn -> Repeat
```

Runs daily via cron, forming a continuous improvement loop.

---

## 7. Directory Structure

```
~/.hermes/
|-- config.yaml
|-- state.db
|-- pool.db
|-- semantics.db
|-- archives/
|   |-- people/
|   |-- projects/
|   |-- knowledge/
|   |-- _index/
|-- skills/
|   |-- memory-starter-kit/
|   |-- memory-archivist/
|   |-- memory-proactive/
|-- scripts/
    |-- archive_sessions.py
    |-- auto_session_summary.py
    |-- sync_embeddings.py
    |-- archive_daily.sh
    |-- curator_runner.py
```

---

## 8. Risk and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| gbrain not installed | Layer 3 unavailable | Graceful degradation to FTS5 only |
| state.db migration | Data loss | try/except wrapping ALTER TABLE |
| Embedding model download | Slow first run | Cache to ~/.cache/huggingface/ |
| Token exhaustion | Archive failure | Per-session timeout + batch limits |

---

## 9. Roadmap

| Phase | Deliverable |
|-------|------------|
| v1.0 (done) | FTS5 retrieval, 3 Skills, one-click install |
| v2.0 (done) | gbrain integration, dual-path search, auto-summary, curator |
| v2.1 (upcoming) | Multi-agent shared memory, conflict resolution |
| v2.2 (upcoming) | Real-time embedding sync, graph visualization |
| v3.0 (upcoming) | Distributed memory, federation protocol |

---

*Last updated: 2026-05-06*


## 11. 参考与致谢

记忆体2.0 参考并借鉴了以下优秀项目：

| 项目 | 借鉴内容 |
|------|---------|
| **[mem0](https://github.com/mem0ai/mem0)** | 记忆分层概念（用户/会话/系统） |
| **[LangChain Memory](https://python.langchain.com/docs/modules/memory/)** | 混合检索策略（buffer + vector store） |
| **[Obsidian](https://obsidian.md/)** | 本地优先 Markdown 档案哲学 |
| **[SQLite FTS5](https://sqlite.org/fts5.html)** | 嵌入式全文检索引擎 |
| **[Karpathy's llm-wiki](https://github.com/karpathy/llm-wiki)** | 个人知识库组织方式 |
| **[gbrain](https://github.com/garrytan/gbrain)** | 知识图谱引擎（MCP + pgvector） |
| **[sentence-transformers](https://sbert.net/)** | 语义搜索嵌入模型 |

**特别感谢** Hermes Agent 团队（Nous Research）提供的原生 memory、skill 和 MCP
扩展 API，使本项目的零侵入部署成为可能。

*记忆体2.0 是在生产环境的 Hermes Agent 实例上经过多轮迭代开发的，
日常处理 700+ 会话和 10,000+ 消息。*
