# Hermes Memory Installer v3.0 Architecture

This document describes the final **v3.0 sidecar architecture** that is intended to be deployed next to a live Hermes installation.

Hermes itself remains the conversation runtime. This project provides a **memory sidecar** that:

- reads Hermes session output,
- organizes important memories into long-term structures,
- rebuilds retrieval indexes,
- prepares layered recall context,
- and exposes operational health signals.

It does **not** patch Hermes core.

## Design Goals

The final v3.0 architecture is designed around five production goals:

1. **Lossless durability**
   Hermes sessions remain the source of truth. The sidecar may summarize, index, or archive them, but it does not depend on destructive cleanup.
2. **Layered recall**
   Retrieval is not “one database search”. The sidecar blends hot, warm, and cold memory layers.
3. **Focused memory management**
   Important people, projects, incidents, or topics can become explicit dossiers instead of staying buried in session fragments.
4. **Operational visibility**
   Queue backlog, sync lag, duplicate ingestion, and rebuild health are visible instead of hidden.
5. **Low coupling**
   Hermes upgrades should not require rewriting the sidecar. The integration boundary is Hermes state, sessions, skills, and sidecar-generated artifacts.

## Runtime Layers

### 1. Source-of-Truth Layer

This layer is owned by Hermes.

- `state.db`
- session files under `~/.hermes/sessions/`

Purpose:

- preserve original conversations,
- preserve chronology,
- support post-hoc recovery and audit.

This layer is never treated as disposable cache.

### 2. Fact Extraction Layer

This layer extracts higher-value memory from raw sessions.

- Hindsight
- sidecar archive intake
- session summaries

Purpose:

- extract reusable facts,
- detect recurring entities and topics,
- maintain a shorter-path memory substrate for active recall.

### 3. Governance Layer

This is the sidecar’s control plane.

- `memory_governance.db`
- `memory_governance_rebuild.py`
- `memory_family_registry.py`

Purpose:

- normalize multi-source memory,
- build hubs and canonical objects,
- enforce family and mode policies,
- track recall and maintenance metrics.

### 4. Recall Layer

This is where query-time layering happens.

- `tiered_context_injector.py`

Purpose:

- classify query family and mode,
- assemble hub/object/hindsight/fallback evidence,
- suppress weak fallback when strong evidence exists,
- return structured recall for Hermes to consume.

### 5. Operations Layer

- `memory_maintenance_cycle.py`
- `memory_guardian.py`
- `sidecar_acceptance_check.py`

Purpose:

- orchestrate maintenance,
- drain and monitor backlog,
- surface queue trends and sync lag,
- run consistent acceptance checks.

## Core Script Set

The supported production script set for v3.0 is:

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

These are the scripts installed by `installer/install.py`.

## Data Stores

### Hermes `state.db`

Role:

- original session store,
- search fallback,
- audit and replay source.

### Hindsight

Role:

- short- and medium-horizon fact store,
- live recall for relationship and context-heavy queries,
- consolidation target for extracted memory.

### `memory_governance.db`

Role:

- sidecar metadata and retrieval control plane.

Current important logical groups:

- session index
- hindsight index
- memory hubs
- memory objects
- recall metrics
- governance meta

### gbrain

Role:

- long-term archive pages,
- hubs, tags, links, and timeline edges,
- durable sidecar archive target.

## Query Families and Modes

v3.0 intentionally routes different kinds of requests differently.

### Provider / System

Modes:

- `config`
- `runtime`
- `tooling`

Examples:

- `hermes gateway provider` -> config-first
- `gateway restart error switching model` -> runtime / incident

### Project

Modes:

- `delivery`
- `exploration`
- `project`

Examples:

- `github script deploy` -> delivery-first
- `search open source automation tools` -> exploration-first

### Relationship / Dossier

This family powers focused dossiers such as `kiki`.

Behavior:

- dossier-first interpretation
- strong preference for live Hindsight
- timeline-aware organization

## Focused Dossier Model

v3.0 generalizes “important topic handling” into **Focused Dossiers**.

A dossier is a high-priority long-term memory profile with:

- aliases,
- topic markers,
- retention priority,
- timeline preference,
- recall preference.

`kiki` is the first production dossier instance, but the architecture is meant for additional future dossiers such as:

- important people,
- major projects,
- long-running incidents,
- strategy themes,
- operational domains.

## Maintenance Workflow

The standard v3.0 maintenance cycle is:

1. session archive intake,
2. governance rebuild,
3. tiered recall generation,
4. guardian health snapshot.

In practical terms:

- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `tiered_context_injector.py`
- `memory_guardian.py --status`

The cycle appends guardian history snapshots so backlog trends can be inspected over time.

## Backlog and Recovery Model

v3.0 includes explicit management for sticky Hindsight consolidation backlog.

Observed production issue:

- backlog can become sticky while failures remain zero,
- duplicate consolidation requests may map to the same in-flight operation,
- queue pressure can plateau instead of draining.

v3.0 mitigation:

- trend and stickiness detection,
- stuck operation detection,
- controlled drain path,
- guarded service restart with cooldown,
- acceptance and health verification after maintenance.

This is intentionally operationally explicit rather than silently optimistic.

## Installation Contract

The installer’s job is to:

- copy the supported sidecar scripts,
- patch Hermes config safely,
- record sidecar install metadata,
- let the operator choose an embedding model,
- keep project versioning on `3.0`.

The installer is not responsible for:

- rewriting Hermes core,
- creating a custom retrieval engine matrix,
- replacing Hindsight or gbrain.

## Embedding Model Role

Embedding models in v3.0 are deployment metadata and retrieval-quality configuration, not the main runtime “engine switch”.

They affect:

- semantic similarity quality,
- multilingual recall quality,
- resource footprint,
- long-term archive search quality.

The installer records the selected model in the install profile so the operator can reproduce or audit a deployment later.

## Acceptance Baseline

The production regression set used during development is:

- `hermes gateway provider`
- `gateway restart error switching model`
- `github script deploy`
- `search open source automation tools`
- `模型用量`
- `kiki`

The project should be considered deployable only if:

- maintenance is `ok`,
- acceptance passes,
- core services are active,
- no new sidecar regression is introduced.

## Architecture Boundary

The final v3.0 project boundary is:

- **inside Hermes**: session generation, Hermes memory tool, Hermes runtime
- **inside the sidecar**: archive, governance, dossiering, recall, health

That boundary is the main reason this design is maintainable across Hermes upgrades.
