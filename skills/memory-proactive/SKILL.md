---
name: memory-proactive
description: "上下文路由、主题检测、语义召回注入 — 让 AI 主动回忆"
tags: [memory, proactive, context, routing, semantic]
---

# Memory Proactive

## Overview

The **memory-proactive** skill enables Hermes to actively recall relevant context:

1. **Topic Detection**: Analyzes current conversation for key topics
2. **Semantic Recall**: Searches embeddings for related past conversations
3. **Context Injection**: Injects relevant memory into the conversation flow

## How It Works

### Dual-Path Search
```
User message
  -> Layer 1: FTS5 (state.db, ms-level, precise keyword)
  -> Layer 2: Semantic (embeddings, agent-local first)
  -> Layer 3: gbrain (knowledge graph, fallback)
```

### Recall Pipeline
1. Clean user query (strip system markers)
2. Search local agent memory (source:user_id filtered)
3. Fall back to cross-platform global search if < 2 results
4. Apply time decay (adjusted_score = sim * exp(-age_days / 30))

## Configuration

Add to config.yaml:
```yaml
skills:
  - memory-proactive
```

The skill auto-triggers on recall keywords:
- Chinese: "还记得", "之前", "上次", "记得吗"
- English: "remember", "earlier", "before", "last time"

## Performance Notes

- Layer 1: < 10ms (FTS5 index)
- Layer 2: ~50-200ms (embedding search)
- Layer 3: ~500ms-3s (gbrain vector + graph, optional)

All layers are best-effort and non-blocking.
