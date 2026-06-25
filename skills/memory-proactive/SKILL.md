---
name: memory-proactive
description: Proactive layered recall and generic domain-aware routing.
---

# Memory Proactive

This skill describes the current proactive recall surfaces that remain useful in
the local repository.

## Layered Context Injection

Primary engine: `tiered_context_injector.py`

It combines multiple recall paths before the next interaction:

- recent session recall from shared SQLite state
- governance-backed object and hub recall
- knowledge note recall
- optional live Hindsight recall when the query profile needs it

Example:

```bash
python3 scripts/tiered_context_injector.py --query "user preferences"
```

Useful knobs:

- `--min-score 0.3`
- `--max-results 10`
- `--recall "project status" "system config"`
- `--domains project,stock`

## Generic Domain Routing

Helper: `domain_memory.py`

This is a lightweight legacy helper for splitting local memory into generic
domains so one topic does not crowd out everything else.

Example domains:

- `project`
- `stock`
- `system`
- `marketing`
- `relationship`
- `general`

Example:

```bash
python3 scripts/domain_memory.py check project "Milestone planning note"
python3 scripts/domain_memory.py status
```

## Guidance

- use generic domains, not user- or project-specific hardcoded labels
- keep recall queries portable across agent runtimes
- treat this skill as an optional helper layer, not a required production
  contract
