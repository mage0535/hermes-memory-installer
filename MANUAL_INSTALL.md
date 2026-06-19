# Hermes Memory Installer v3.5 Manual Installation

This guide is for operators who want the generic public sidecar installed manually instead of using `./install.sh`.

## Scope

The manual path installs the public `v3.5` sidecar runtime:

- session archive to gbrain
- governance rebuild
- layered recall
- guardian health checks
- acceptance validation
- curated knowledge-note indexing

It does not patch agent source code.

It does not install `memory_watermark.py` or `memory_snapshot_backup.py`; those repository helpers are optional host-specific operations and are not part of the default public install set.

## Installer Modes

The wrapper installer supports 3 dependency-assistance modes before sidecar deployment starts:

- `--install-mode 3`
  Default automatic-first path for beginners.
- `--install-mode 2`
  Guided assistance mode.
- `--install-mode 1`
  Detection-only mode.

Fallback order:

1. Try mode `3`
2. If mode `3` fails, switch to mode `2`
3. If mode `2` still fails, switch to mode `1`

The wrapper installer also supports:

- `--lang en`
- `--lang zh`

## Embedding Model Selection

The wrapper installer keeps the embedding model selection flow.

- interactive selection from built-in models
- direct model override with `--embedding`
- custom model id entry in interactive mode

## Prerequisites

- Python `3.9+`
- `pip`
- PostgreSQL `16`
- reachable Hindsight service
- reachable gbrain service
- an agent home directory with `state.db` and session files

Installer helper dependency:

```bash
python3 -m pip install "PyYAML>=6.0"
```

## Core Installed Script Set

Create the target scripts directory:

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.hermes}"
mkdir -p "$AGENT_HOME/scripts"
```

Copy the installed runtime entry scripts:

```bash
cp scripts/session_to_gbrain.py "$AGENT_HOME/scripts/"
cp scripts/memory_governance_rebuild.py "$AGENT_HOME/scripts/"
cp scripts/memory_guardian.py "$AGENT_HOME/scripts/"
cp scripts/memory_family_registry.py "$AGENT_HOME/scripts/"
cp scripts/tiered_context_injector.py "$AGENT_HOME/scripts/"
cp scripts/memory_maintenance_cycle.py "$AGENT_HOME/scripts/"
cp scripts/sidecar_acceptance_check.py "$AGENT_HOME/scripts/"
cp scripts/archive_sessions.py "$AGENT_HOME/scripts/"
cp scripts/auto_session_summary.py "$AGENT_HOME/scripts/"
cp scripts/memory_observability_report.py "$AGENT_HOME/scripts/"
```

Copy the support modules:

```bash
cp scripts/state_db_schema.py "$AGENT_HOME/scripts/"
cp scripts/knowledge_notes.py "$AGENT_HOME/scripts/"
cp scripts/recall_samples.py "$AGENT_HOME/scripts/"
chmod +x "$AGENT_HOME/scripts/"*.py
```

## Skills

```bash
mkdir -p "$AGENT_HOME/skills"
cp -r skills/memory-starter-kit "$AGENT_HOME/skills/"
cp -r skills/memory-archivist "$AGENT_HOME/skills/"
cp -r skills/memory-proactive "$AGENT_HOME/skills/"
```

## Agent Config

If your agent uses `config.yaml`, the minimum expected entries are:

```yaml
memory:
  provider: hindsight

skills:
  - memory-starter-kit
  - memory-archivist
  - memory-proactive

memory_sidecar:
  version: "3.5"
  profile: hybrid
  scripts_dir: /path/to/agent-home/scripts
```

Merge into existing config instead of replacing it wholesale.

## Embedding Profile Metadata

Record the selected embedding model so the deployment is reproducible:

```bash
mkdir -p "$AGENT_HOME/memory-sidecar"
cat > "$AGENT_HOME/memory-sidecar/install-profile.json" <<'EOF'
{
  "version": "3.5",
  "profile": "hybrid",
  "embedding_model": {
    "model_id": "intfloat/multilingual-e5-small"
  }
}
EOF
```

## First Run

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

Expected result:

- maintenance returns `ok: true`
- archive, governance rebuild, recall generation, and guardian checks succeed
- acceptance checks return pass output

## Knowledge-and-Memory-Management

For upstream knowledge collection and curation, pair this sidecar with [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management).

Operational relationship:

- KMM manages source knowledge, curated notes, ingestion flows, and broader knowledge operations
- Memory Sidecar indexes curated notes and turns them into recallable context for agents

The sidecar will index:

- `$AGENT_HOME/knowledge/notes`
- legacy paths such as `$AGENT_HOME/knowledge/wiki/wiki`

## Gray / Isolated Runtime Variables

For gray testing or isolated deployments, these optional environment variables can override default paths:

- `MEMORY_STATE_DB_PATH`
- `MEMORY_GOVERNANCE_DB_PATH`
- `MEMORY_KNOWLEDGE_NOTES_DIR`
- `MEMORY_OUTPUT_CONTEXT_PATH`
- `MEMORY_OUTPUT_RECALL_PATH`

## Optional Repository Helpers

These scripts exist in the repository but are not part of the generic public install set:

- `memory_watermark.py`
- `memory_snapshot_backup.py`

Only add them deliberately if your host environment matches their operational assumptions.

## Troubleshooting

| Problem | Meaning | First check |
|---------|---------|-------------|
| `ok=false` in maintenance | One of the sidecar stages failed | Re-run the failed stage directly and inspect stderr |
| Acceptance fails on one query | Retrieval policy regressed or a dependency is missing | Run `tiered_context_injector.py` directly and inspect results |
| gbrain lookup fails | Cold layer unavailable | Check gbrain health and credentials |
| Hindsight lookup fails | Warm layer unavailable | Check Hindsight health and PostgreSQL reachability |
| Knowledge notes missing | KMM/knowledge path not indexed | Check `MEMORY_KNOWLEDGE_NOTES_DIR` and governance rebuild output |
