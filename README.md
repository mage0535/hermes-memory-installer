<div align="center">

# Memory Sidecar Installer v3.0

**A production-grade sidecar memory system for AI agents.**

[**中文文档**](README_CN.md) | [**English**](README.md)

</div>

---

## What v3.0 Is

Memory Sidecar v3.0 is a **sidecar memory system** for AI agents such as Hermes, Claude Code, Cursor, Codex, and others.  
It does **not** patch the agent's core. Instead, it runs alongside and provides:

- durable session intake and long-term archival
- canonical memory objects with governance indexes
- focused dossiers for important people, projects, and topics
- layered retrieval with intent-aware routing and fusion
- health checks, acceptance checks, and backlog remediation
- optional semantic search via vector embeddings

**Multi-agent support**: all scripts use the `AGENT_HOME` environment variable (backward compatible with `HERMES_HOME`).  
Mount the sidecar to any agent by setting `AGENT_HOME` to the agent's data directory.

---

## Architecture

```text
Agent Core
  └─ writes state.db + session JSON

Sidecar Capture Layer
  └─ session_to_gbrain.py        — incremental session ingestion → gbrain

Sidecar Governance Layer
  ├─ memory_family_registry.py   — query intent classification + focus profiles
  ├─ memory_governance_rebuild.py — canonical objects, hubs, multi-version status, vector index
  └─ memory_guardian.py          — capacity monitoring, consolidation drain, stuck-op recovery

Sidecar Recall Layer
  └─ tiered_context_injector.py  — layered retrieval (L1/L2/L3), RRF fusion, rerank

Sidecar Maintenance + Acceptance
  ├─ memory_maintenance_cycle.py — orchestrator: archive → rebuild → drain → recall → health
  └─ sidecar_acceptance_check.py — production verification suite
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical breakdown.

---

## Quick Start

### Prerequisites

- Python 3.9+
- [gbrain](https://github.com/hi-ogawa/gbrain) installed and serving
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) running (port 8890 by default)
- An agent (Hermes / Claude Code / etc.) already producing sessions

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

The installer deploys the supported sidecar scripts into `$AGENT_HOME/scripts/`, patches `$AGENT_HOME/config.yaml`, and writes install metadata to `$AGENT_HOME/memory-sidecar/install-profile.json`.

### Mount to a Different Agent

```bash
export AGENT_HOME=/home/user/.my-agent
python3 installer/install.py --noninteractive
```

Backward compatible: `--hermes-home` and `HERMES_HOME` env var also work.

### Run One Maintenance Cycle

```bash
AGENT_HOME=/root/.hermes python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py
```

### Run Acceptance Checks

```bash
AGENT_HOME=/root/.hermes python3 $AGENT_HOME/scripts/sidecar_acceptance_check.py
```

---

## What Gets Installed

The supported v3.0 sidecar runtime consists of these 7 scripts:

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

These are the scripts used in the validated production deployment.

---

## How the Sidecar Works

### 1. Session Intake

The agent writes `state.db` and session JSON files normally.  
The sidecar reads them incrementally and tracks progress with a checkpoint.

### 2. Long-Term Archive

`session_to_gbrain.py` converts high-value sessions into gbrain pages, applies tags, writes timeline entries, and links sessions to topic hubs.

### 3. Governance Rebuild

`memory_governance_rebuild.py` rebuilds:

- session indexes (FTS5)
- hindsight indexes
- memory hubs (topic-based theme aggregators)
- canonical memory objects with multi-version status (`active` / `superseded`) and time validity (`valid_from` / `valid_to`)
- conflict groups for deduplication
- dossier metadata
- recall metrics
- **vector embeddings** (when `EMBEDDING_API_URL` is configured)

It also maintains repair infrastructure:
- `orphan_messages` — orphan message audit trail
- `session_repair_map` — message-to-session repair mapping
- `session_lineage_repair` — session parent-chain repair
- `recovered_fragments` — unassignable memory fragment archive
- `memory_aliases` / `memory_relations` — alias and relation graph
- `sessions_effective` view — repaired session view layer

### 4. Layered Retrieval

`tiered_context_injector.py` classifies the query intent and fuses:

- hub summaries (topic-level)
- canonical objects (fact-level, with multi-version status filtering)
- hindsight cache (pre-indexed hindsight memories)
- live hindsight (when policy says it should be used)
- **semantic search** (when vector index is available)
- weak fallback layers only when necessary (FTS5 / LIKE / semantics)

### 5. Health and Remediation

`memory_guardian.py` reports health, trend data, duplicate counts, sync lag, and consolidation backlog signals.  
It includes safe remediation logic for sticky consolidation backlogs and stuck operation detection.

---

## Focused Dossiers

v3.0 introduces the **Focused Dossier** concept.  
A dossier is a first-class memory profile for an important person, relationship, project, event, or topic.  
The production deployment includes a validated relationship dossier , and the shared registry supports extending to more dossiers.

---

## Embedding Model Selection

Embedding models enable **semantic vector search** as an additional retrieval layer in L3 recall.  
When `EMBEDDING_API_URL` is set, the governance rebuild automatically generates 384–1024 dimensional embeddings for each active `memory_object` and stores them in the `canonical_semantic_index` table. During recall, `tiered_context_injector.py` can query this index via cosine similarity alongside keyword-based FTS5 and LIKE paths.

### How it affects retrieval quality

- **semantic recall quality**: vectors capture meaning beyond keyword overlap
- **cross-lingual matching**: Chinese queries can match English content and vice versa
- **dossier clustering**: objects about the same topic are grouped even when wording differs
- **fallback frequency**: richer semantic index reduces reliance on weak LIKE / FTS5 fallbacks

### Deploying an embedding server

The sidecar does not bundle an embedding server. You run one independently and point the sidecar to it via `EMBEDDING_API_URL`.

**Quick start with sentence-transformers** (recommended for development):

```bash
pip install sentence-transformers flask
```

Create a minimal server that serves the OpenAI-compatible `/v1/embeddings` endpoint.  
A reference implementation is included in the community scripts:

```python
# embedding_server.py (example — serve with your chosen model)
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
        self.wfile.write(json.dumps({"data": [{"embedding": e} for e in emb]}).encode())

HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
```

Then set the environment variable and run a governance rebuild:

```bash
export EMBEDDING_API_URL=http://127.0.0.1:8766/v1/embeddings
python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py
```

When `EMBEDDING_API_URL` is not set, the sidecar runs entirely without embeddings — all text-based retrieval (FTS5 / LIKE / hindsight / gbrain) continues to work normally.

### How model selection works during install

During installation, the installer either:
- prompts for a model interactively, or
- accepts `--embedding <model-id>`, or
- uses the recommended default in non-interactive mode

The selected model is recorded in `install-profile.json` as metadata.  
It does **not** automatically deploy the model — you must run the embedding server with the chosen model yourself.

### Supported models

| Model | Languages | Dimension | Size | Best for |
|---|---|---|---:|---|
| `intfloat/multilingual-e5-small` | 100+ languages | 384d | ~470MB | **Recommended default** for mixed Chinese/English deployments |
| `BAAI/bge-small-zh-v1.5` | Chinese focused | 512d | ~96MB | Lowest-resource Chinese-first deployment |
| `paraphrase-multilingual-MiniLM-L12-v2` | 50+ languages | 384d | ~471MB | Mature multilingual sentence-transformers ecosystem |
| `Alibaba-NLP/gte-multilingual-base` | 75+ languages | 768d | ~610MB | Higher multilingual recall quality |
| `sentence-transformers/LaBSE` | 109 languages | 768d | ~471MB | Cross-lingual alignment-heavy workloads |
| `BAAI/bge-m3` | 100+ languages | 1024d | ~2GB | Maximum quality when hardware is generous |

### Recommended default

```text
intfloat/multilingual-e5-small
```

Why:
- strong multilingual coverage (100+ languages)
- good enough quality for production memory recall
- moderate resource cost (~470MB RAM)
- safe default for mixed Chinese / English workloads

Use `BAAI/bge-small-zh-v1.5` only when the deployment is overwhelmingly Chinese and resource-constrained (96MB).

---

## Choosing Your Retrieval Engine

In v3.0, "retrieval engine" is not a single database choice.  
It is the **retrieval profile** that decides how the sidecar prioritizes evidence layers.

### The production profile: Hybrid Sidecar

This repository ships one maintained deployment profile:

- **Hybrid Sidecar** (recommended)

It combines:

| Layer | Source | Role |
|---|---|---|
| L1: Recent sessions | `state.db` sessions table | Immediate context |
| L2: FTS5 + LIKE search | `state.db` messages_fts / messages / sessions | Keyword-based session retrieval |
| L3: Governance objects | `memory_governance.db` (FTS5) | Canonical long-term memory with multi-version filtering |
| L3: Hindsight cache | `memory_governance.db` hindsight_index | Pre-indexed Hindsight memories |
| L3: Memory hubs | `memory_governance.db` memory_hubs | Topic-level theme aggregators |
| L3: **Semantic vectors** | `canonical_semantic_index` | Cosine similarity search (when EMBEDDING_API_URL is configured) |
| Live Hindsight API | Hindsight HTTP API | Real-time fact recall (when policy triggers) |
| Fallback: semantics | `semantics.db` | LIKE-based embedding content search |
| Fallback: archives | `state.db` archives_fts | FTS5 over archived session summaries |

All layers are fused via **RRF (Reciprocal Rank Fusion)** with intent-aware re-ranking.

### How retrieval adapts to query intent

| Need | Dominant layers |
|---|---|
| Current system / provider state | governance objects + system hub |
| Relationship memory | dossier hub + live hindsight + hindsight cache + **semantic** |
| Project delivery | canonical project objects + hindsight cache |
| Broad exploration | wider governance/object evidence, limited fallback |
| Cold archive lookup | gbrain session pages + topic hubs |
| Recent conversation | L1 recent sessions + L2 FTS5 |

### Why "engine swapping" was dropped

Older drafts described the project as if you could freely swap PostgreSQL, Elasticsearch, SQLite, and other engines.  
That was not the final production reality. The validated system is:

- **sidecar-first**
- **agent-agnostic** (AGENT_HOME-based)
- **Hindsight-backed**
- **gbrain-archived**
- **governance-indexed**
- **semantically-enhanced** (optional vector index)

This narrower definition makes the repository cleaner, more maintainable, and reliably redeployable.

---

## Operational Workflow

```text
Agent writes new sessions
  -> session_to_gbrain.py ingests archive candidates
  -> memory_governance_rebuild.py refreshes objects / hubs / metrics / vectors
  -> memory_guardian.py checks backlog and health
  -> tiered_context_injector.py generates layered recall artifacts
  -> Agent consumes the resulting context when needed
```

## Validation Workflow

For production changes:

1. develop locally
2. compile locally
3. back up server scripts
4. deploy to `$AGENT_HOME/scripts/`
5. run `memory_maintenance_cycle.py`
6. run `sidecar_acceptance_check.py`
7. confirm live agent regression queries still behave correctly

## Repository Layout

```text
installer/     install entrypoints, config patch helpers, environment checks
scripts/       final sidecar runtime scripts (7 supported scripts)
skills/        agent-side memory skills
templates/     archive / skill templates
tests/         import and smoke validation for the repository
```

---

## Acknowledgements

### Core projects and ecosystems

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — the original agent that this sidecar was built alongside
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) — short-to-medium term memory graph
- [gbrain](https://github.com/hi-ogawa/gbrain) — personal knowledge graph engine
- [sentence-transformers](https://www.sbert.net/) — embedding model framework
- [OpenCode](https://opencode.ai) — intelligent coding assistant that guided the design
- [PostgreSQL](https://www.postgresql.org/) — gbrain backing store
- [pgvector](https://github.com/pgvector/pgvector) — vector extension for PostgreSQL
- [SQLite](https://www.sqlite.org/) — state.db and governance.db backing store
- [FTS5](https://www.sqlite.org/fts5.html) — full-text search engine for session and object indexes

### Embedding model providers

- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [sentence-transformers/LaBSE](https://huggingface.co/sentence-transformers/LaBSE)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)

### Community feedback

Thanks to the users who reported edge cases, memory misses, multilingual recall problems, sticky consolidation signals, and operational issues through:

- **GitHub Issues** — bugs, feature requests, and architecture discussions
- **GitHub Discussions** — design reviews and deployment questions
- **Reddit** — r/LocalLLaMA, r/MachineLearning, and other communities
- **V2EX** — Chinese-language user feedback and problem reports
- **Direct server-side production feedback** — Hermes users who shared real-world recall misses and performance data

Those reports materially shaped the final v3.0 sidecar design — from the initial 4-layer architecture through multi-agent support, conflict-group deduplication, multi-version status, time validity, and the optional vector index.

---

## License

This project is provided for reference and deployment use.  
See individual dependencies for their respective licenses.
