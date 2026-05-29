# Hermes Memory Installer v3.0 Manual Installation

For operators who want to deploy the final sidecar manually instead of using the wrapper installer.

## What This Manual Installs

The manual path installs the supported **v3.0 sidecar**:

- governance rebuild
- layered recall
- archive sync to gbrain
- guardian health monitoring
- acceptance checks

It does **not** patch Hermes core.

## Prerequisites

- Hermes already installed
- Python 3.9+
- `pip` available
- Hindsight already configured as the Hermes memory provider
- gbrain available on the host

Python dependency for the installer helpers:

```bash
python3 -m pip install PyYAML
```

## Core Script Set

The supported runtime script set is:

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

## 1. Copy Scripts

From the repository root:

```bash
mkdir -p ~/.hermes/scripts
cp scripts/memory_family_registry.py ~/.hermes/scripts/
cp scripts/memory_governance_rebuild.py ~/.hermes/scripts/
cp scripts/memory_guardian.py ~/.hermes/scripts/
cp scripts/memory_maintenance_cycle.py ~/.hermes/scripts/
cp scripts/session_to_gbrain.py ~/.hermes/scripts/
cp scripts/sidecar_acceptance_check.py ~/.hermes/scripts/
cp scripts/tiered_context_injector.py ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/*.py
```

## 2. Copy Skills

```bash
mkdir -p ~/.hermes/skills
cp -r skills/memory-starter-kit ~/.hermes/skills/
cp -r skills/memory-archivist ~/.hermes/skills/
cp -r skills/memory-proactive ~/.hermes/skills/
```

## 3. Patch Hermes Config

Edit `~/.hermes/config.yaml` so it contains at least:

```yaml
memory:
  provider: hindsight

skills:
  - memory-starter-kit
  - memory-archivist
  - memory-proactive

memory_sidecar:
  version: "3.0"
  profile: hybrid
  scripts_dir: ~/.hermes/scripts
```

If your existing file already contains more settings, merge these entries instead of replacing the entire config.

## 4. Choose an Embedding Model

v3.0 records the chosen embedding model as deployment metadata so the retrieval setup is reproducible.

Recommended default:

- `intfloat/multilingual-e5-small`

Other common options:

- `BAAI/bge-small-zh-v1.5`
- `paraphrase-multilingual-MiniLM-L12-v2`
- `Alibaba-NLP/gte-multilingual-base`
- `sentence-transformers/LaBSE`
- `BAAI/bge-m3`

Record the chosen model in:

```bash
mkdir -p ~/.hermes/memory-sidecar
cat > ~/.hermes/memory-sidecar/install-profile.json <<'EOF'
{
  "version": "3.0",
  "profile": "hybrid",
  "embedding_model": {
    "model_id": "intfloat/multilingual-e5-small"
  }
}
EOF
```

## 5. Verify gbrain Access

The sidecar expects `gbrain` to be callable on the host, typically from:

- `/root/.bun/bin/gbrain`

Basic checks:

```bash
gbrain doctor --fast
gbrain list -n 3
```

## 6. Run Maintenance Once

```bash
python3 ~/.hermes/scripts/memory_maintenance_cycle.py
```

Expected result:

- `ok: true`
- `session_to_gbrain`, `memory_governance_rebuild`, `tiered_context_generate`, and `memory_guardian_status` all succeed

## 7. Run Acceptance

```bash
python3 ~/.hermes/scripts/sidecar_acceptance_check.py
```

This validates the standard regression set:

- `hermes gateway provider`
- `gateway restart error switching model`
- `github script deploy`
- `search open source automation tools`
- `模型用量`
- `kiki`

## 8. Optional CLI Helper

If you want the local helper command:

```bash
mkdir -p ~/.local/bin
cp bin/hermes-memory ~/.local/bin/hermes-memory
chmod +x ~/.local/bin/hermes-memory
```

Then:

```bash
hermes-memory doctor
hermes-memory maintenance
hermes-memory acceptance
```

## 9. Ongoing Operation

The sidecar is designed to run next to Hermes, not inside Hermes core.

Recommended routine:

- run `memory_maintenance_cycle.py` on a schedule
- review `memory_guardian.py --status`
- inspect `~/.hermes/metrics/guardian_status_history.jsonl`

## Troubleshooting

| Problem | Meaning | First check |
|---------|---------|-------------|
| `ok=false` in maintenance | One of the sidecar stages failed | Re-run stage manually and inspect stderr |
| `pending_consolidation` grows | Hindsight consolidation backlog exists | Run `memory_guardian.py --status` and inspect backlog trend |
| Acceptance fails on one query | Retrieval family policy regressed | Compare output from `tiered_context_injector.py --test` |
| `gbrain` commands fail | Archive layer unavailable | Re-run `gbrain doctor --fast` |
| Python import error | Sidecar scripts not deployed consistently | Re-copy the supported script set |
