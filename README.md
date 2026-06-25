<div align="center">

# Memory Sidecar v3.5

**A publishable, agent-agnostic memory sidecar for Hermes, Claude Code, Codex, Cursor, and similar agents.**

[![Version](https://img.shields.io/badge/version-3.5-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**中文说明**](README_CN.md) | [**Architecture**](ARCHITECTURE.md)

</div>

## What This Is

Memory Sidecar is an external memory system that runs next to an AI agent without patching the agent itself. It reads the agent's data directory, archives sessions, builds long-term knowledge, and injects relevant recall back into future work.

Release `3.5` is the public packaging pass for the current architecture:

- agent-agnostic install flow driven by `AGENT_HOME`
- layered recall across hot, warm, cold, and curated knowledge notes
- clean public repository with no server-specific paths or credentials
- install surface aligned with the actual deployed script set

This repository is suitable for public install feedback from technical users running their own `Hindsight + gbrain + PostgreSQL` environment.

## How It Works

The sidecar follows a simple operational loop:

1. Read the agent's state and session data from `AGENT_HOME`
2. Archive new sessions into gbrain and the session search index
3. Rebuild governance indexes and curated knowledge note indexes
4. Generate tiered recall context for the next agent turn
5. Run health checks and acceptance checks so failures stay visible

## What It Improves

The sidecar is designed to improve memory in three concrete ways:

1. It archives session output into durable stores instead of letting history disappear with a single conversation window.
2. It retrieves context from multiple layers instead of relying on one prompt-local memory file.
3. It lets curated knowledge notes participate in recall, so project playbooks and wiki pages can influence future answers.

## Public Release Scope

`v3.5` intentionally separates the generic sidecar from host-specific operations:

- Installed by default: the generic multi-agent sidecar runtime, installer, CLI, and memory skills.
- In this repository but not installed by default: `memory_watermark.py` and `memory_snapshot_backup.py`.

Those two operational helpers are Hermes-oriented maintenance scripts with stronger host assumptions, so they are **not installed by default** in the public multi-agent path.

## Requirements

- Python `3.9+`
- PostgreSQL `16`
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) running and reachable
- [gbrain](https://github.com/hi-ogawa/gbrain) running and reachable
- An agent data directory containing `state.db` and session files

Supported examples:

- Hermes Agent
- Claude Code
- Codex / Codex-style local agents
- Cursor-style shared data directory setups

## Quick Start

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

export AGENT_HOME="$HOME/.hermes"   # or ~/.claude, ~/.cursor, ~/.agent, etc.
./install.sh
```

Non-interactive mode:

```bash
./install.sh --noninteractive --agent-home "$HOME/.my-agent"
```

## Install Modes

The installer supports three install modes for dependency assistance:

- `--install-mode 3`
  Default. Tries the most automatic dependency bootstrap path first.
- `--install-mode 2`
  Guided dependency assistance. Shows the recommended commands and lets you continue step by step.
- `--install-mode 1`
  Detection-only mode. Does not change the system and prints what is missing.

If mode `3` fails, re-run with:

```bash
./install.sh --install-mode 2
```

If mode `2` still does not work, fall back to:

```bash
./install.sh --install-mode 1
```

The installer also supports bilingual output:

```bash
./install.sh --lang en
./install.sh --lang zh
```

When `--lang` is omitted, the installer falls back to locale detection.

After install:

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## Installed Script Set

The public installer deploys 10 runtime entry scripts and 3 support modules into `$AGENT_HOME/scripts/`.

Entry scripts:

- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_family_registry.py`
- `tiered_context_injector.py`
- `memory_maintenance_cycle.py`
- `sidecar_acceptance_check.py`
- `archive_sessions.py`
- `auto_session_summary.py`
- `memory_observability_report.py`

Support modules:

- `state_db_schema.py`
- `knowledge_notes.py`
- `recall_samples.py`

Optional repository-only helpers:

- `memory_watermark.py`
- `memory_snapshot_backup.py`

## Repository Structure

- `installer/` contains the install entrypoint and environment checks
- `scripts/` contains the runtime sidecar entry scripts and support modules
- `skills/` contains agent-side memory skills
- `templates/` contains reusable memory templates
- `docs/` contains planning, verification, and release notes

## Knowledge Integration

Memory Sidecar can consume curated markdown knowledge in addition to session history.

By default, governance rebuild checks:

- `$AGENT_HOME/knowledge/notes`
- legacy knowledge layouts such as `$AGENT_HOME/knowledge/wiki/wiki`

These notes are indexed into a dedicated `knowledge` recall layer and participate in fused retrieval alongside session search, Hindsight facts, and gbrain results.

## Knowledge-and-Memory-Management

For a larger knowledge workflow, pair this project with [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management).

That project extends the sidecar with:

- structured knowledge collection pipelines
- wiki and note management
- broader sync and ingestion tooling
- a larger operating model for "where knowledge comes from and how it is maintained"

Practical boundary:

- `hermes-memory-installer` is the memory sidecar runtime and installer
- `Knowledge-and-Memory-Management` is the upstream knowledge capture and curation layer

Used together, KMM supplies curated notes and source material, and Memory Sidecar turns that material into recallable context for agents.

## Embeddings

Semantic recall is optional but recommended. The installer records the selected model, while the embedding service itself is run separately.

## Embedding Model Selection

The installer keeps the interactive embedding model selection flow.

- You can pick from multiple built-in models during install.
- You can still pass a model directly with `--embedding`.
- In interactive mode, you can choose a custom model id as well.

Recommended default:

- `intfloat/multilingual-e5-small`

Without embeddings, text retrieval still works through:

- FTS5 session search
- Hindsight recall
- gbrain keyword retrieval
- curated knowledge note indexing

## Compatibility Position

The public packaging target is compatibility through stable data boundaries, not through deep agent-specific hooks.

Expected agent-side assumptions:

- a writable agent home directory
- `state.db`
- session files in a readable location
- ability to run Python helper scripts outside the agent process

That boundary is what keeps the project usable across multiple agents.

## Validation

The repository is validated locally with:

- unit and regression tests
- installer rollback tests
- multi-layer recall tests
- public repository hygiene checks

For operators, the main validation command after install is:

```bash
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## Changelog

### v3.5 (2026-06-19)

- public release packaging pass for GitHub distribution
- version alignment across installer, CLI, architecture docs, and manuals
- explicit separation between generic installed runtime and optional Hermes operational helpers
- clearer KMM positioning and integration guidance
- repository license and release-surface cleanup
- published release page: [v3.5](https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5)

### v3.5.1 (2026-06-20)

- added bilingual installer output (`zh` / `en`)
- added install modes `1 / 2 / 3` with downgrade guidance
- kept embedding model selection and custom model entry in the installer
- documented fallback paths for dependency assistance

For the short GitHub release summary, see [docs/release-v3.5.md](docs/release-v3.5.md).

### v3.2 (2026-06-08)

- added observability reporting
- moved token configuration to environment-driven paths
- refined sidecar documentation and runtime layout

### v3.1.0 (2026-06-02)

- simplified the architecture to a 3-layer memory stack
- removed the old agentmemory bridge
- adopted `AGENT_HOME` for agent-agnostic installs

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [MANUAL_INSTALL.md](MANUAL_INSTALL.md)
- [MANUAL_INSTALL_CN.md](MANUAL_INSTALL_CN.md)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

## Acknowledgements

Reference projects:

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

Community and user feedback sources that shaped the current public package:

- GitHub issues and discussions
- direct production feedback from operators
- feedback about recall quality, install friction, and multi-agent compatibility

## License

MIT.
