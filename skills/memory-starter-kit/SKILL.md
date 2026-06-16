---
name: memory-starter-kit
description: 基础记忆层 — Hot/Warm 双层自动记忆, 让 AI 真正记住你
---

# Memory Starter Kit

Hermes 记忆体系的基础层。让 AI 跨越会话记住你的身份、偏好和项目背景。

## 架构: 四层记忆体

```
L0 Hot  (memory tool, 5KB cap)     → 用户画像 + 系统笔记, 每轮自动注入
L1 Warm (Hindsight, PostgreSQL)     → auto-retain + auto-recall + 每周反思
L2 Hot-Warm bridge (agentmemory)    → 51 MCP 工具, 语义+关键词+图检索
L3 Cold (gbrain)                    → 知识图谱, 长期档案, pgvector 向量
```

## 安装

一键安装脚本会完成:
1. 安装 Python 依赖 (hindsight, agentmemory SDK)
2. 初始化 Hindsight PostgreSQL (PG16)
3. 启动 agentmemory Docker 容器
4. 配置 config.yaml (`memory.provider: hindsight`)
5. 部署所有 runtime 脚本到 `~/.hermes/scripts/`

## 验证

```bash
systemctl is-active hindsight           # 应返回 active
docker ps | grep agentmemory            # 应显示 running
python3 ~/.hermes/scripts/memory_guard.py  # 检查内存健康
```

## 日常运作

- **自动**: 每轮 Hindsight auto-retain 存储关键信息, auto-recall 检索上下文
- **手动**: `hindsight recall "关键词"` 或通过 agentmemory MCP 工具
- **周常**: 每周日 5:30 Hindsight Reflect 自动生成用户画像更新

## 文件结构

```
~/.hermes/
├── scripts/          # runtime 脚本
│   ├── hindsight-service.py
│   ├── memory_guard.py
│   ├── memory_prewrite_guard.py
│   └── ...
├── archives/         # 档案目录
│   ├── people/
│   ├── projects/
│   └── knowledge/
└── config.yaml       # memory.provider: hindsight
```

## 常见问题

| 问题 | 解决 |
|------|------|
| memory 满了 | `python3 ~/.hermes/scripts/compact_memory.py` |
| hindsight 不启动 | 检查 PG16 连接: `PGPASSWORD=xxx psql -h localhost -U gbrain -d hindsight` |
| agentmemory 断连 | `docker restart agentmemory-iii-engine-1` |
