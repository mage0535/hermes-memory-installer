---
name: memory-archivist
description: 自动归档 + 知识图谱同步 + 记忆生命周期管理
---

# Memory Archivist

进阶记忆层。实现自动化: 会话归档 → gbrain 知识图谱同步 → 记忆清理。

## 核心脚本

### 1. 会话归档 (`archive_sessions.py`)
从 state.db 提取完整对话 → 生成结构化摘要 → 写入 gbrain

```bash
python3 scripts/archive_sessions.py --session-id <id>
```

### 2. 自动摘要 (`auto_session_summary.py`)
分析对话关键决策/学习/变更 → 生成 session_summary.md

### 3. 知识图谱同步 (`session_to_gbrain.py`)
增量同步: Hermes state.db → gbrain pages, 含 timeline + tags + wikilinks

```bash
python3 scripts/session_to_gbrain.py --resume  # 断点续传
```

### 4. 记忆生命周期 (`memory_lifecycle.py`)
- 检测 stale 记忆 (>30天未访问)
- 标记 expired 记忆 (>90天)
- 自动清理, 保护已标注 `keep` 的记忆

### 5. 记忆守护 (`memory_guardian.py`)
11.7KB, 最全面的记忆管理:
- 容量检测 (memory tool 5KB cap)
- 冲突检测 (新旧信息矛盾)
- 智能压缩 (合并重复条目)
- 过期清理

### 6. 记忆反思 (`memory_reflect.py`)
周期性运行, 分析近期记忆趋势, 生成用户画像更新建议

## Cron 配置

```yaml
# 每日归档
schedule: "30 3 * * *"
script: $AGENT_HOME/scripts/archive_sessions.py

# 每周生命周期
schedule: "0 4 * * 0"
script: $AGENT_HOME/scripts/memory_lifecycle.py
```
