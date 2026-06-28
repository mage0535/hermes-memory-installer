<div align="center">

# Memory Sidecar v3.5.1

**A publishable, agent-agnostic memory sidecar for Hermes, Claude Code, Codex, Cursor, and similar agents.**

[![Version](https://img.shields.io/badge/version-3.5.1-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5.1)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**中文说明**](README_CN.md) | [**Architecture**](ARCHITECTURE.md)

</div>

## What This Is

Memory Sidecar is an external memory system that runs next to an AI agent without patching the agent itself. It reads the agent's data directory, archives sessions, builds long-term knowledge, and injects relevant recall back into future work.

Release `3.5.1` is the operational hardening release for the current public architecture:

- agent-agnostic install flow driven by `AGENT_HOME`
- layered recall across hot, warm, cold, and curated knowledge notes
- clean public repository with no server-specific paths or credentials
- install surface aligned with the actual deployed script set

This repository is suitable for public install feedback from technical users running their own `Hindsight + gbrain + PostgreSQL` environment.

## Why It Was Built

Long-running AI agents tend to lose useful context when work spans many sessions, projects, and knowledge sources. A single prompt-local memory file is not enough for durable recall, and operators need to know when archival, recall, or compaction silently stops working.

Memory Sidecar was built to make memory an installable, observable sidecar rather than a hidden agent-core modification.

## Design Goals

- Keep the agent core untouched.
- Use stable data boundaries such as `AGENT_HOME`, `state.db`, sessions, Hindsight, gbrain, and markdown notes.
- Combine hot, warm, cold, and curated knowledge recall.
- Emit machine-readable health artifacts for automation.
- Keep the public repository free of private server paths, credentials, and production data.

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

`v3.5.1` intentionally separates the generic sidecar from host-specific operations:

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

The public installer deploys 28 runtime, support, and observability scripts into `$AGENT_HOME/scripts/`.

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
- `gbrain_deorphan_index.py`
- `memory_observability_report.py`
- `memory_storage_cross_check.py`
- `runtime_drift_check.py`
- `gbrain_stale_maintenance.py`
- `alert_queue.py`
- `alert_webhook_receiver.py`
- `metrics_dashboard.py`
- `metrics_dashboard_server.py`
- `openmetrics_exporter.py`
- `slo_rollup.py`
- `profile_isolation_soak.py`
- `synthetic_recall_benchmark.py`
- `hindsight_security_audit.py`

Support modules:

- `state_db_schema.py`
- `knowledge_notes.py`
- `recall_samples.py`
- `langsmith_monitor.py`
- `langsmith_task_wrapper.py`
- `langsmith_trend_report.py`

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

Common alternatives:

- `BAAI/bge-small-zh-v1.5`: lightweight Chinese-first deployments.
- `paraphrase-multilingual-MiniLM-L12-v2`: mature sentence-transformers ecosystem.
- `Alibaba-NLP/gte-multilingual-base`: higher quality when RAM headroom is available.
- `sentence-transformers/LaBSE`: cross-language alignment.
- `BAAI/bge-m3`: maximum recall quality with higher resource cost.

## Alerts And Dashboard

`alert_queue.py` normalizes health artifacts into a local queue. `alert_webhook_receiver.py` provides a real local webhook target, can forward `action-needed` alerts to generic webhooks, Slack, Feishu/Lark, DingTalk, or Telegram via private environment variables, and can replay dead-letter rows after a downstream outage.

Alert text is language-adaptive:

- `payload.lang` / `payload.preferred_lang` / `payload.user_lang` takes priority
- for Telegram, a cached per-chat language learned from bot updates takes priority over defaults
- otherwise `MEMORY_ALERT_LANG`, `MEMORY_UI_LANG`, or system locale is used
- current defaults support `zh` and `en`

Telegram note:

- Telegram client language is only learnable after the user has sent at least one message to the bot.
- `telegram_language_sync.py` reads bot updates, stores `chat_id -> lang`, and later outbound alerts reuse that language automatically.

`metrics_dashboard.py` renders a static HTML dashboard. `metrics_dashboard_server.py` can serve HTML, `/api/status` JSON, and `/metrics` OpenMetrics text behind a bearer/query token, and binds to `127.0.0.1` by default. `slo_rollup.py` summarizes acceptance rate, alert queue growth, dead-letter replay success, and recall latency quantiles into `slo-rollup-latest.json`. `synthetic_recall_benchmark.py` provides a private-data-free recall regression fixture for CI.

For shell and monitoring probes:

```bash
hermes-memory status
hermes-memory slo-rollup
hermes-memory openmetrics
```

Grafana dashboards included in the repository:

- [docs/grafana/hermes-memory-home.json](docs/grafana/hermes-memory-home.json): operator home page
- [docs/grafana/hermes-memory-openmetrics-dashboard.json](docs/grafana/hermes-memory-openmetrics-dashboard.json): detailed OpenMetrics dashboard

A ready-to-run Prometheus/Grafana stack template is included in [deploy/observability/README.md](deploy/observability/README.md).

That stack now also includes:

- `prometheus-rules.yml` for default alert rules
- `provision_dashboards.py` to import the dashboards through the Grafana API and set the default Grafana home dashboard

Reverse proxy templates are available in [docs/dashboard-reverse-proxy.md](docs/dashboard-reverse-proxy.md). Release validation steps are listed in [docs/release-checklist.md](docs/release-checklist.md).

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

### v3.5.1 (2026-06-26)

- added local action-needed webhook receiver with optional external forwarding
- added Telegram, Slack, Feishu/Lark, and DingTalk webhook payload adapters
- added inbound webhook queue rotation and token-gated dashboard serving
- added OpenMetrics export, dashboard JSON API, dead-letter replay, SLO rollup, release checksums, a Grafana dashboard template, and synthetic recall benchmarking
- added dual-profile isolation soak checks for multi-agent deployments
- unified public version metadata across installer, CLI, docs, and release notes
- kept embedding model selection: recommended default, common presets, and custom model entry

### v3.5 (2026-06-19)

- public release packaging pass for GitHub distribution
- version alignment across installer, CLI, architecture docs, and manuals
- explicit separation between generic installed runtime and optional Hermes operational helpers
- clearer KMM positioning and integration guidance
- repository license and release-surface cleanup
- published release page: [v3.5](https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5)

For the short GitHub release summary, see [docs/release-v3.5.1.md](docs/release-v3.5.1.md).

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
