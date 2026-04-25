---
name: memory-archivist
description: Hermes 记忆体系自动化维护工具。定期归档会话、清理过期数据、备份与回滚。推荐安装。
---

# Memory Archivist

让你的记忆系统自动运转，无需手动维护。

---

## 它做什么

| 功能 | 说明 | 频率 |
|------|------|------|
| **对话归档** | 将会话历史导入 pool.db | 每日凌晨 |
| **索引更新** | 更新档案目录的 FTS5 索引 | 每周 |
| **数据清理** | 删除过期会话释放空间 | 每周 |
| **备份** | 自动备份到指定目录 | 每日 |

---

## 自动化配置

安装后自动创建以下 cronjob：

```bash
# 每日 04:00: 对话归档 + 备份
0 4 * * * cd ~/.hermes && python3 skills/memory-archivist/scripts/daily_archive.py

# 每周日 03:00: 索引更新 + 数据清理
0 3 * * 0 cd ~/.hermes && python3 skills/memory-archivist/scripts/weekly_cleanup.py
```

你可以修改时间窗口，或者禁用某些任务。

---

## 手动执行

### 立即归档

```bash
python3 ~/.hermes/skills/memory-archivist/scripts/daily_archive.py
```

### 立即清理

```bash
python3 ~/.hermes/skills/memory-archivist/scripts/weekly_cleanup.py \
    --keep-days 30 \
    --dry-run
```

### 立即备份

```bash
python3 ~/.hermes/skills/memory-archivist/scripts/backup.py \
    --dest /path/to/backup
```

---

## 存储策略

### 数据保留规则

| 数据类型 | 默认保留期 | 说明 |
|----------|-----------|------|
| 原始对话 | 30 天 | 完整的消息记录 |
| 对话摘要 | 90 天 | 压缩后的关键信息 |
| 会话元数据 | 永久 | 标题、时间、参与者 |
| 档案文件 | 永久 | 人工维护的长文档 |

### 磁盘管理

当磁盘使用超过 80% 时：
1. 自动删除 30 天以上的原始对话
2. 发送警告通知
3. 保留摘要和档案不动

---

## 常见问题

**Q: 会不会删除重要数据？**
A: 不会。删除规则非常保守，只删除原始消息，摘要永久保留。且每次清理前自动备份。

**Q: 可以在多台设备同步吗？**
A: 安装备份脚本可以配置远程目录，但实时同步需要额外配置（如 rsync 或云盘）。

**Q: 数据库损坏怎么办？**
A: 每日自动备份到 `~/.hermes/backups/` ，使用 `backup.py --restore` 恢复。

---

*版本：0.1.0 | 依赖：memory-starter-kit*
