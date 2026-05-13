<div align="center">

# 🧠 Hermes Memory Installer 2.1.1

**AI长期记忆系统 — 由 gbrain 知识图谱驱动**

[中文版](README_CN.md) | [English](#)

![Version](https://img.shields.io/badge/version-2.2.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)

</div>

---

## 🇺🇸 About

### Why Memory 2.0?

The #1 pain point of AI assistants — **they forget**. Hermes Agent provides native `memory` and `skill` mechanisms, but lacks an out-of-the-box structured long-term memory solution.

**Memory 1.0** solved this with SQLite FTS5 + Markdown archives + 3 skills. It was a solid foundation.

**Memory 2.0** goes further — adding a **knowledge graph engine (gbrain)**, **dual-path semantic search**, **auto-summarization pipeline**, **curator self-evolution**, and **cross-platform recall**.

### Core Architecture

```
╔══════════════════════════════════════════════════╗
║            Memory 2.0 Three-Layer Stack           ║
╠══════════════════════════════════════════════════╣
║  Dialog Layer │ User ↔ Hermes Gateway ↔ AI       ║
║  ─────────────────────────────────────────────── ║
║  Skill Layer  │ memory-starter-kit  [Required]    ║
║               │ memory-archivist    [Recommended] ║
║               │ memory-proactive    [Optional]    ║
║               │ curator             [Self-Evolve] ║
║  ─────────────────────────────────────────────── ║
║  Data Layer   │ state.db (FTS5)    — Live store   ║
║               │ pool.db  (FTS5)    — Archive idx  ║
║               │ archives/ (Markdown) — File system ║
║               │ gbrain (pgvector)  — Knowledge    ║
╚══════════════════════════════════════════════════╝
```

## v2.1.1 Changelog

### 🌐 Multi-Language Embedding Engine Upgrade

Upgraded from Chinese-only `BAAI/bge-small-zh-v1.5` (512d, 96MB) to **`intfloat/multilingual-e5-small`** (384d, ~470MB) — now supporting **100+ languages** including Chinese, English, Japanese, Korean, Arabic, Thai, Vietnamese, Hindi, and all major European languages.

- New: Multi-model selection during installation (`install.sh` prompts user to choose)
- New: AI assistant auto-detection — if run by an LLM, install script reminds to confirm model with user
- Updated: `scripts/embedding_server.py` — default model changed to `intfloat/multilingual-e5-small`
- Updated: `install.sh` — `select_embedding_model()` function with 7 model options

### 🧪 Model Selection During Install

The installer now presents a model picker before proceeding:

```
📊 Select Embedding Engine Model

  1) intfloat/multilingual-e5-small     ⭐ Recommended
     384d | 100+ languages | ~470MB
  2) BAAI/bge-small-zh-v1.5             Chinese-only
     512d | Chinese optimized | ~96MB
  3) paraphrase-multilingual-MiniLM-L12-v2
     384d | 50+ languages | ~471MB
  4) Alibaba-NLP/gte-multilingual-base
     768d | 75+ languages | ~610MB
  5) sentence-transformers/LaBSE
     768d | 109 languages | ~471MB
  6) BAAI/bge-m3
     1024d | 100+ languages | ~2GB
  7) Custom (enter model ID)
```

### 🤖 AI Assistant Auto-Detection

When the installer detects it's running under an AI assistant (non-interactive TTY or `AI_ASSISTED` env), it pauses to remind the AI to **confirm the model choice with the user** before continuing. This prevents silent model downgrades or unexpected disk usage.

### 🔤 A. Multi-language Search Engine

Upgraded embedding model from English-only `all-MiniLM-L6-v2` (384d) to **BAAI/bge-small-zh-v1.5** (512d, 33MB). A single model now handles both **Chinese and English** search natively — no dual-model split needed.

- New: `scripts/embedding_server.py` — OpenAI-compatible API on port 8766
- Updated: `scripts/sync_embeddings.py` — uses BAAI/bge-small-zh-v1.5 by default
- Updated: `scripts/gbrain_init.sh` — `--embed` flag auto-deploys the server

### 🛠️ B. Production Scripts Added

| Script | Purpose |
|--------|---------|
| `scripts/daily_archive.py` | Daily session archival to gbrain + DB backup |
| `scripts/weekly_cleanup.py` | Weekly FTS5 reindex + expired session cleanup + orphan detection |
| `scripts/backup.py` | Full backup/restore with `backup`/`restore`/`list` subcommands |
| `scripts/test_router.py` | Validates FTS5 → embedding → gbrain recall pipeline |
| `bin/hermes-memory` | CLI tool with `new`/`doctor`/`init` commands |

### 🏠 C. Cross-platform Path Support

Fixed critical issue where hard-coded `/root/.hermes` broke installations on machines with different home directories (e.g., `/home/user/.hermes`).

- All scripts now use `$HOME` / `Path.home()` (zero hard-coded paths)
- `install.sh` includes `detect_hermes_home()` pre-flight check
- Auto-detects and adjusts paths on first run
- Non-root users install seamlessly

### 📦 Upgrade from v2.0.0

```bash
cd /tmp && git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer && git checkout v2.1.0
# Copy new scripts
cp scripts/daily_archive.py scripts/weekly_cleanup.py scripts/backup.py ~/.hermes/scripts/
cp scripts/test_router.py scripts/embedding_server.py ~/.hermes/scripts/
cp bin/hermes-memory ~/.local/bin/
# Install embedding server
python3 ~/.hermes/scripts/embedding_server.py &
```

### Original vs Memory 1.0 vs Memory 2.0

| Dimension | Original Hermes | Memory 1.0 | ⭐ Memory 2.0 |
|---|---|---|---|
| **Storage** | Single text blob | Flat Markdown + SQLite FTS5 | Markdown + SQLite FTS5 + **gbrain knowledge graph** |
| **Retrieval** | LLM context only | FTS5 full-text search | **FTS5 + vector similarity + graph traversal** (triple path) |
| **Automation** | None | Scheduled cron | Cron + **auto-summary + curator + self-evolution** |
| **Context** | Current session | Lazy load archives | **Dual-layer semantic recall + cross-platform + knowledge graph** |
| **Observability** | Not viewable | Markdown in editor | Markdown + **gbrain dashboard + health metrics** |
| **Extensibility** | Core code changes | Pure skills + templates | Skills + MCP tools + **gbrain API + plugins** |
| **Install** | Manual | 30s one-click | 30s one-click + **optinal gbrain setup** |
| **Resource** | Minimal | ~50MB + SQLite | ~200MB + SQLite + optional Bun/gbrain |

### gbrain Knowledge Graph Engine (v2.0 Core)

Memory 2.0 introduces **gbrain** (Postgres-native knowledge graph) as the Layer 3 retrieval engine:

- **Storage**: PGLite (zero-config, default) or PostgreSQL 16+ + pgvector
- **Retrieval**: Keyword (tsvector) + Vector semantic (pgvector) + Graph traversal (triple hybrid)
- **Integration**: Via Hermes MCP protocol, Gateway auto-starts gbrain sidecar
- **Automation**: Daily session archiving to gbrain pages + timeline entries

```
User Query -> FTS5 (state.db, ms-level)
          -> Semantic search (embeddings, ~200ms)
          -> gbrain knowledge graph (vector+keyword+graph, fallback)
```

### Component Comparison

| Dimension | Memory 1.0 | Memory 2.0 |
|-----------|-----------|------------|
| **Retrieval** | FTS5 single path | FTS5 + Vector + Graph triple path |
| **Knowledge Engine** | None | gbrain (PGLite/Postgres + pgvector) |
| **Session Archive** | Local files only | Auto-writes to gbrain pages + timeline |
| **Maintenance** | Manual | gbrain_maintain.sh daily auto |
| **Search** | Local FTS5 | gbrain query hybrid search |
| **Observability** | File tree | gbrain doctor + dashboard |



### Installation

#### Method A: One-click (Beginner)

```bash
curl -fsSL https://raw.githubusercontent.com/mage0535/hermes-memory-installer/main/install.sh | bash
```

#### Method B: Manual (Advanced)

See [MANUAL_INSTALL.md](MANUAL_INSTALL.md)

### Credits and Inspirations

| Project | What We Borrowed |
|---------|-----------------|
| **[mem0](https://github.com/mem0ai/mem0)** | Memory layering architecture |
| **[LangChain Memory](https://python.langchain.com/docs/modules/memory/)** | Hybrid retrieval strategy |
| **[Obsidian](https://obsidian.md/)** | Local-first Markdown philosophy |
| **[SQLite FTS5](https://sqlite.org/fts5.html)** | Embedded full-text search |
| **[Karpathy's llm-wiki](https://github.com/karpathy/llm-wiki)** | Knowledge base organization |
| **[gbrain](https://github.com/garrytan/gbrain)** | Knowledge graph engine (New in 2.0) |

**Special thanks** to the Hermes Agent team for the native extension APIs.



## 📊 Embedding Engine Model Comparison

For a detailed comparison guide to help choose the right model, see the table below.  
**Our recommendation**: `intfloat/multilingual-e5-small` (100+ languages, balanced size & quality).

| # | Model | Size | Dim | Languages | Best For |
|---|-------|:----:|:---:|:---------:|----------|
| 1 | `intfloat/multilingual-e5-small` ⭐ | 470MB | 384 | 100+ | Global users, default choice |
| 2 | `BAAI/bge-small-zh-v1.5` | 96MB | 512 | zh | Chinese-only, minimal resources |
| 3 | `paraphrase-multilingual-MiniLM-L12-v2` | 471MB | 384 | 50+ | Mature community model |
| 4 | `Alibaba-NLP/gte-multilingual-base` | 610MB | 768 | 75+ | High Chinese accuracy, 8K tokens |
| 5 | `sentence-transformers/LaBSE` | 471MB | 768 | 109 | Cross-lingual alignment specialist |
| 6 | `BAAI/bge-m3` | 2GB | 1024 | 100+ | Maximum precision, heavy resources |
| 7 | `sentence-transformers/distiluse-base-multilingual-cased-v2` | 539MB | 512 | 50+ | Legacy stability |

**Switching models**: Set `EMBEDDING_MODEL` env var before running the embedding server:
```bash
export EMBEDDING_MODEL="BAAI/bge-m3"
python3 scripts/embedding_server.py
```

**Note**: Changing the embedding model requires rebuilding the pgvector index if dimensions differ.

### Version History

| Version | Date | Highlights |
|---------|------|------------|
| v2.1.1 | 2026-05 | 🌐 multilingual-e5-small (100+ languages), 🧪 model selection during install, 🤖 AI assistant auto-detection |
| v2.1.0 | 2026-05 | 🔤 BAAI/bge-small-zh-v1.5 multilingual search, 🛠️ 5 new production scripts, 🏠 cross-platform path auto-detection |
| v2.0.0 | 2026-05 | gbrain integration, dual-path search, auto-summarization, curator, self-evolution |
| v1.0.0 | 2026-04 | FTS5 retrieval, 3 skills, one-click install, Markdown archives |




### License

MIT
