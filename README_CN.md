<div align="center">

# 🧠 Hermes Memory Installer 2.2.0

**为 Hermes AI Agent 注入持久记忆 — 由 gbrain 知识图谱驱动**

[English](README.md) | [中文版](#)

![Version](https://img.shields.io/badge/version-2.2.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)

一键安装脚本，为 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 注入持久化长期记忆能力。

</div>

## ✨ 主要特性

- **三层上下文检索**: L1 最近会话 → L2 FTS5 全文检索 × 30天半衰期 → L3 gbrain 知识图谱，RRF 融合排序
- **记忆体生命周期**: 自动检测 stale(90d)/archived(180d) 页面，保护关键页面免于降级
- **领域隔离**: 5 领域配额管理（kiki/astock/promo/system/misc），防止单一领域撑爆总量
- **记忆体容量守卫**: 写入前检查容量 + 矛盾检测 + 自动 compaction 预警
- **会话→知识图谱**: 自动将 Hermes 会话摘要摄入 gbrain，生成带 tag/timeline 的知识页面
- **反馈驱动排名**: `fb:helpful/misleading/outdated` 标签影响上下文检索得分
- **零第三方依赖**: 全部脚本仅使用 Python 标准库

## 🚀 快速安装

```bash
# 方法 1：一键脚本
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
bash install.sh

# 方法 2：Python 安装器
python3 installer/install.py
```

## 📦 包含组件

### Runtime 脚本 (安装在 ~/.hermes/scripts/)

| 脚本 | 行数 | 用途 |
|---|---|---|
| `tiered_context_injector.py` | 384 | 三层上下文检索 + RRF 融合排序 |
| `session_to_gbrain.py` | 476 | 会话摘要→gbrain 知识图谱 |
| `memory_lifecycle.py` | 118 | 生命周期管理 + 保护配置 |
| `domain_memory.py` | 144 | 领域隔离与配额管理 |
| `memory_guard.py` | 76 | 写入前容量检查 |
| `memory_prewrite_guard.py` | 58 | 写入前验证 + 矛盾检测 |
| `compact_memory.py` | 128 | 记忆体压缩与清理 |
| — | — | — |
| *原 v2.1.1 已有脚本* | ~4,200 | 归档引擎、gbrain 搜索、嵌入同步等 |

### Skills (安装在 ~/.hermes/skills/)

- `memory-starter-kit` — 快速上手模板
- `memory-archivist` — 高级归档管理
- `memory-proactive` — 主动记忆召回

## 📖 版本历史

### v2.2.0 (2026-05-13)

**新增 7 个 Runtime 脚本 (1,393 行，全部零依赖):**

- `tiered_context_injector.py` — 三层上下文注入器 v3，RRF 融合排序，反馈标签调分
- `session_to_gbrain.py` — 自动将 Hermes 会话摘要摄入 gbrain 知识图谱（增量 checkpoint）
- `memory_lifecycle.py` — 页面生命周期状态机，保护配置外移至 YAML 文件
- `domain_memory.py` — 5 领域隔离与配额管理（kiki/astock/promo/system/misc）
- `memory_guard.py` — 写入前容量检查，<20% 触发 compaction 预警
- `memory_prewrite_guard.py` — 写入前验证 + 矛盾检测 + 结构化 JSON 输出
- `compact_memory.py` — 记忆体压缩 v2，过期模式匹配，支持 --analyze/--apply

**修改 4 个文件:**

- `install.sh` — 版本 2.1.1→2.2.0，`/tmp/memory-repo` 硬编码路径修复为相对路径
- `installer/install.py` — 版本标注更新
- `README.md` / `README_CN.md` — 本文档
- `tests/test_smoke.py` — 路径修复 + 新增脚本覆盖

**数据安全重构:**

- `memory_lifecycle.py`: 剥离内嵌的 `PROTECTED_SLUGS/TAGS`（内部页面名）→ 外部 YAML 配置
- 新增 `config/memory_lifecycle.example.yaml` 占位配置示例

### v2.1.1 (2026-05-09)

- 默认嵌入模型切换为 `intfloat/multilingual-e5-small`
- 模型选择器增加 AI 助手自动安装支持
- 跨平台路径支持

### v2.1.0 (2026-05-08)

- 多语言语义搜索
- 新增脚本：嵌入引擎、自动摘要、gbrain 维护
- 跨平台 Windows/macOS/Linux 路径支持

### v2.0.0 (2026-05-06)

- gbrain 知识图谱集成
- 双路径搜索（gbrain + 本地 FTS5）
- 自动摘要与 curator 自我进化

## 🏗 架构

```
Hermes Agent ←→ Memory Pipeline
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    tiered_context   lifecycle   domain_memory
    (RRF fusion)    (state machine) (quota mgmt)
          │            │            │
          └────────────┼────────────┘
                       ▼
                 gbrain + SQLite
                 (knowledge graph + FTS5)
```

### 数据流

1. **写入路径**: agent memory() 调用 → `memory_guard`(容量检查) → `memory_prewrite_guard`(矛盾检测) → `domain_memory`(领域路由) → 写入
2. **读取路径**: agent 会话启动 → `tiered_context_injector`(L1+L2+L3) → RRF 融合排序 → 注入 agent 上下文
3. **维护路径**: cron 每日 02:00 → `memory_lifecycle`(状态检查) → `session_to_gbrain`(增量同步) → 一致性校验(周一) → TTL 降级(15日)

## 🛠 增量同步架构

`session_to_gbrain.py` 使用 checkpoint 文件追踪已处理的会话：

```
~/.hermes/scripts/
├── session_to_gbrain.py    # 主管道
├── .gbrain_session_cursor  # 增量 checkpoint (自动创建)
└── ...
```

- 首次运行：处理所有历史会话摘要
- 后续运行：仅处理新产生的会话
- 设计为每 6 小时 cron 调用一次（可在 `install.sh` 中选择）

## 🤝 致谢

- **[@mattamundson](https://github.com/mattamundson)** — [ralph-orchestrator](https://github.com/mattamundson/ralph-orchestrator) 和 ai-agent-memory-patterns 中的配置外部化与内存隔离模式，启发了 memory_lifecycle 的保护数据外移方案（硬编码 slug/tag → YAML 配置加载）。
- **RRF 融合算法** — 基于信息检索领域标准 Reciprocal Rank Fusion 公式 (k=60)
- **[gbrain](https://github.com/garrytan/gbrain)** — 由 garrytan/gbrain 项目提供 `put_page` / `add_timeline_entry` / `query` MCP 接口
- **@domain 前缀协议** — v1 阶段用户定义的命名约定
- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — 上游 `memory()` 工具提供了写入/读取基础能力

其余所有代码均为全自主开发。

## 📄 License

MIT
