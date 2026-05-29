<div align="center">

# Hermes Memory Installer v3.0

**A production sidecar memory system for Hermes Agent.**

[**中文文档**](README_CN.md) | [**English**](README.md)

</div>

---

## What v3.0 Is

Hermes Memory Installer v3.0 is a **sidecar memory system**. It does **not** patch Hermes core.  
Instead, it runs beside Hermes and provides:

- durable session intake
- long-term archive pages in gbrain
- canonical memory objects and governance indexes
- focused dossiers for important people / projects / topics
- layered retrieval for Hermes to reference when it needs memory
- health checks, acceptance checks, and backlog remediation

This repository now reflects the **final production layout** that is deployed on the live server.

## What It Solves

Hermes has a strong conversation loop, but long-lived work needs more than a prompt-local memory tool.

v3.0 adds:

- **durability**: memory survives across sessions, restarts, and weeks
- **organization**: memory is grouped into hubs, canonical objects, and dossiers
- **layered recall**: hot facts, governance objects, archive pages, and fallback search are fused deliberately
- **operational safety**: the sidecar is observable and testable without modifying Hermes core

## Final v3.0 Architecture

```text
Hermes Core
  └─ writes state.db + session JSON

Sidecar Capture Layer
  └─ session_to_gbrain.py

Sidecar Governance Layer
  ├─ memory_family_registry.py
  ├─ memory_governance_rebuild.py
  └─ memory_guardian.py

Sidecar Recall Layer
  └─ tiered_context_injector.py

Sidecar Maintenance + Acceptance
  ├─ memory_maintenance_cycle.py
  └─ sidecar_acceptance_check.py
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the technical breakdown.

## Quick Start

### Install

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
python3 installer/install.py
```

Non-interactive install with explicit embedding model:

```bash
python3 installer/install.py --noninteractive --embedding intfloat/multilingual-e5-small
```

The installer deploys the supported sidecar scripts into `~/.hermes/scripts/`, patches `~/.hermes/config.yaml`, and writes install metadata to `~/.hermes/memory-sidecar/install-profile.json`.

### Run One Maintenance Cycle

```bash
~/.hermes/scripts/memory_maintenance_cycle.py
```

### Run Acceptance Checks

```bash
~/.hermes/scripts/sidecar_acceptance_check.py
```

## What Gets Installed

The supported v3.0 sidecar runtime is the following script set:

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

These are the scripts currently used in the validated production deployment.

## How the Sidecar Works

### 1. Session Intake

Hermes continues to write `state.db` and session JSON files.  
The sidecar reads those files incrementally and tracks progress with a checkpoint.

### 2. Long-Term Archive

`session_to_gbrain.py` converts high-value sessions into gbrain pages, applies tags, writes timeline entries, and links sessions to topic hubs.

### 3. Governance Rebuild

`memory_governance_rebuild.py` rebuilds:

- session indexes
- hindsight indexes
- memory hubs
- canonical memory objects
- dossier metadata
- recall metrics

### 4. Layered Retrieval

`tiered_context_injector.py` classifies the query and fuses:

- hub summaries
- canonical objects
- hindsight cache
- live hindsight (when policy says it should be used)
- weak fallback layers only when necessary

### 5. Health and Remediation

`memory_guardian.py` reports health, trend data, duplicate counts, sync lag, and consolidation backlog signals.  
It also includes safe remediation logic for sticky consolidation backlogs.

## Focused Dossiers

v3.0 introduces the **Focused Dossier** concept.

A dossier is a first-class memory profile for an important person, relationship, project, event, or topic.  
The current production deployment includes a validated relationship dossier (`kiki`) and the code is structured so more dossiers can be added through the shared registry.

## Embedding Model Selection

Embedding models matter because they affect:

- semantic recall quality
- cross-lingual matching quality
- dossier clustering quality
- long-term archive retrieval quality
- CPU / RAM / disk footprint

### How model selection works

During installation, the installer either:

- prompts for a model interactively, or
- accepts `--embedding <model-id>`, or
- uses the recommended default in non-interactive mode

### Supported models

| Model | Languages | Size | Best for |
|---|---|---:|---|
| `intfloat/multilingual-e5-small` | 100+ languages | ~470MB | Recommended default for mixed Chinese/English Hermes deployments |
| `BAAI/bge-small-zh-v1.5` | Chinese focused | ~96MB | Lowest-resource Chinese-first deployment |
| `paraphrase-multilingual-MiniLM-L12-v2` | 50+ languages | ~471MB | Mature multilingual sentence-transformers ecosystem |
| `Alibaba-NLP/gte-multilingual-base` | 75+ languages | ~610MB | Higher multilingual recall quality |
| `sentence-transformers/LaBSE` | 109 languages | ~471MB | Cross-lingual alignment-heavy workloads |
| `BAAI/bge-m3` | 100+ languages | ~2GB | Maximum quality when hardware is generous |

### Recommended default

The recommended default is:

```text
intfloat/multilingual-e5-small
```

Why:

- strong multilingual coverage
- good enough quality for production Hermes memory
- moderate resource cost
- safe default for mixed Chinese / English recall

Use `BAAI/bge-small-zh-v1.5` only when the deployment is overwhelmingly Chinese and resource-constrained.

## Choosing Your Retrieval Engine

In the final v3.0 design, “retrieval engine” is not a single database choice.  
It is the **retrieval profile** that decides how the sidecar prioritizes layers.

### The supported production profile: Hybrid Sidecar

This repository ships one maintained deployment profile:

- **Hybrid Sidecar** (recommended)

It combines:

- Hermes `state.db` / session history
- Hindsight for live semantic memory
- governance objects for canonical long-term memory
- gbrain pages for durable archive pages and topic hubs

This is the profile used by the validated production deployment.

### How to think about retrieval in practice

| Need | Layer that usually leads |
|---|---|
| current system / provider state | governance objects + system hub |
| relationship memory | dossier hub + live hindsight + hindsight cache |
| project delivery memory | canonical project objects + hindsight cache |
| broad exploration memory | wider governance/object evidence, limited fallback |
| cold archive lookup | gbrain session pages and topic hubs |

### Why v3.0 does not market “engine agnostic” anymore

Older drafts described the project as if you could freely swap PostgreSQL, Elasticsearch, SQLite, and other engines.  
That was not the final production reality.

The final validated system is:

- **sidecar-first**
- **Hermes-compatible**
- **Hindsight-backed**
- **gbrain-archived**
- **governance-indexed**

That narrower definition is intentional: it makes the repository cleaner and redeployable.

## Operational Workflow

```text
Hermes writes new sessions
  -> session_to_gbrain.py ingests archive candidates
  -> memory_governance_rebuild.py refreshes objects / hubs / metrics
  -> memory_guardian.py checks backlog and health
  -> tiered_context_injector.py generates layered recall artifacts
  -> Hermes consumes the resulting context when needed
```

## Validation Workflow

For production changes, the expected workflow is:

1. develop locally
2. compile locally
3. back up server scripts
4. deploy to `~/.hermes/scripts/`
5. run `memory_maintenance_cycle.py`
6. run `sidecar_acceptance_check.py`
7. confirm live Hermes regression queries still behave correctly

## Current Known State

The current production deployment is healthy, but one signal is intentionally still exposed:

- sticky Hindsight consolidation backlog can exist in a **flat / controlled** state
- sidecar remediation logic detects, drains, and safely guards restart behavior
- this is observable, not hidden

That is by design: v3.0 prefers explicit operational visibility over silent failure.

## Repository Layout

```text
installer/   install entrypoints and config patch helpers
scripts/     final sidecar runtime scripts
skills/      Hermes-side memory skills
templates/   archive / skill templates
tests/       import and smoke validation for the repository
```

## Acknowledgements

### Core projects and ecosystems

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain) and the surrounding personal knowledge graph workflow
- [sentence-transformers](https://www.sbert.net/)
- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [sentence-transformers/LaBSE](https://huggingface.co/sentence-transformers/LaBSE)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
- [PostgreSQL](https://www.postgresql.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [SQLite](https://www.sqlite.org/)

### Community feedback

Thanks to the users who reported edge cases, memory misses, multilingual recall problems, and operational issues through:

- GitHub issues
- GitHub discussions
- Reddit threads
- V2EX and other community forums
- direct server-side production feedback from Hermes users

Those reports materially shaped the final v3.0 sidecar design.
