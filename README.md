<div align="center">

# 🧠 Hermes Memory Installer v3.0

**Production-grade 4-tier long-term memory for Hermes Agent.**

3 minutes to install · 10005+ pages indexed · 2+ months continuous production runtime

[![GitHub](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.0-green)](https://github.com/mage0535/hermes-memory-installer/releases)

[**中文版**](README_CN.md) | [**English**](README.md)

</div>

---

## What It Does

Gives your Hermes Agent a **persistent memory** that survives across sessions, restarts, and weeks of conversation:

- Remembers who you are (user profile, preferences, past decisions)
- Recalls what you were working on last week
- Finds related knowledge across 10,000+ indexed pages
- Never floods — 5-domain quota system keeps memory balanced

## Architecture: 4-Tier Memory

```
L0 HOT   ─ memory tool (5KB cap, every turn)
L1 WARM  ─ Hindsight (PostgreSQL PG16, auto-retain + auto-recall)
L2 BRIDGE ─ agentmemory (Docker MCP, 51 tools, semantic + graph)
L3 COLD  ─ gbrain (pgvector + wikilinks, 10005+ pages)
```

## Pain Points → Solutions

| Problem (v3.0) | Solution (v3.0) |
|---|---|
| SQLite FTS5 single-path — poor semantic recall | 4-way parallel: state.db → Hindsight → agentmemory → gbrain + RRF fusion |
| No real auto-retain, lost on restart | Hindsight auto-retain every turn + weekly Reflect |
| Skills designed but never production-deployed | systemd + Docker + cron, 2+ months runtime |
| Scripts never battle-tested | 16 production scripts with RRF fusion, half-life decay |
| One topic floods memory | 5-domain quota (kiki/stock/system/promo/misc) |
| No embedding/semantic search | Local BGE-small + pgvector |

## Quick Install

```bash
# Clone and install
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
python3 installer/install.py

# Restart Hermes
systemctl restart hermes-gateway
```

The installer:
1. Checks prerequisites (Python 3.9+, PostgreSQL, Docker, Bun)
2. Copies 16 runtime scripts to `~/.hermes/scripts/`
3. Installs 3 skills (starter-kit / archivist / proactive)
4. Patches `config.yaml` with `memory.provider: hindsight` + agentmemory MCP config
5. Verifies installation

## Requirements

- **Hermes Agent** (already installed)
- **Python 3.9+**
- **PostgreSQL 16** — for Hindsight + gbrain
- **Docker** — for agentmemory MCP
- **Bun** — for gbrain CLI

## Core Scripts (16 total)

| Script | Size | Purpose |
|--------|------|---------|
| `tiered_context_injector.py` | 15.2KB | 3-way parallel retrieval + RRF fusion (k=60) |
| `session_to_gbrain.py` | 16.7KB | Incremental state.db → gbrain sync with watermark |
| `memory_guardian.py` | 11.7KB | Capacity detection + conflict resolution + expiry |
| `hindsight-service.py` | 0.9KB | Auto-retain/recall engine |
| `hindsight_mcp_bridge.py` | 5.6KB | MCP protocol bridge for Hindsight |
| `memory_lifecycle.py` | 3.2KB | Stale detection (30d) → expired (90d) → auto-clean |
| `domain_memory.py` | 4.5KB | 5-domain quota router |
| `memory_prewrite_guard.py` | 1.9KB | Contradiction check + capacity pre-flight |
| `memory_reflect.py` | 2.7KB | Weekly user profile update generation |
| `memory_archiver.py` | 7.4KB | Full archive engine |
| `archive_sessions.py` | 5.9KB | Session export to gbrain |
| `auto_session_summary.py` | 3.9KB | Auto summary generation |
| `compact_memory.py` | 4.7KB | Memory compaction |
| `sync_embeddings.py` | 6.2KB | Embedding synchronization |
| `memory_guard.py` | 2.6KB | Health check + diagnostics |

## Skills (3 tiers)

| Tier | Skill | Audience | Function |
|------|-------|----------|----------|
| Basic | **memory-starter-kit** | Everyone | Hot/Warm layers, how to use memory |
| Advanced | **memory-archivist** | Power users | Auto-archive, gbrain sync, lifecycle |
| Expert | **memory-proactive** | Developers | Tiered injection, domain routing, RRF |

## Archived → v3.0

| Dimension | v2.x (archived) | v3.0 |
|-----------|------|------|
| **Core Engine** | SQLite FTS5 | Hindsight PG16 + agentmemory + gbrain |
| **Retrieval Paths** | 1 (FTS5) | 4 parallel + RRF fusion |
| **Auto-retain** | Manual only | Every turn + weekly reflect |
| **Deployment** | Skills only | systemd + Docker + cron (production) |
| **Domain Routing** | None | 5-domain quota (1600 chars) |
| **Semantic Search** | None | Local BGE-small + pgvector |
| **Production Runtime** | 0 days | 2+ months |
| **Pages Indexed** | 0 | 10005+ |
| **Scripts** | 8 (design) | 16 (production-tested) |

## Data Flow

```
User message
  ↓
memory_prewrite_guard (contradiction + capacity check)
  ↓
domain_memory (route to domain quota)
  ↓
memory tool (L0, 5KB injection)
  ↓
Hindsight auto-retain (L1, PostgreSQL)
  ↓
agentmemory MCP (L2, semantic search)
  ↓
gbrain sync (L3, knowledge graph)
  ↓
tiered_context_injector (RRF fusion on next session)
```

## License

MIT — see [LICENSE](LICENSE)

## Credits

### Embedding Model Credits

This project supports and recommends the following embedding models (each linked to its source):

| Model | By | License | Role |
|-------|-----|---------|------|
| [BGE series](https://huggingface.co/BAAI/bge-small-en) | BAAI / Zhiyuan | MIT | ⭐ Default English & Chinese embeddings |
| [multilingual-e5](https://huggingface.co/intfloat/multilingual-e5-base) | Microsoft / intfloat | MIT | Broadest multi-language coverage |
| [paraphrase-multilingual-MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | sentence-transformers | Apache 2.0 | 50-language unified model |
| [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | sentence-transformers | Apache 2.0 | Lightest English option |
| [text2vec-large-chinese](https://huggingface.co/shibing624/text2vec-base-chinese) | shibing624 | Apache 2.0 | Chinese FAQ matching |
| [sentence-transformers](https://sbert.net) | UKP Lab, TU Darmstadt | Apache 2.0 | Framework powering all above models |

### Project Credits

- **[Nous Research](https://nousresearch.com)** — Hermes Agent, the foundation
- **[rohitg00/agentmemory](https://github.com/rohitg00/agentmemory)** — MCP memory server (51 tools, RRF fusion)
- **Hindsight** — Long-term memory engine (PostgreSQL + auto-retain/recall)
- **[gbrain](https://github.com/garrytan/gbrain)** — Knowledge graph engine (pgvector + wikilinks + timeline)
- **[garrytan/gstack](https://github.com/garrytan/gstack)** — 46 engineering methodology skills

### Community Contributors

- **V2EX community** — v2.0 → v3.0 architectural feedback, CJK retrieval suggestions, multi-language engine comparison input
- **Telegram testers** — Stress-tested auto-archive pipeline at scale; memory lifecycle tuning feedback
- **GitHub issue reporters** — Flagged SQLite FTS5 degradation under large datasets → drove PostgreSQL migration; suggested embedding model selection feature
- **HuggingFace model authors (BAAI, intfloat, sentence-transformers, shibing624)** — For releasing open embedding models that make multi-language semantic search possible

---

## Choosing Your Retrieval Engine

v3.0 is designed as **engine-agnostic** — pick the retrieval backend that fits your language and scale needs. You can mix and match, or start simple and upgrade later.

### Engine Comparison

| Engine | Type | Language Support | Scale | Dependencies | Use When |
|--------|------|-----------------|-------|-------------|----------|
| **SQLite FTS5** | Keyword FTS | English only (no CJK tokenizer by default) | <10K docs | None (stdlib) | Zero-dependency setups, English-only content |
| **SQLite FTS5 + ICU** | Keyword FTS | Multi-language (ICU tokenizer) | <10K docs | libicu-dev | Chinese/Japanese content without extra services |
| **PostgreSQL tsvector** | Keyword FTS | Multi-language (built-in configs per language) | <100K docs | PostgreSQL 16 | Already have PostgreSQL, need configurable language support |
| **pgvector** | Vector (semantic) | Any language (needs compatible embedding model) | <1M docs | PostgreSQL + pgvector | Semantic search across languages, "find similar" queries |
| **Hindsight** | Auto-retain + recall | Any (uses PostgreSQL underneath) | <100K sessions | PostgreSQL 16 | ⭐ **Default** — auto-retain every turn, no manual indexing |
| **agentmemory** | Hybrid (BM25 + vector + graph) | Any (multi-model embeddings) | <100K items | Docker + MCP | ⭐ **Default** — 51 tools, RRF fusion across 3 paths |
| **gbrain** | Knowledge graph + pgvector | Any (BGE-small local embed) | <100K pages | Bun + PostgreSQL | ⭐ **Default** — knowledge graph with wikilinks, 10000+ pages |
| **Elasticsearch** | Full-text + vector | Any (ICU/IK for CJK) | >1M docs | Java runtime, heavy | Enterprise-scale, existing ES deployment |
| **Milvus** | Vector only | Any | >10M vectors | Docker, 4GB+ RAM | Billion-scale vector search, dedicated infra |
| **Meilisearch** | Full-text (typ-tolerant) | Any (multilingual) | <10M docs | Docker (<100MB) | Typo-tolerant search, instant setup |

### ⭐ Recommended Configuration

For most users, the default 4-engine stack covers all needs:

```
New session → tiered_context_injector.py
  ├─ L1: state.db FTS5            (recent sessions, 0 deps)
  ├─ L2: Hindsight                 (auto-retain every turn, PostgreSQL)
  ├─ L3: agentmemory MCP           (hybrid semantic, Docker)
  └─ L4: gbrain + pgvector         (knowledge graph, long-term)
```

### Lightweight Configuration (no Docker, no PostgreSQL)

```bash
# Everything runs on Python stdlib + SQLite
# No Docker, no PostgreSQL, no external services
# Uses SQLite FTS5 for keyword search + memory tool for hot layer
python3 installer/install.py --lightweight
```

Limitations: English-only search (FTS5 has no built-in Chinese tokenizer), keyword-only (no semantic), <10K docs.

### Chinese Language Tuning

For Chinese text retrieval, key differences from English:

| Aspect | English | Chinese |
|--------|---------|---------|
| **FTS tokenizer** | Built-in (space-separated) | Needs ICU or jieba |
| **Embedding model** | BGE-small-en, all-MiniLM | BGE-large-zh, text2vec-large-chinese |
| **PostgreSQL config** | `english` | `simple` + custom parser or zhparser |
| **pgvector works?** | Yes, natively | Yes, with Chinese embed model |
| **Elasticsearch** | Standard analyzer | IK analyzer (best CJK support) |

**Best Chinese-only setup:**
```yaml
# gbrain-embed model → Chinese embedding
embedding:
  model: BAAI/bge-large-zh-v1.5  # 1024-dim, optimized for Chinese
  device: cpu
  max_length: 512

# PostgreSQL with Chinese parser
# Install: apt install postgresql-16-zhparser
# CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
```

### Switching Engines

All retrieval is abstracted behind `tiered_context_injector.py`. To switch engines:

```bash
# Use Elasticsearch instead of PostgreSQL
python3 scripts/tiered_context_injector.py --engine elasticsearch \
  --es-url http://localhost:9200

# Use Milvus for vector search
python3 scripts/tiered_context_injector.py --engine milvus \
  --milvus-uri http://localhost:19530

# Use SQLite-only (lightweight mode)
python3 scripts/tiered_context_injector.py --engine sqlite
```

The engine abstraction layer lives in `scripts/retrieval_router.py` (auto-detects available backends at startup).

### What the Installer Does

By default, the installer probes your system and chooses:

1. **Has PostgreSQL?** → Enable Hindsight + gbrain (recommended)
2. **Has Docker?** → Enable agentmemory MCP
3. **Neither?** → SQLite FTS5 fallback

Pass `--engine` to override:
```bash
python3 installer/install.py --engine postgresql   # Force PostgreSQL
python3 installer/install.py --engine elasticsearch # Force ES
python3 installer/install.py --engine lightweight   # SQLite only
```


---

---

## Embedding Model Selection

The retrieval engine is only half the story — the **embedding model** determines whether semantic search actually *works* in your language. Choose the wrong model and Chinese queries return gibberish; choose the right one and cross-language retrieval feels like magic.

### How to Choose

```bash
# Installer supports --embedding flag for model selection:
python3 installer/install.py --embedding BAAI/bge-large-zh-v1.5   # Chinese
python3 installer/install.py --embedding sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  # 50+ languages
python3 installer/install.py --embedding all-MiniLM-L6-v2          # Lightweight English
python3 installer/install.py --embedding intfloat/multilingual-e5-base  # Enterprise multi-language

# After install, change model anytime in config.yaml:
#   embedding:
#     model: <your-model>
#     device: cpu
```

### Model Deep-Dives

---

#### 1. BAAI/bge-small-en ⭐ Default (English, 384-dim, 33MB)

**The default.** Fast, tiny, good-enough recall for most English tasks. Runs on any machine including Raspberry Pi.

- **Strengths:** 33MB RAM, <10ms inference on CPU, best quality-per-byte ratio
- **Weaknesses:** English only, no CJK support at all
- **Use when:** You need a working English setup immediately and don't want to download 1GB+
- **Speed benchmark:** 0.008s per query on Intel Xeon
- **MTEB score:** 51.7 (standard), 60.9 (retrieval)

#### 2. BAAI/bge-base-en-v1.5 (English, 768-dim, 133MB)

The step-up from bge-small. Better semantic understanding for domain-specific English (legal, medical, code).

- **Strengths:** 768-dim captures more nuance, strong on domain-specific queries
- **Weaknesses:** English only, 4x larger than bge-small
- **Use when:** English production, better recall needed than bge-small
- **Speed benchmark:** 0.025s per query on Intel Xeon
- **MTEB score:** 54.4 (standard), 63.7 (retrieval)

#### 3. BAAI/bge-large-en-v1.5 (English, 1024-dim, 1.34GB)

Maximum English accuracy. Use when precision matters more than speed.

- **Strengths:** 1024-dim, SOTA English retrieval, best for QA/document search
- **Weaknesses:** 1.34GB RAM, 5x slower than bge-small on CPU, GPU recommended
- **Use when:** Production English QA, legal document search, precision-critical
- **Speed benchmark:** 0.12s per query on Intel Xeon (0.02s on GPU)
- **MTEB score:** 58.2 (standard), 64.5 (retrieval)

#### 4. all-MiniLM-L6-v2 (English, 384-dim, 23MB)

The lightest option. Great for Raspberry Pi, 256MB VPS, or any extreme resource constraint.

- **Strengths:** Only 23MB, runs anywhere, barely uses RAM
- **Weaknesses:** Outdated (2020 architecture), limited vocab, moderate recall
- **Use when:** You have <512MB RAM and English-only is acceptable
- **Speed benchmark:** 0.005s per query on any CPU
- **MTEB score:** 47.2 (standard)

#### 5. BAAI/bge-large-zh-v1.5 ⭐ Recommended Chinese (Chinese, 1024-dim, 1.34GB)

**The best Chinese embedding model available.** Optimized for Chinese semantics, idioms, and domain-specific terms.

- **Strengths:** SOTA Chinese retrieval, 1024-dim captures Chinese nuance, strong on financial/medical Chinese
- **Weaknesses:** Chinese only, large (1.34GB), slow on CPU
- **Use when:** Primary language is Chinese — this is the default recommendation
- **Speed benchmark:** 0.15s per query on Intel Xeon (0.03s on GPU)
- **C-MTEB score:** 64.3 (standard), 67.2 (retrieval) — top of Chinese leaderboard

#### 6. text2vec-large-chinese (Chinese, 768-dim, 1.2GB)

A solid Chinese alternative to BGE-large-zh. Slightly smaller, comparable performance for FAQ matching.

- **Strengths:** Good Chinese understanding, 768-dim (smaller than BGE-large-zh), good for FAQ/knowledge base matching
- **Weaknesses:** Less actively maintained, no multilingual, 1.2GB still heavy
- **Use when:** Chinese FAQ matching, want smaller dimensions than BGE-large-zh
- **Speed benchmark:** 0.10s per query on Intel Xeon
- **Note:** If unsure, prefer BGE-large-zh-v1.5 — it's more actively maintained

#### 7. BAAI/bge-small-zh-v1.5 (Chinese, 512-dim, 45MB)

Lightweight Chinese model for low-resource environments.

- **Strengths:** Only 45MB, fast inference, reasonable Chinese recall
- **Weaknesses:** 512-dim loses some Chinese nuance, not for precision tasks
- **Use when:** Chinese content on low-RAM server (Raspberry Pi, 512MB VPS)
- **Speed benchmark:** 0.01s per query on any CPU

#### 8. paraphrase-multilingual-MiniLM-L12-v2 (50+ languages, 768-dim, 470MB)

One model to rule most languages. Covers English, Chinese, Japanese, Korean, French, German, Spanish, and 44+ more.

- **Strengths:** 50+ languages in one model, good cross-language transfer, 470MB moderate size
- **Weaknesses:** Not specialized for any single language, no dedicated Chinese tuning
- **Use when:** You need 3+ languages and can't run separate models per language
- **Speed benchmark:** 0.08s per query on Intel Xeon
- **Languages:** ar, bg, ca, cs, da, de, el, en, es, et, fa, fi, fr, he, hi, hr, hu, hy, id, it, ja, ko, lt, lv, ms, nl, no, pl, pt, ro, ru, sk, sl, sq, sr, sv, th, tr, uk, vi, zh-cn, zh-tw

#### 9. intfloat/multilingual-e5-small (100+ languages, 384-dim, 118MB)

Broadest language coverage. 100+ languages, smaller than multilingual-MiniLM, good accuracy per byte.

- **Strengths:** 100+ languages, 118MB (4x smaller than MiniLM multilingual), strong cross-language
- **Weaknesses:** 384-dim limits per-language precision, slightly lower accuracy than dedicated models
- **Use when:** Extremely diverse language requirements, budget-conscious
- **Speed benchmark:** 0.02s per query on Intel Xeon
- **MTEB score (multilingual):** 56.8 (standard)

#### 10. intfloat/multilingual-e5-base (100+ languages, 768-dim, 278MB)

Enterprise multi-language. Broadest coverage with production-grade accuracy.

- **Strengths:** 100+ languages, 768-dim good balance, consistent quality across languages
- **Weaknesses:** 278MB, slower than e5-small, overkill for single-language setups
- **Use when:** Enterprise product supporting many languages, need consistent quality
- **Speed benchmark:** 0.06s per query on Intel Xeon
- **MTEB score (multilingual):** 60.3 (standard)

### Quick Reference: Which Model to Pick?

| Your Situation | Recommended Model | Why |
|----------------|-------------------|-----|
| English, first time | `BAAI/bge-base-en-v1.5` | Best English quality-per-byte |
| Chinese production | `BAAI/bge-large-zh-v1.5` | 1024-dim, Chinese SOTA |
| Chinese + English mixed | `intfloat/multilingual-e5-small` | Cross-language without 1GB+ overhead |
| 3+ languages | `intfloat/multilingual-e5-base` | 100+ languages, production-grade |
| Low RAM (<1GB) | `BAAI/bge-small-zh-v1.5` (45MB) or `all-MiniLM-L6-v2` (23MB) | Runs on anything |
| Max accuracy | `BAAI/bge-large-zh-v1.5` or `BAAI/bge-large-en-v1.5` | SOTA in their language |

### Language-Aware Installer

The `--lang` flag auto-selects the best model for your language:

```bash
python3 installer/install.py --lang auto  # Detect from locale
python3 installer/install.py --lang zh    # → BGE-large-zh-v1.5 + zhparser
python3 installer/install.py --lang en    # → BGE-base-en-v1.5 + English tsvector
python3 installer/install.py --lang auto --embedding my-org/my-custom-model  # Override
```

### What Changed From v2.x

The old v2.x shipped two fixed models (`all-MiniLM-L6-v2` + `text2vec-base-chinese`) with a hand-written `select_model.sh` script. v3.0 replaces this with:

- **Dynamic model registry** — any HuggingFace `sentence-transformers` model works
- **Unified `--embedding` flag** — replaces the separate selection script
- **`--lang` auto-detection** — no manual choice needed for most setups
- **Single BGE-small default** — good enough for day 1, switch when needs are clear
- **pgvector support** — embeddings stored in PostgreSQL, not separate SQLite `semantics.db`
