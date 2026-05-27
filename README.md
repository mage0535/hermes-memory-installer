# Hermes Memory Installer v4.0

**Production-grade 4-tier long-term memory for Hermes Agent.**

3 minutes to install. 10005+ pages indexed. 2+ months continuous production runtime.

[![GitHub](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0-green)](https://github.com/mage0535/hermes-memory-installer/releases)

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

| Problem (v3.0) | Solution (v4.0) |
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

## v3.0 → v4.0

| Dimension | v3.0 | v4.0 |
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

Built on the shoulders of these excellent projects and communities:

- **[Nous Research](https://nousresearch.com)** — Hermes Agent, the foundation
- **[rohitg00/agentmemory](https://github.com/rohitg00/agentmemory)** — MCP memory server (51 tools, RRF fusion)
- **Hindsight** — Long-term memory engine (PostgreSQL + auto-retain/recall)
- **[gbrain](https://github.com/garrytan/gbrain)** — Knowledge graph engine (pgvector + wikilinks + timeline)
- **[garrytan/gstack](https://github.com/garrytan/gstack)** — 46 engineering methodology skills
- **[BAAI/bge-small](https://huggingface.co/BAAI/bge-small-en)** — Local embedding model
- **V2EX community** — v2.0~v3.0 feedback and architectural suggestions
- **Telegram testers** — Stress-tested auto-archive pipeline at scale
- **GitHub issue reporters** — Flagged SQLite FTS5 degradation → drove PostgreSQL migration
