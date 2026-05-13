<div align="center">

# 🧠 Hermes Memory Installer

**Production-grade long-term memory system for Hermes AI Agent — powered by gbrain knowledge graph**

[![Version](https://img.shields.io/badge/version-2.2.0-blue)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v2.2.0)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)]()
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)]()

[中文版](README_CN.md) | [English](README.md)

A zero-dependency memory system that adds persistent, searchable, lifecycle-managed memory to any Hermes Agent deployment. Installs in under 60 seconds.

</div>

---

## Table of Contents
<!-- TOC -->
- [Why This Exists](#why-this-exists)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
  - [Data Flow](#data-flow)
  - [Component Map](#component-map)
- [Script Reference](#script-reference)
  - [Core Pipeline Scripts](#core-pipeline-scripts)
  - [Guard & Validation Scripts](#guard--validation-scripts)
  - [Utility Scripts](#utility-scripts)
- [Configuration](#configuration)
  - [Memory Lifecycle Protection](#memory-lifecycle-protection)
  - [Domain Quotas](#domain-quotas)
- [Scheduling](#scheduling)
- [Incremental Sync Architecture](#incremental-sync-architecture)
- [Changelog](#changelog)
- [Acknowledgments](#acknowledgments)
- [License](#license)

---

## Why This Exists

Hermes Agent's built-in `memory()` tool works well for short-term recall, but it has fundamental limitations:

1. **No lifecycle management** — entries accumulate indefinitely, old and new compete for the same slot
2. **No tiered retrieval** — every session starts from scratch, no context beyond the most recent memory dump
3. **No domain isolation** — stock analysis config and relationship notes mix in the same flat namespace
4. **No feedback loop** — the agent can't signal "this was helpful" or "this is outdated"

This installer adds a complete memory pipeline that wraps Hermes' native `memory()` tool with:

- A **tiered context injector** that builds rich session context from three independent data sources
- A **lifecycle state machine** that tracks page freshness and auto-archives stale knowledge
- **Domain isolation** with per-domain quotas so no single topic dominates
- **Pre-write guards** that detect contradictions and capacity issues before they happen
- A **session-to-gbrain pipeline** that turns ephemeral conversations into persistent knowledge graph nodes

All in ~1,400 lines of Python, with zero third-party dependencies.

---

## Key Features

### 🧠 Tiered Context Injection (v3 + RRF Fusion)

When the agent starts a new session, the injector builds a composite context from:

| Layer | Source | Decay | Weight |
|-------|--------|-------|--------|
| **L1** | Recent session summaries (SQLite `messages_fts`) | — | Always included |
| **L2** | FTS5 full-text search across 60K+ messages | 30-day half-life (`0.5^(days/30)`) | RRF fused with L3 |
| **L3** | gbrain knowledge graph MCP query | — | RRF fused with L2 |

L2 and L3 run in parallel (not cascade). Results are merged via **Reciprocal Rank Fusion** (k=60): entries that match both sources get a significant ranking boost over entries that match only one. The agent sees the most relevant content first.

### 🔄 Memory Lifecycle State Machine

Each gbrain page follows a four-state lifecycle, managed by `memory_lifecycle.py`:

```
active ──[90 days untouched]──► stale ──[manual update]──► active
  │                                │
  │                                ├──[superseded tag]──► superseded
  │                                │
  └──[180 days untouched]─────────► archived (hidden from search)
```

**Protected pages** (configured via YAML — e.g., hub pages, critical knowledge) are excluded from auto-archiving. The protection mechanism is entirely config-driven; the repository ships zero internal page names.

### 🚧 Pre-Write Guards

Before any new memory is written, two guards inspect the proposed entry:

1. **Capacity guard** (`memory_guard.py`) — rejects writes when remaining capacity drops below 15%
2. **Contradiction guard** (`memory_prewrite_guard.py`) — scans existing entries for conflicting claims (regex-based, zero token cost)

Both return structured JSON that the agent can act on autonomously.

### 🏷️ Feedback Tags

After the agent uses context in a response, it can tag pages with:

- `fb:helpful` — boosts the page's rank in future RRF fusion (+0.1)
- `fb:misleading` — penalizes the page's rank (-0.5)
- `fb:outdated` — marks the page for lifecycle review

Tags are stored on gbrain pages as standard tags, queryable by any agent in future sessions.

### 🔌 Domain Isolation

Memory is split into five domains with per-domain quotas:

| Domain | Quota | Purpose |
|--------|-------|---------|
| `kiki` | 300 | Relationship status & personality profile |
| `astock` | 400 | A-stock config, models, factor weights |
| `promo` | 300 | Promotion operations & channel data |
| `system` | 300 | System config, philosophy, hard rules |
| `misc` | 300 | General / catch-all |

The `@domain:` prefix routes entries automatically. The domain manager (`domain_memory.py`) enforces per-domain caps independently.

---

## Quick Start

### Prerequisites

- Hermes Agent installed (v0.11+)
- Python ≥ 3.9 with SQLite FTS5 support
- (Optional) [gbrain](https://github.com/garrytan/gbrain) for knowledge graph features

### Installation

```bash
# Clone & install
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

# Option A: Automated installer (recommended)
bash install.sh

# Option B: Python installer
python3 installer/install.py

# Restart Hermes Gateway
systemctl restart hermes-gateway  # or: hermes restart
```

### Verify Installation

```bash
# Check key components
ls ~/.hermes/scripts/tiered_context_injector.py     # context injection
ls ~/.hermes/scripts/memory_lifecycle.py            # lifecycle management
ls ~/.hermes/pool.db                                 # archive database (FTS5)
ls ~/.hermes/archives/                               # archive directories
ls ~/.hermes/skills/memory-starter-kit              # starter skill
```

### First Run

```bash
# One-shot context injection test
python3 ~/.hermes/scripts/tiered_context_injector.py --recall test

# Dry-run lifecycle check
python3 ~/.hermes/scripts/memory_lifecycle.py --dry-run

# Session → gbrain sync (dry-run)
python3 ~/.hermes/scripts/session_to_gbrain.py --dry-run
```

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Hermes Agent                       │
│  ┌─────────┐   ┌──────────┐   ┌──────────────────┐  │
│  │ memory() │   │ session  │   │ tiered_context   │  │
│  │  write   │   │ context  │   │ injector (read)  │  │
│  └────┬─────┘   └────┬─────┘   └────────┬─────────┘  │
└───────┼──────────────┼──────────────────┼────────────┘
        │              │                  │
        ▼              ▼                  ▼
┌─────────────────────────────────────────────────────┐
│                Memory Pipeline Layer                  │
│                                                       │
│  ┌────────────┐  ┌────────────────┐  ┌───────────┐  │
│  │ Guards     │  │ Session to     │  │ Lifecycle │  │
│  │ - capacity │  │ gbrain         │  │ - stale   │  │
│  │ - conflict │  │ (incremental)  │  │ - archive │  │
│  └─────┬──────┘  └───────┬────────┘  └─────┬─────┘  │
│        │                 │                  │        │
│        ▼                 ▼                  ▼        │
│  ┌────────────┐  ┌────────────────┐  ┌───────────┐  │
│  │ Domain     │  │ gbrain MCP     │  │ Domain    │  │
│  │ Memory     │  │ (knowledge     │  │ Memory    │  │
│  │ 5 areas    │  │  graph)        │  │ 5 areas   │  │
│  └─────┬──────┘  └───────┬────────┘  └─────┬─────┘  │
└────────┼─────────────────┼──────────────────┼────────┘
         │                 │                  │
         ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────┐
│                    Storage Layer                       │
│                                                       │
│  ┌────────────────┐  ┌──────────────────────────┐    │
│  │ Hermes state    │  │ gbrain brain.db          │    │
│  │ state.db        │  │ (knowledge graph +       │    │
│  │ messages_fts    │  │  embeddings + vectors)   │    │
│  │ (60K messages)  │  │                          │    │
│  └────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Data Flow

#### Write Path

```
agent memory() call
    │
    ▼
┌─────────────────────────────┐
│ memory_guard.py              │
│ → check remaining capacity  │
│ → reject if < 15% free      │
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ memory_prewrite_guard.py     │
│ → scan for contradictions   │
│ → suggest replace vs add    │
│ → return structured JSON    │
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ domain_memory.py             │
│ → parse @domain: prefix     │
│ → route to correct domain   │
│ → enforce per-domain quota  │
└──────────┬──────────────────┘
           ▼
    memory written to Hermes state.db
           │
           ▼ (async, via cron)
    session_to_gbrain.py
    → create/update gbrain page
    → add tags + timeline
```

#### Read Path

```
agent session starts
    │
    ▼
┌──────────────────────────────────────┐
│ tiered_context_injector.py           │
│                                      │
│  ┌─────────────────┐    ┌─────────┐ │
│  │ L1: Recent N     │    │ L3:     │ │
│  │ sessions from    │    │ gbrain  │ │
│  │ state.db         │    │ MCP     │ │
│  └────────┬────────┘    │ query   │ │
│           │             └────┬────┘ │
│  ┌────────▼────────┐        │       │
│  │ L2: FTS5 search │        │       │
│  │ × half-life     │        │       │
│  │ decay (30d)     │        │       │
│  └────────┬────────┘        │       │
│           │                 │       │
│           └──────┬──────────┘       │
│                  ▼                  │
│  ┌─────────────────────────────┐    │
│  │ RRF Fusion (k=60)           │    │
│  │ combine L2 + L3 scores     │    │
│  │ apply fb:helpful/misleading │   │
│  └──────────┬──────────────────┘    │
└─────────────┼───────────────────────┘
              ▼
    TIERED_CONTEXT.md (injected into agent prompt)
    PROACTIVE_RECALL.md (pre-emptive context hints)
```

#### Maintenance Path (cron)

```
Daily 02:00 (merged cron job):
    │
    ├── session_to_gbrain.py      → incremental session sync
    ├── tiered_context_injector   → refresh TIERED_CONTEXT.md
    ├── memory_lifecycle          → stale/archive check
    └── archive integrity check   → compare memory ↔ gbrain

Mondays:
    └── consistency check         → memory vs skill vs gbrain vs file

15th of month:
    └── TTL degrade               → mark 90d-untouched entries
```

### Component Map

| Component | Type | Language | Dependencies | Lines |
|-----------|------|----------|-------------|-------|
| `tiered_context_injector.py` | Read pipeline | Python | stdlib only | 384 |
| `session_to_gbrain.py` | Write pipeline | Python | stdlib only | 476 |
| `memory_lifecycle.py` | Maintenance | Python | stdlib only | 118 |
| `domain_memory.py` | Routing | Python | stdlib only | 144 |
| `memory_guard.py` | Pre-write guard | Python | stdlib only | 76 |
| `memory_prewrite_guard.py` | Pre-write guard | Python | stdlib only | 58 |
| `compact_memory.py` | Cleanup | Python | stdlib only | 128 |
| `install.sh` | Installer | Bash | — | 100 |
| `installer/install.py` | Installer | Python | stdlib + ruamel.yaml | 127 |

---

## Script Reference

### Core Pipeline Scripts

#### `tiered_context_injector.py` (384 lines)

The central context builder. Runs before every agent session (or on cron) to prepare the best possible context snapshot.

**Key features:**
- Reads session summaries from `state.db` `messages_fts` table
- Applies 30-day half-life decay to FTS5 scores: `score * 0.5^(days_since / 30)`
- Parallel query to gbrain MCP for knowledge graph matches (not fallback)
- RRF fusion (k=60) merges L2 and L3 rankings
- Feedback adjustment: `fb:helpful` +0.1 boost, `fb:misleading` -0.5 penalty
- Outputs `TIERED_CONTEXT.md` and `PROACTIVE_RECALL.md`

**Usage:**
```bash
# Build context with recall topics
python3 tiered_context_injector.py --recall kiki memory stock

# Cron mode (quiet, no console output)
python3 tiered_context_injector.py --cron
```

**L3 query sources:**
- `semantics.db` → `content_chunks` table (7.6K entries, gbrain-style content)
- `archives_fts` → FTS5 archive table (3K entries from pool.db)

#### `session_to_gbrain.py` (476 lines)

Translates ephemeral Hermes session summaries into persistent gbrain knowledge graph nodes.

**Key features:**
- Reads from Hermes `state.db` `sessions` table
- Generates structured gbrain pages with tags, timeline entries, and cross-links
- Incremental processing via checkpoint file (`.gbrain_session_cursor`)
- Skips system broadcasts, non-human messages, already-archived sessions
- Batching with `--batch N` for large backfills

**Usage:**
```bash
# Dry run (preview only)
python3 session_to_gbrain.py --dry-run

# Process next 10 sessions
python3 session_to_gbrain.py --batch 10

# Full backfill
python3 session_to_gbrain.py
```

**Output schema (gbrain page):**
```yaml
slug: session/2026-05-13-analysis
type: session
tags: [stock-analysis, a-share, 2026-05]
timeline: [{date: 2026-05-13, summary: "Daily stock analysis run"}]
content: "[auto-generated session summary]"
```

### Guard & Validation Scripts

#### `memory_guard.py` (76 lines)

Pre-write capacity scanner. Runs before every `memory()` write operation to prevent silent failures when memory is full.

**Behavior:**
- Checks remaining capacity against `MEMORY_LIMIT` (configurable)
- At <20%: emits compaction recommendation
- At <15%: blocks write with clear error message

**Usage:**
```python
from memory_guard import check_capacity
result = check_capacity()
# result = {"remaining": 420, "total": 2200, "needs_compaction": True, "action": "warn"}
```

#### `memory_prewrite_guard.py` (58 lines)

Contradiction detector. Scans existing memory entries for claims that conflict with proposed new content.

**Contradiction patterns (regex-based, zero token cost):**
- Status conflicts: "not working" vs "works great"
- Ownership conflicts: "I handle X" vs "someone else handles X"
- Temporal conflicts: "tomorrow" vs "already done"

**Output:**
```json
{
  "allow_write": true,
  "contradictions": [],
  "suggestion": "add",
  "capacity_check": {"ok": true, "remaining_pct": 68}
}
```

#### `domain_memory.py` (144 lines)

Routes memory entries to the correct domain based on `@domain:` prefix. Manages per-domain quotas independently so one topic can't crowd out another.

**Supported commands:**
```bash
# List entries in a domain
python3 domain_memory.py --domain kiki --list

# Get domain usage stats
python3 domain_memory.py --stats

# Check if a domain has room
python3 domain_memory.py --domain astock --check-capacity
```

#### `compact_memory.py` (128 lines)

Memory compaction tool. Analyzes existing entries and identifies candidates for removal.

**Stale pattern detection:**
- `已完成|已修复|已部署|done|fixed|resolved` — completed tasks
- Entries with no updates in 60+ days
- Entries superseded by newer information

**Usage:**
```bash
# Generate compaction report
python3 compact_memory.py --analyze

# Apply removals (calls memory(action='remove') internally)
python3 compact_memory.py --apply
```

### Utility Scripts

The installer also ships the v2.1.1 script suite for backward compatibility:

| Script | Purpose |
|--------|---------|
| `archive_sessions.py` | Batch session archiving engine |
| `auto_session_summary.py` | Automatic session summarization |
| `gbrain_search.py` | Gbrain knowledge graph search CLI |
| `sync_embeddings.py` | Embedding synchronization for vector search |
| `init_db.py` | Archive database (pool.db) initialization |
| `daily_archive.py` | Daily archive rotation |
| `weekly_cleanup.py` | Weekly maintenance tasks |
| See full list in `scripts/` directory | |

---

## Configuration

### Memory Lifecycle Protection

Create `~/.hermes/memory_lifecycle.yaml` to define pages that should never be auto-archived:

```yaml
# Pages matching these slugs are protected from auto-archive
protected_slugs:
  - my-project-config
  - my-hub-operations

# Pages with these tag values are protected
protected_tags:
  - archive     # protects all pages tagged "archive"
  - hub         # protects all hub pages
  - protected   # manually tagged protected pages
```

If the config file doesn't exist, protection defaults to **off** (no pages are protected). Copy the template from `config/memory_lifecycle.example.yaml`.

### Domain Quotas

Domain quota defaults are defined in `domain_memory.py`. To customize:

```python
# Edit domain_memory.py, DOMAIN_QUOTAS dict:
DOMAIN_QUOTAS = {
    "kiki": 300,
    "astock": 400,
    "promo": 300,
    "system": 300,
    "misc": 300,
}
```

### Tiered Context Parameters

Key tunables in `tiered_context_injector.py`:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `HALF_LIFE_DAYS` | 30 | Speed of FTS5 score decay |
| `TOP_K_L1` | 5 | Recent sessions to include |
| `TOP_K_L2` | 5 | FTS5 results to carry forward |
| `TOP_K_L3` | 3 | gbrain results to carry forward |
| `RRF_K` | 60 | RRF fusion constant (lower = more rank dominance) |
| `FEEDBACK_BOOST` | 0.1 | Score boost for fb:helpful |
| `FEEDBACK_PENALTY` | -0.5 | Score penalty for fb:misleading |

---

## Scheduling

The installer suggests the following cron schedule (configurable during `install.sh`):

| Time (CST) | Task | Frequency |
|------------|------|-----------|
| 02:00 daily | Merged maintenance: session→gbrain sync + lifecycle check + tiered context refresh | Daily |
| 02:00 Mon | Additional: four-way consistency check (memory ↔ skill ↔ gbrain ↔ file) | Weekly |
| 02:00 15th | Additional: TTL degrade (mark 90d-untouched entries) | Monthly |

These are managed through Hermes' built-in cron scheduler. View active jobs with:

```bash
hermes cron list
```

---

## Incremental Sync Architecture

`session_to_gbrain.py` tracks processed sessions via a cursor file to enable efficient incremental operation:

```
~/.hermes/scripts/
├── session_to_gbrain.py        # Main pipeline script
├── .gbrain_session_cursor      # Auto-created checkpoint file
└── ...
```

**How it works:**

1. **First run**: Scans all session summaries in `state.db`, creates gbrain pages for each, writes the last-processed session timestamp to `.gbrain_session_cursor`
2. **Subsequent runs**: Reads the cursor, only processes sessions newer than the cursor
3. **Idempotency**: Already-synced sessions are detected by content hash and skipped
4. **Recovery**: If the pipeline crashes mid-batch, the next run picks up from the last checkpoint

**Design for 6-hour cron cadence:**
- Each run processes at most `--batch N` sessions (default: all pending)
- Typical run processes 0-5 new sessions and completes in <10 seconds
- A full backfill of 100 sessions completes in ~60 seconds

---

## Changelog

### v2.2.0 (2026-05-13)

#### 🚀 New Runtime Scripts (7 new, 1,393 lines added)

```
scripts/tiered_context_injector.py   384 lines  — Tiered context injection v3 with RRF fusion
scripts/session_to_gbrain.py         476 lines  — Hermes session → gbrain knowledge graph pipeline
scripts/memory_lifecycle.py          118 lines  — Page lifecycle state machine (active→stale→archived)
scripts/domain_memory.py             144 lines  — 5-domain memory isolation with per-domain quotas
scripts/memory_guard.py               76 lines  — Pre-write capacity guard with compaction detection
scripts/memory_prewrite_guard.py      58 lines  — Contradiction detection + structured JSON output
scripts/compact_memory.py            128 lines  — Memory compaction v2 with stale pattern matching
```

#### 🔧 Modified Files (4 files)

| File | Changes |
|------|---------|
| `install.sh` | Version 2.1.1→2.2.0; fixed hardcoded `/tmp/memory-repo` paths → relative paths |
| `installer/install.py` | Version label 2.0→2.2 |
| `README.md` / `README_CN.md` | Full documentation update with architecture, changelog, acknowledgments |
| `tests/test_smoke.py` | Fixed hardcoded `/tmp/memory-repo` path; added memory_lifecycle.py and tiered_context_injector.py test coverage |

#### 🔒 Data Safety Fix

- **memory_lifecycle.py**: Moved hardcoded `PROTECTED_SLUGS`/`PROTECTED_TAGS` (containing internal page names) to external YAML config. The repository now ships zero internal data.
- **New**: `config/memory_lifecycle.example.yaml` — placeholder config template with generic example values.

#### 📈 Scale

| Metric | v2.1.1 | v2.2.0 | Δ |
|--------|--------|--------|---|
| Scripts | 13 | 20 | **+54%** |
| Code lines | ~4,200 | ~5,600 | **+33%** |
| Hardcoded internal data | 1 instance | 0 | **✅ Fixed** |
| Hardcoded absolute paths | 3 instances | 0 | **✅ Fixed** |
| Third-party dependencies | 0 | 0 | **✅ Unchanged** |

### v2.1.1 (2026-05-09)
- Default embedding model switched to `intfloat/multilingual-e5-small`
- Model selector with AI assistant auto-install support
- Cross-platform path support (Windows/macOS/Linux)

### v2.1.0 (2026-05-08)
- Multilingual semantic search
- New scripts: embedding server, auto-summarization, gbrain maintenance
- Cross-platform path handling

### v2.0.0 (2026-05-06)
- gbrain knowledge graph integration (Memory 2.0)
- Dual-path search: gbrain + local FTS5
- Auto-summarization and curator self-evolution

---

## Acknowledgments

- **[@mattamundson](https://github.com/mattamundson)** — The [ralph-orchestrator](https://github.com/mattamundson/ralph-orchestrator) project and the ai-agent-memory-patterns issue discussions inspired the config externalization pattern (moving hardcoded protected slugs/tags to YAML config) used in `memory_lifecycle.py`. The snapshot-based memory isolation approach also influenced the domain isolation design.
- **RRF (Reciprocal Rank Fusion)** — The fusion algorithm used in `tiered_context_injector.py` is based on the standard IR formula `score(entry) = Σ 1/(k + rank_i)` with k=60, as described in the information retrieval literature.
- **[gbrain](https://github.com/garrytan/gbrain)** — The knowledge graph engine by garrytan provides the `put_page` / `add_timeline_entry` / `query` MCP interfaces used by `session_to_gbrain.py` and `tiered_context_injector.py`.
- **@domain prefix protocol** — The domain isolation naming convention was established by the user during the v1 development phase.
- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — The upstream `memory()` tool provides the underlying write/read primitives that all pipeline scripts build upon.

All new code (7 runtime scripts, config templates, installer patches, documentation) is original development. Zero third-party Python packages are required beyond the standard library.

---

## License

MIT — see [LICENSE](LICENSE) for details.
