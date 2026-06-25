# Compatibility Matrix

This project is designed to support multiple agent runtimes through a shared `AGENT_HOME` data directory model. Not every historical script is equally portable, so this matrix separates agent-agnostic surfaces from Hermes-specific legacy helpers.

## Agent-Agnostic

These are the primary supported surfaces for multi-agent use:

| Surface | Status | Notes |
|---|---|---|
| `session_to_gbrain.py` | Agent-Agnostic | Reads `AGENT_HOME/sessions` and `state.db` |
| `memory_governance_rebuild.py` | Agent-Agnostic | Supports configurable DB and KMM note paths |
| `tiered_context_injector.py` | Agent-Agnostic | Uses governance DB + `AGENT_HOME` data |
| `memory_guardian.py` | Agent-Agnostic | Monitors governance and Hindsight state |
| `memory_maintenance_cycle.py` | Agent-Agnostic | Orchestrates the supported runtime scripts |
| `sidecar_acceptance_check.py` | Agent-Agnostic | Validates layered recall behavior |
| `archive_sessions.py` | Agent-Agnostic | Archives sessions from `AGENT_HOME/state.db` |
| `auto_session_summary.py` | Agent-Agnostic | Summarizes sessions directly from shared SQLite state |
| `memory_observability_report.py` | Agent-Agnostic | Reads governance DB only |
| `hermes-memory` CLI | Agent-Agnostic | Operates on installed scripts in `AGENT_HOME/scripts` |

## Hermes-Only

These historical helpers still assume Hermes-private runtime pieces and should not be treated as portable sidecar APIs:

| Surface | Status | Why |
|---|---|---|
| `memory_reflect.py` | Hermes-Only | Imports Hermes-side runtime modules and assumes Hermes logging layout |
| `memory_lifecycle.py` | Hermes-Only | Uses historical Hermes-specific local DB layout and test scaffolding |
| `HERMES_ONBOARDING.md` | Hermes-Only | Onboarding guide for a Hermes deployment, not a generic sidecar install |
| `skills/memory-starter-kit/SKILL.md` | Hermes-Only historical | Still references removed or Hermes-specific layers such as `agentmemory` |

## Recommended Rule

For new integrations with Claude Code, Cursor, Codex, or other agents:

1. Use the Agent-Agnostic surfaces first.
2. Treat Hermes-Only items as references, not stable interfaces.
3. If a new capability cannot run from `AGENT_HOME` + shared SQLite/session files alone, document it before adding it to the supported install set.
