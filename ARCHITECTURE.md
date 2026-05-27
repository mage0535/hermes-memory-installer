# Architecture: Hermes Memory Installer v3.0

## Overview

The v3.0 memory system is a **4-tier, multi-engine architecture** designed for production AI agents. It replaces the old single-engine single-engine (SQLite FTS5) design with a battle-tested, horizontally layered system that has run continuously for 2+ months.

## Design Principles

1. **No single point of failure** — 4 independent retrieval paths, any one can fail without breaking recall
2. **Progressive depth** — L0→L3, each layer adds richer recall at the cost of latency, queries cascade
3. **Zero-touch retention** — auto-retain every turn, no manual `remember this` needed
4. **Domain isolation** — quota per topic, prevents memory flooding
5. **Local-first** — everything on-prem, no cloud dependencies beyond PostgreSQL

## Tier Details

### L0: Hot Memory (memory tool)

- **Storage**: Built-in Hermes memory tool (5KB cap)
- **Content**: User profile (name, role, preferences), system notes
- **Latency**: 0ms (injected into system prompt)
- **Lifecycle**: Manually managed via `memory()` tool calls
- **Guard script**: `memory_prewrite_guard.py` — capacity check + contradiction detection before write

### L1: Warm Memory (Hindsight)

- **Storage**: PostgreSQL 16, `hindsight` database
- **Engine**: Hindsight Memory Server (systemd service, port 8890)
- **Capabilities**:
  - `auto-retain`: Every turn, key facts extracted and stored (non-blocking, ~50ms)
  - `auto-recall`: Before each session, relevant context injected (async, ~200ms)
  - `Hindsight Reflect`: Weekly (Sun 5:30), generates user profile updates
- **Bridge**: `hindsight_mcp_bridge.py` — exposes recall/retain/reflect as MCP tools

### L2: Bridge Memory (agentmemory)

- **Storage**: Docker container, `iii-engine`, port 3111
- **Engine**: rohitg00/agentmemory MCP Server
- **51 MCP tools** including:
  - `memory_smart_search` — hybrid BM25 + vector + graph
  - `memory_recall` — context-aware recall
  - `memory_save` — structured save with concepts + files
  - `memory_graph_query` — knowledge graph traversal
- **Retrieval**: Reciprocal Rank Fusion (k=60) across 3 internal paths

### L3: Cold Storage (gbrain)

- **Storage**: PostgreSQL 16 + pgvector extension
- **Engine**: gbrain (Bun CLI + MCP server)
- **Index**: 10005+ pages, wikilinks graph, timeline entries
- **Embedding**: Local BGE-small model via `gbrain-embed.service` (port 8765)
- **Sync**: `session_to_gbrain.py` — incremental state.db → gbrain with watermark
- **Lifecycle**: `memory_lifecycle.py` — 30d stale → 90d expired → auto-clean

## Retrieval Pipeline

```
User: "what did we discuss about curl timeout?"

tiered_context_injector.py:
  ┌─ L1: state.db FTS5 → "curl timeout" hits 3 sessions
  ├─ L2: Hindsight semantic → "http requests" + "timeout" → 5 memories
  ├─ L3: gbrain pgvector → nearest neighbors → 7 pages
  └─ RRF fusion (k=60) → ranked top-10 → injected into context
```

## Domain Quota Router

`domain_memory.py` enforces per-domain character quotas:

```python
DOMAINS = {
    'kiki':  500,  # relationship analysis
    'stock': 400,  # A-share strategies  
    'system':300,  # server configuration
    'promo': 200,  # channel promotion
    'misc':  200,  # everything else
}
TOTAL_CAP = 5000  # memory tool hard limit
```

## Data Integrity Guarantees

1. **Write guard**: `memory_prewrite_guard.py` checks for contradictions before write
2. **Atomic writes**: PostgreSQL transactions for all Hindsight operations
3. **Watermark sync**: `session_to_gbrain.py` tracks last sync position, resumes from break
4. **Backup**: config.yaml backed up before modification (`config.yaml.pre-memory-DATE`)
5. **Archive pruning**: `memory_lifecycle.py` marks as archived, never deletes from gbrain

## File Layout

```
~/.hermes/
├── config.yaml                  # memory.provider: hindsight
├── MEMORY.md                    # L0 snapshot
├── state.db                     # Session store (source of truth)
├── scripts/
│   ├── tiered_context_injector.py    # RRF fusion engine
│   ├── memory_guardian.py            # Lifecycle manager
│   ├── session_to_gbrain.py          # gbrain sync
│   └── ... (13 more)
├── skills/
│   ├── memory-starter-kit/           # Basic tier
│   ├── memory-archivist/             # Archive tier
│   └── memory-proactive/             # Proactive tier
├── archives/                         # Manual archives
│   ├── people/
│   ├── projects/
│   └── knowledge/
└── templates/                        # jinja2 templates
```

## Dependencies

| Component | External Dep | Purpose |
|-----------|-------------|---------|
| Hindsight | PostgreSQL 16 | Memory storage |
| agentmemory | Docker | MCP memory server |
| gbrain | Bun + PostgreSQL + pgvector | Knowledge graph |
| gbrain-embed | sentence-transformers (BGE-small) | Local embeddings |

All Python scripts use **stdlib only** — zero third-party dependencies for the core runtime.

## Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| memory_prewrite_guard | <5ms | Single JSON scan |
| domain_memory route | <1ms | Dict lookup |
| Hindsight auto-retain | ~50ms | Async, non-blocking |
| Hindsight auto-recall | ~200ms | Pre-session async |
| tiered_context_injector | ~500ms-2s | 3 parallel queries + RRF |
| gbrain sync (incremental) | ~2-10s | Depends on delta size |
| gbrain sync (full) | ~30-60s | 10005+ pages |

## Failure Modes & Recovery

| Failure | Impact | Recovery |
|---------|--------|----------|
| Hindsight down | L1 lost, L0+L2+L3 still work | `systemctl restart hindsight` |
| agentmemory down | L2 lost, L0+L1+L3 work | `docker restart agentmemory-iii-engine-1` |
| gbrain down | L3 lost, L0+L1+L2 work | Check PostgreSQL + Bun |
| gbrain-embed down | semantic search degraded to keyword | `systemctl restart gbrain-embed` |
| memory tool full | New writes rejected | `compact_memory.py` or manual cleanup |
| PostgreSQL down | L1+L3 lost, L0+L2 still work | Full PostgreSQL recovery |

## Engine Abstraction Layer

The retrieval layer is fully pluggable. `tiered_context_injector.py` discovers available backends at startup and selects the best combination.

### Discovery Order

```
1. Check PostgreSQL connection (for Hindsight + gbrain)
2. Check Docker socket (for agentmemory MCP)
3. Check Elasticsearch endpoint (if configured)
4. Check Milvus endpoint (if configured)
5. Fallback to SQLite FTS5
```

### Language-Specific Backend Recommendations

| Use Case | Recommended Backend | Rationale |
|----------|-------------------|-----------|
| English, <10K docs | SQLite FTS5 (stdlib) | Zero dependencies, fast enough |
| English, <100K docs | PostgreSQL tsvector | Full-text search + auto-retain |
| Any language, semantic | pgvector (+ BGE-small) | Cross-language, finds meaning not keywords |
| Chinese, <100K docs | PostgreSQL + zhparser | Proper Chinese word segmentation |
| Chinese, semantic | pgvector + BGE-large-zh-v1.5 | Chinese-optimized embeddings |
| Japanese/Korean | Elasticsearch + ICU/Nori | Best CJK support outside Python |
| Multi-language mixed | agentmemory MCP (hybrid) | BM25 + vector + graph RRF fusion |
| Knowledge graph queries | gbrain (pgvector + wikilinks) | Entity relationships, timeline |

### Engine Configuration File

`~/.hermes/config.yaml` allows per-engine settings:

```yaml
engine:
  primary: hindsight           # default engine
  secondary: agentmemory       # fallback engine
  fallback: sqlite             # last resort (always available)
  embeddings:
    model: BAAI/bge-small-en   # or BGE-large-zh for Chinese
    device: cpu
  postgresql:
    url: postgresql://localhost:5432/hindsight
  elasticsearch:
    url: http://localhost:9200
  milvus:
    uri: http://localhost:19530
  sqlite:
    path: ~/.hermes/pool.db
```

### Performance by Engine

| Engine | Query Latency | Index Speed | Disk Usage | Recall (English) | Recall (Chinese) |
|--------|--------------|-------------|------------|-----------------|-----------------|
| SQLite FTS5 | <1ms | Fast | Low | ~30% keyword | ~10% (no tokenizer) |
| SQLite FTS5 + ICU | <1ms | Fast | Low | ~30% | ~50% keyword |
| PostgreSQL tsvector | <5ms | Fast | Medium | ~40% | ~50% (zhparser) |
| pgvector (BGE-small) | <20ms | Medium | Medium | ~85% semantic | ~60% (BGE-small-en) |
| pgvector (BGE-large-zh) | <50ms | Slow | High | ~80% | ~90% semantic |
| agentmemory hybrid | <100ms | Medium | Medium (Docker) | ~95% RRF | ~85% RRF |
| Elasticsearch | <10ms | Fast | High | ~90% | ~95% (IK) |
| Milvus | <5ms | Fast | High | ~95% | ~95% |

### Adding a Custom Engine

Implement the `RetrievalBackend` interface:

```python
# scripts/retrieval_router.py
class RetrievalBackend:
    def search(self, query: str, limit: int = 10) -> list[dict]:
        raise NotImplementedError
    def index(self, doc: dict):
        raise NotImplementedError
    def health(self) -> bool:
        raise NotImplementedError
```

Register your backend, and `tiered_context_injector.py` will auto-discover it.
