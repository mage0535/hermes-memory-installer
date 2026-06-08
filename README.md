<div align="center">

# Memory Sidecar v3.1.0

**A production memory system for any AI agent. Keep knowledge across sessions, without touching agent internals.**

[![Version](https://img.shields.io/badge/version-3.1.0-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**中文文档**](README_CN.md) | [**Architecture**](ARCHITECTURE.md)

</div>

---

## What This Is

AI agents forget things. Every new session starts blank.

Memory Sidecar runs alongside your agent — Hermes, Claude Code, Cursor, Codex, whatever — and gives it a real memory. It saves important conversations, builds long-term knowledge, and feeds relevant context back when needed.

It doesn't patch the agent. It's a sidecar: separate process, shared data directory.

**Three things it actually does:**

1. **Archives sessions to permanent knowledge** — conversations aren't lost when you restart
2. **Recalls what matters** — layered retrieval: recent context → semantic search → knowledge graph
3. **Tracks important topics** — people, projects, recurring problems get their own "dossier"

## Architecture at a Glance

```
Agent writes sessions → state.db + session files
              ↓
Sidecar reads checkpoint, processes new sessions
              ↓
  ┌───────────┼───────────┐
  │           │           │
  ▼           ▼           ▼
Hot Layer   Warm Layer  Cold Layer
(memory     (Hindsight  (gbrain graph
 tool,      PostgreSQL)  + FTS5 search)
 5KB cap)               
              ↓
  Tiered context injection → agent's system prompt
```

The full stack is documented in [ARCHITECTURE.md](ARCHITECTURE.md). Short version:

| Layer | What | Technology | Speed |
|-------|------|-----------|-------|
| Hot | Current user + system facts | memory tool injection | 0ms |
| Warm | Extracted facts, recurring patterns | Hindsight (PostgreSQL 16) | ~50ms |
| Cold | Permanent archive, knowledge graph | gbrain + FTS5 session search | ~500ms–2s |

We dropped the intermediate agentmemory bridge layer from earlier versions. It added Docker overhead with barely any data. The current three layers are simpler, faster, and more reliable.

## Quick Start

### What you need

- Python 3.9+
- [gbrain](https://github.com/hi-ogawa/gbrain) (knowledge graph, running on port 8787)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) (fact store, port 8890)
- PostgreSQL 16 (backing store for both of the above)
- An AI agent producing sessions (Hermes, Claude Code, etc.)

### Install

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

# Set AGENT_HOME to point to your agent's data directory
export AGENT_HOME="$HOME/.hermes"   # or ~/.claude, ~/.cursor, etc.
./install.sh
```

The installer will:

1. **Check your environment** — Python, PostgreSQL, Hindsight, gbrain reachability
2. **Let you pick an embedding model** — for semantic search (optional but recommended)
3. **Deploy sidecar scripts** — to `$AGENT_HOME/scripts/`
4. **Patch agent config** — adds memory provider settings if a config file is found

Non-interactive mode:

```bash
./install.sh --noninteractive --agent-home "$HOME/.my-agent"
```

### After Installing

```bash
# Run one archive pass
python3 $AGENT_HOME/scripts/session_to_gbrain.py --resume

# Run the full maintenance cycle
python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py

# Verify everything works
python3 $AGENT_HOME/scripts/sidecar_acceptance_check.py
```

For ongoing operation, schedule the maintenance cycle via cron (or your agent's built-in scheduler). See [ARCHITECTURE.md](ARCHITECTURE.md) for recommended schedules.

## The Scripts

Seven scripts run the sidecar. All live in `$AGENT_HOME/scripts/` after install:

| Script | Role |
|--------|------|
| `session_to_gbrain.py` | Incremental session → gbrain archive with MCP API bridge |
| `memory_governance_rebuild.py` | Rebuild session index, hubs, canonical objects, vector index |
| `memory_guardian.py` | Capacity monitoring, backlog detection, stuck operation recovery |
| `memory_family_registry.py` | Query intent classification + Focused Dossier routing |
| `tiered_context_injector.py` | Layered recall: Hot → Warm → Cold → RRF fusion |
| `memory_maintenance_cycle.py` | Orchestrator: archive → rebuild → drain → recall → health |
| `sidecar_acceptance_check.py` | Production validation suite |
| `archive_sessions.py` | Bulk session archival to gbrain (in cron at 2am) |
| `auto_session_summary.py` | Session digest generation, runs every 6 hours |

**Running in production (cron):** `session_to_gbrain.py`, `archive_sessions.py`, `auto_session_summary.py`

**Available on-demand:** `memory_governance_rebuild.py`, `memory_guardian.py`, `memory_family_registry.py`, `tiered_context_injector.py`, `memory_maintenance_cycle.py`, `sidecar_acceptance_check.py`


## Focused Dossiers

Some things matter more than others. A key person. A long-running project. A recurring incident.

v3.1.0 lets you declare **Focused Dossiers** — high-priority memory profiles that get special treatment in recall. A dossier has:

- **aliases** — all the names it's referred to by
- **topic markers** — keywords that trigger dossier-first retrieval
- **retention priority** — don't let this get pruned
- **timeline tracking** — chronological entries for major events

The first production dossier is `kiki` — a relationship memory profile that demonstrated the pattern works at scale (hundreds of sessions, thousands of extracted facts, timeline-aware recall).

To add your own, edit `memory_family_registry.py` and add a new profile entry. The format is self-documenting in the file.

## Embedding Model Selection

Semantic search needs embeddings. The sidecar supports pluggable models via sentence-transformers.

During install, you pick one. The installer records your choice but doesn't deploy the model — you run the embedding service separately.

**How it affects retrieval:**
- Semantic matching catches meaning, not just keywords
- Cross-lingual: Chinese queries find English content
- Better clustering of related facts even when wording differs

**Supported models:**

| Model | Langs | Dim | Size | Best For |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` ★ | 100+ | 384d | ~470MB | Default. Balanced multilingual |
| `BAAI/bge-small-zh-v1.5` | Chinese | 512d | ~96MB | Tiny Chinese-first deployment |
| `paraphrase-multilingual-MiniLM-L12-v2` | 50+ | 384d | ~471MB | Mature ST ecosystem |
| `Alibaba-NLP/gte-multilingual-base` | 75+ | 768d | ~610MB | Higher recall, more RAM |
| `sentence-transformers/LaBSE` | 109 | 768d | ~471MB | Strong cross-lingual alignment |
| `BAAI/bge-m3` | 100+ | 1024d | ~2GB | Maximum precision, needs resources |

### Deploying the Embedding Service

```bash
pip install sentence-transformers flask
```

Minimal server:

```python
from sentence_transformers import SentenceTransformer
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

model = SentenceTransformer("intfloat/multilingual-e5-small")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        texts = body.get("input", [])
        emb = model.encode(texts, normalize_embeddings=True).tolist()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(
            {"data": [{"embedding": e} for e in emb]}
        ).encode())

HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
```

Set the URL and rebuild governance:

```bash
export EMBEDDING_API_URL=http://127.0.0.1:8766/v1/embeddings
python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py
```

No embedding service? No problem — text-based retrieval (FTS5, LIKE, Hindsight, gbrain) works without it.

## Works With Any Agent

Memory Sidecar is agent-agnostic. It reads from `$AGENT_HOME/state.db` and session files, and operates entirely outside the agent process.

Tested with:
- **Hermes Agent** — original companion, 2+ months production
- **Claude Code** — via `AGENT_HOME=~/.claude`
- **Cursor / Codex** — shared data directory pattern

The installer respects `AGENT_HOME` (falls back to `HERMES_HOME` for backward compatibility). If your agent stores data somewhere non-standard, point `--agent-home` at it.

## Production Track Record

This isn't a prototype. The current stack has been running continuously on a production Hermes installation since April 2026:

- **10,885 gbrain pages** — full knowledge graph with timeline tracking
- **42,481 Hindsight nodes** — extracted facts with auto-retain/recall/reflect
- **105,601 indexed messages** — FTS5 searchable session archive
- **100% embedding coverage** — vector search across all content
- **brain score 73** — gbrain content quality metric

## Changelog

### v3.1.1 (2026-06-08)

- **New scripts**: `memory_watermark.py` (auto-detect memory capacity and archive stale entries) + `memory_snapshot_backup.py` (periodic snapshot backup)
- **Updated**: `hindsight-service.py` — simplified standalone daemon using existing PG on port 5432
- **Updated**: `hindsight_mcp_bridge.py` — clean line endings and improved MCP stdio bridge
- **Updated**: `session_to_gbrain.py` — env-var-based token config (no more hardcoded secrets)
- **Docs**: repo layout now reflects 9 scripts instead of 7

### v3.1.0 (2026-06-02)

- Simplified 4-tier → 3-tier architecture (removed agentmemory Docker bridge)
- Removed `memory_index.db` (semi-finished layer)
- Agent-agnostic via `AGENT_HOME` (not hardcoded to Hermes)
- Interactive embedding model selection during install
- Dry-run mode (`--dry-run`)
- Bilingual README (EN/CN) with language switching
- ARCHITECTURE_CN.md — Chinese architecture translation
- Focused Dossier model (first production instance: Kiki)
- Embedding Model selection guide (6 models)
- Production track record: 10.8K pages, 42K nodes, 100% embed coverage

### v3.0.0 (2026-05-29)

- Complete documentation overhaul
- Added HERMES_AUDIT_REPORT.md — comprehensive agent capability audit
- Optimized Chinese README for SoV/SEO
- 4-tier architecture: Hot → Warm → Cold → Archive

## Repository Layout

```
installer/     Entry point, config patching, environment checks
|scripts/       9 supported sidecar scripts (incl. memory_watermark, memory_snapshot_backup)
|skills/        Agent-side memory skills (starter-kit, proactive, archivist)
templates/     Memory templates
```

## Acknowledgements

### Core Projects

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — the agent this sidecar was built alongside
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) — short/medium-term fact graph
- [gbrain](https://github.com/hi-ogawa/gbrain) — personal knowledge graph engine
- [sentence-transformers](https://www.sbert.net/) — embedding model framework
- [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) — vector storage backbone
- [OpenCode](https://opencode.ai) — guided architecture and production iteration

### Embedding Models

- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [sentence-transformers/LaBSE](https://huggingface.co/sentence-transformers/LaBSE)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)

### Community

Shoutout to everyone who filed issues, surfaced recall gaps, and pushed the design forward. GitHub Issues, Discussions, Reddit (r/LocalLLaMA, r/MachineLearning), V2EX, and direct production feedback all shaped v3.1.0.

---

If this project helps you, [drop a star ⭐](https://github.com/mage0535/hermes-memory-installer) — it helps others find it too.

## License

MIT. See bundled dependencies for their respective licenses.
