# Memory Sidecar Architecture v3.1.0

The production memory stack for AI agents. Three layers, no Docker dependency, agent-agnostic.

## Design Principles

1. **Lossless durability.** Agent sessions are the source of truth. The sidecar indexes and archives them but never deletes originals.
2. **Layered recall.** Retrieval isn't one database query. Hot, warm, and cold layers blend through Reciprocal Rank Fusion.
3. **Focused memory.** Important people, projects, and incidents get explicit dossiers instead of staying buried in session fragments.
4. **Operational visibility.** Backlog size, sync lag, duplicate ingestion, and rebuild health are visible, not hidden.
5. **Agent-agnostic.** Works with Hermes, Claude Code, Cursor, Codex — anything that writes sessions to a data directory.

## What Changed in v3.1.0

v3.0 had four layers with an `agentmemory` Docker bridge between Hindsight and gbrain. In practice that bridge held 13 stale records and added a Docker dependency for no benefit. v3.1.0 removes it entirely and adds session_search FTS5 as a parallel cold path.

**Removed:**
- agentmemory MCP (Docker container, 51 tools, 13 records)
- memory_index.db (semi-finished consolidation layer, 100 misc entries)
- Docker as a sidecar runtime dependency

**Added:**
- session_search FTS5 — PostgreSQL full-text search over 105K messages
- gbrain MCP bridge — session_to_gbrain.py now calls gbrain via HTTP API instead of CLI
- consolidated_system.py auto_repair — health checks for all memory services
- OneDrive knowledge sync pipeline
- book_cache system for large reference libraries

## The Three Layers

```
┌──────────────────────────────────────────────────┐
│                   AGENT                          │
│  writes sessions → state.db + session files      │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│              SIDECAR (this project)               │
│                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  HOT     │  │    WARM      │  │    COLD     │ │
│  │ memory   │  │  Hindsight   │  │  gbrain     │ │
│  │ tool     │──│  PostgreSQL  │──│  + FTS5     │ │
│  │ 5KB cap  │  │  ~50ms       │  │  ~500ms     │ │
│  └──────────┘  └──────────────┘  └─────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │        tiered_context_injector.py            │ │
│  │   RRF fusion → intent routing → injection   │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### Hot Layer — memory tool

Lives in the agent's system prompt. Holds user identity, critical preferences, and active context. Cap is 5KB by default. The compact_memory.py script handles pruning and dedup when it fills up.

**What goes here:**
- Who the user is
- Current project state
- Recurring corrections (so the agent doesn't repeat mistakes)
- Critical config (provider chains, auth preferences)

### Warm Layer — Hindsight

PostgreSQL-backed fact graph. Hindsight auto-retains key facts from each session, auto-recalls relevant context at query time, and runs a weekly reflect cycle to synthesize patterns.

**Production numbers (from a live Hermes install):**
- 21,629 extracted memories
- 20,543 observations
- 309 semantic cache entries
- 42,481 total nodes

API endpoints for health checking:
- `GET /health` → `{"status":"healthy","database":"connected"}`
- `GET /v1/default/banks/hermes/stats` → bank statistics (bank name is deployment-specific; `hermes` is the default)
- `GET /metrics` → Prometheus-format metrics

### Cold Layer — gbrain + session_search

Two parallel paths for long-term retrieval:

**gbrain knowledge graph** (10,885 pages, brain score 73):
- Vector search via pgvector (384d embeddings from multilingual-e5-small)
- Keyword search via FTS
- Graph traversal via wikilinks and typed edges
- Timeline entries for chronological queries
- Tag-based filtering

**session_search FTS5** (105,601 messages, 6,374 sessions):
- Full-text search over all historical messages
- Session-level scoping and lineage tracking
- Chinese text search with trigram indexing

## Core Scripts

### session_to_gbrain.py

The archiving workhorse. Reads agent sessions from `$AGENT_HOME/sessions/`, processes unarchived ones, and writes structured pages to gbrain.

v3.1.0 upgrade: Uses a **direct MCP API bridge** instead of the gbrain CLI. The CLI was brittle — path-dependent, occasionally crashing, hard to debug. The MCP bridge calls gbrain's HTTP endpoint at `localhost:8787` with Bearer auth, so it works regardless of CLI state.

Session processing flow:
1. Load checkpoint (which sessions have been processed)
2. Scan for new session files
3. For each unprocessed session:
   - Extract key decisions, learnings, and context
   - Create gbrain page with frontmatter (tags, date, summary)
   - Link to relevant topic hubs
   - Add timeline entries for significant events
4. Save updated checkpoint

Runs every 6 hours in production: `*/30 */6 * * *`

### memory_governance_rebuild.py

The indexer. Rebuilds:
- Session index (FTS5 over state.db)
- Hindsight index (pre-cached recall results)
- Memory hubs (topic aggregators)
- Canonical memory objects with multi-version state (active/superseded) and temporal validity (valid_from/valid_to)
- Conflict groups (dedup clusters)
- Dossier metadata
- Recall metrics
- Vector embeddings (when EMBEDDING_API_URL is configured)

Infrastructure tables maintained:
- `orphan_messages` — audit table for unattached messages
- `session_repair_map` — message→session repair mapping
- `session_lineage_repair` — parent chain repair for sessions
- `recovered_fragments` — un-bucketable memory fragments
- `memory_aliases` / `memory_relations` — alias and relationship graphs
- `sessions_effective` — repaired session view

### memory_guardian.py

Capacity and health watchdog. Tracks:
- Hot memory fill rate (5KB cap dashboard)
- Duplicate detection (same fact stored multiple ways)
- Backlog trends (are we falling behind on processing?)
- Stuck operations (jobs that haven't progressed)
- Sync lag (Hindsight consolidation queue depth)

Provides safe drain paths for backlog and stuck operations.

### memory_family_registry.py

Intent classifier + dossier router. Maps query text to retrieval families:

- **Provider/System** → config-first, governance objects
- **Project** → delivery-first, canonical project objects
- **Relationship/Dossier** → dossier-first, live Hindsight + timeline-aware
- **Exploratory** → broader governance evidence, limited fallback

Contains the active Focused Dossier registry. Add new dossiers by editing the `active_focus_profiles()` dict.

### tiered_context_injector.py

The recall engine. Three-path parallel retrieval with RRF fusion:

```
Query arrives
    ↓
┌───┼───────────────────────────────┐
│   │                               │
▼   ▼                               ▼
L1  L2                              L3
Hot Warm                            Cold
    (Hindsight)                     (gbrain + FTS5)
    │                               │
    └───────────────┬───────────────┘
                    ↓
            RRF fusion (k=60)
                    ↓
            Intent re-ranking
                    ↓
            Injected to agent context
```

Supports domain routing to prevent one topic from dominating all memory:

| Domain | Quota | Purpose |
|--------|-------|---------|
| magic | 500 | Relationship analysis |
| stock | 400 | Trading strategies |
| system | 300 | System configuration |
| promo | 200 | Channel promotion |
| misc | 200 | Everything else |

### memory_maintenance_cycle.py

Orchestrator that sequences the full maintenance pipeline:
1. Session archive intake (session_to_gbrain.py)
2. Governance rebuild (memory_governance_rebuild.py)
3. Backlog drain (memory_guardian.py)
4. Tiered recall generation (tiered_context_injector.py)
5. Health snapshot (memory_guardian.py --status)

### sidecar_acceptance_check.py

Production validation suite. Runs key regression queries and checks that all layers return expected results.

## Focused Dossier Model

When a person, project, or topic is important enough to track systematically, it becomes a Focused Dossier.

A dossier entry in `memory_family_registry.py`:

```python
"magic": {
    "slug": "hub-magic-relationship",
    "title": "magic Relationship Archive",
    "tags": ["magic", "relationship"],
    "keywords": ["magic", "M", "chat", "relationship"],
    "aliases": ["M", "🍡"],
    "retention_priority": "high",
    "enable_timeline": True,
}
```

When a query matches dossier keywords, the recall engine:
1. Pulls the dossier hub page from gbrain first
2. Loads recent timeline entries
3. Searches Hindsight with dossier-scoped filters
4. Ranks dossier evidence above general governance results

## Embedding Infrastructure

Semantic search is optional but strongly recommended. The sidecar uses sentence-transformers models served as a local HTTP API.

**Production deployment (live Hermes install):**
- Model: `intfloat/multilingual-e5-small` (384d)
- Service: systemd-managed, port 8766
- Health check: `GET /health` → `{"ok": true, "service": "gbrain-embed"}`
- Consumption: gbrain chunk embeddings + governance rebuild vector indexing

Without an embedding service, all text-based retrieval paths (FTS5, LIKE, Hindsight, gbrain keyword) continue to work.

## Maintenance Schedule (Production)

From a live Hermes deployment running since April 2026:

| Job | Schedule | Purpose |
|-----|----------|---------|
| session_to_gbrain | Every 6h | Incremental session archival |
| auto_session_summary | Every 6h | Session digest generation |
| archive_sessions | Daily 02:00 | Bulk session archival |
| consolidated_system | Hourly :00/:30 | Service health + auto_repair |
| Hindsight reflect | Weekly Sun 05:30 | Pattern synthesis from accumulated facts |
| memory maintenance cycle | Manual / on-demand | Full rebuild when needed |

## Data Flow (End-to-End)

```
1. Agent conversation happens
   └→ state.db updated + session JSON written

2. session_to_gbrain.py picks up new sessions
   └→ gbrain pages created with tags, timeline, hub links

3. memory_governance_rebuild.py indexes everything
   └→ session index, hindsight index, hubs, canonical objects

4. memory_guardian.py checks health
   └→ backlog trend, capacity, stuck ops

5. Next agent conversation starts
   └→ tiered_context_injector.py assembles context
      Hot (memory tool) → Warm (Hindsight) → Cold (gbrain + FTS5)
      RRF fusion → injected to agent prompt
```

## Operational Health Signals

When the sidecar is healthy:
- gbrain page creation is current (no unprocessed session backlog)
- Hindsight consolidation queue drains steadily
- memory tool stays under 80% capacity
- embedding coverage is near 100%
- session_search FTS5 index is up to date

When something is wrong:
- `memory_guardian.py --status` shows backlog growth
- gbrain health endpoint shows missing embeddings
- tiered_context_injector.py returns fewer results than expected
- sidecar_acceptance_check.py fails regression queries

## Architecture Boundary

The sidecar's responsibility ends at the agent's data directory. It reads from `$AGENT_HOME/state.db` and `$AGENT_HOME/sessions/`, and writes indexes/archives to its own stores (gbrain, Hindsight). It never modifies agent source code.

This boundary is why the sidecar survives agent upgrades. When Hermes or Claude Code ships a new version, the sidecar keeps working — it only depends on stable data formats (SQLite + JSON files), not agent internals.

---

For a high-level overview and setup instructions, see the [README](README.md).
