---
name: memory-starter-kit
description: Historical starter note for the memory sidecar stack.
---

# Memory Starter Kit

Hermes-only historical note: this skill is kept for repository continuity, not
as a current portable install contract.

## Current Status

The old four-layer description is obsolete. The maintained local/public build is
the three-layer sidecar documented in:

- `README.md`
- `ARCHITECTURE.md`
- `docs/compatibility-matrix.md`

## Use This Skill For

- understanding the historical evolution of the project
- mapping old Hermes deployments to the current sidecar surfaces
- identifying which older helpers are no longer part of the default install set

## Do Not Use This Skill As

- a production installation guide
- a multi-agent compatibility contract
- a source of current runtime dependencies

## Current Portable Runtime

Use the installed scripts under `$AGENT_HOME/scripts/` together with:

- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `tiered_context_injector.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `sidecar_acceptance_check.py`

## Historical Notes

- older Hermes deployments used additional local helpers not shipped by the
  current installer
- legacy bridge layers mentioned in earlier versions were removed from the
  maintained public stack
- if a teammate is working from old notes, reconcile them against
  `docs/compatibility-matrix.md` before changing runtime behavior
