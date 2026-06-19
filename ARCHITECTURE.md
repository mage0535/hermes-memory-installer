# Memory Sidecar Architecture v3.5

Memory Sidecar v3.5 is the public, agent-agnostic release of the project. It is designed to sit beside an agent, read its durable data directory, and improve recall without patching the agent itself.

Release page: https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5

## Architecture Goals

The v3.5 architecture is built around four constraints:

1. Preserve original session data. The sidecar indexes and archives, but does not delete source data.
2. Retrieve from multiple layers. Recall should blend session history, Hindsight facts, gbrain pages, and curated knowledge notes.
3. Stay portable. The same runtime should work with Hermes, Claude Code, Codex, Cursor, and similar agents as long as they expose a writable agent home directory.
4. Keep the public release safe. Host-specific maintenance helpers remain optional and are not part of the default install set.

## Core Layers

### 1. Hot layer

The hot layer is the agent-local memory tool. It keeps short-lived state such as current project context, key preferences, and active corrections. It is intentionally small and is pruned when needed.

### 2. Warm layer

The warm layer is Hindsight. It stores extracted facts and session-level observations in PostgreSQL and provides durable recall for important items that should survive beyond a single conversation.

### 3. Cold layer

The cold layer combines gbrain and `session_search`:

- gbrain stores structured pages, topic hubs, timelines, and linked knowledge.
- `session_search` provides full-text search over the agent session archive.

### 4. Knowledge layer

The knowledge layer indexes curated markdown notes, including note collections produced by [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management). This lets cleaned-up knowledge participate in recall without forcing it through raw session ingestion first.

## Retrieval Flow

When a query arrives:

1. The sidecar classifies intent and selects a recall family.
2. It pulls candidates from hot, warm, cold, and knowledge layers.
3. It merges candidates with Reciprocal Rank Fusion.
4. It re-ranks by intent and injects a compact context block back to the agent.

This is the main reason the sidecar improves recall quality compared with a single prompt-local memory file.

## Main Scripts

### `session_to_gbrain.py`

Archives new sessions from `$AGENT_HOME/sessions/` into gbrain and records timeline entries for important events.

### `memory_governance_rebuild.py`

Rebuilds the indexes used by recall:

- session index
- Hindsight cache index
- knowledge note index
- canonical memory objects
- conflict groups
- recall metrics

### `memory_guardian.py`

Monitors health and capacity:

- backlog growth
- duplicate ingestion
- sync lag
- stuck operations
- hot layer fill rate

### `memory_family_registry.py`

Routes queries into recall families. This is what keeps project lookups, system lookups, and dossier lookups from interfering with each other.

### `tiered_context_injector.py`

Runs layered retrieval and injects the final context block. This is the runtime path that actually surfaces memory back to the agent.

### `memory_maintenance_cycle.py`

Runs the full maintenance chain in order:

1. archive sessions
2. rebuild governance indexes
3. drain backlog
4. generate tiered recall
5. record health

### `sidecar_acceptance_check.py`

Runs a regression check against the installed runtime so operators can confirm the sidecar is still behaving as expected.

## Embeddings

Embeddings are optional but recommended. The default recommended model is `intfloat/multilingual-e5-small`.

With embeddings enabled, the sidecar can improve semantic retrieval. Without embeddings, the runtime still works through:

- FTS5 session search
- Hindsight recall
- gbrain keyword retrieval
- curated knowledge note indexing

## Installation Boundary

The public installer focuses on a generic runtime:

- default install flow driven by `AGENT_HOME`
- bilingual installer output
- install modes `3 / 2 / 1` with fallback guidance
- preserved embedding model selection flow
- clean separation between public runtime scripts and optional host-specific helpers

Optional repository helpers such as `memory_watermark.py` and `memory_snapshot_backup.py` remain in the repo, but are not part of the default public install path.

## Compatibility Position

The project aims for compatibility through stable data boundaries, not through deep internal coupling.

An agent only needs:

- a writable agent home directory
- `state.db`
- readable session files
- the ability to run Python helper scripts outside the agent process

That boundary is what keeps the sidecar usable across multiple agent products.

## Operational Schedule

Typical production cadence:

- `session_to_gbrain.py`: every 6 hours
- `auto_session_summary.py`: every 6 hours
- `archive_sessions.py`: daily
- `consolidated_system` health checks: hourly
- Hindsight reflect cycle: weekly

## Relation to Knowledge-and-Memory-Management

`hermes-memory-installer` is the runtime and installer layer.
`Knowledge-and-Memory-Management` is the upstream knowledge curation layer.

Used together:

- KMM curates source knowledge and clean notes
- Memory Sidecar indexes that knowledge and makes it recallable for agents

## Validation

Operators should validate the installation with:

```bash
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

For the user-facing overview and install instructions, see [README](README.md).
