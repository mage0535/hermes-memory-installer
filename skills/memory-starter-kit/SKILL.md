---
name: memory-starter-kit
description: "记忆体2.0 入门套件 — 档案模板、目录结构、使用指南"
tags: [memory, archive, template, starter]
---

# Memory Starter Kit

## What is this?

The **memory-starter-kit** is your entry point to the Memory 2.0 system. It provides:

- Archive directory structure and conventions
- Ready-to-use templates for People, Projects, and Knowledge
- Writing guidelines and best practices

## Directory Structure

Archives live in `~/.hermes/archives/`:

```
archives/
├── people/       # Person profiles
├── projects/     # Project documentation
├── knowledge/    # General knowledge base
└── _index/       # Index metadata (auto-managed)
```

## Getting Started

1. Create your first person archive:
```bash
cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \
   ~/.hermes/archives/people/name/profile.md
```

2. Open in any editor and fill in the fields

3. For automation, ensure memory-archivist skill is also installed

## Templates

- `person.md.j2` — People profiles with background, relationship, timeline
- `project.md.j2` — Project documentation with milestones, decisions
- `knowledge.md.j2` — Knowledge base entries with references

## See Also

- `memory-archivist` — Auto-archive and FTS5 indexing
- `memory-proactive` — Context routing and semantic recall
