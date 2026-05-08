<div align="center">

# 🧠 Hermes Memory Installer 2.1

**为 Hermes AI Agent 注入持久记忆 — 由 gbrain 知识图谱驱动**

[English](README.md) | [中文](#)

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)

</div>

---

## 🇨🇳 项目介绍

### 为什么升级到 2.0？

AI 助理最常见的痛点——**聊着聊着就忘了**。Hermes Agent 原生提供了 `memory` 工具和 `skill` 系统，但欠缺开箱即用的长期记忆管理方案。

**记忆体1.0** 用 SQLite FTS5 + Markdown 档案 + 3 个 Skill 解决了基础问题。

**记忆体2.0** 在此基础上引入了 **gbrain 知识图谱引擎**、**双路语义搜索**、**自动摘要流水线**、**知识图谱自进化机制**和**跨平台召回**。

### 核心架构

```
╔══════════════════════════════════════════════════╗
║              记忆体2.0 三层架构                    ║
╠══════════════════════════════════════════════════╣
║  对话层     │ 用户 ↔ Hermes Gateway ↔ AI         ║
║  ─────────────────────────────────────────────── ║
║  技能层     │ memory-starter-kit  [必装]          ║
║             │ memory-archivist    [推荐]          ║
║             │ memory-proactive    [可选]          ║
║             │ curator             [自进化]        ║
║  ─────────────────────────────────────────────── ║
║  数据层     │ state.db (FTS5)    — 实时存储        ║
║             │ pool.db  (FTS5)    — 档案索引        ║
║             │ archives/ (Markdown) — 文件系统       ║
║             │ gbrain (pgvector)  — 知识图谱        ║
╚══════════════════════════════════════════════════╝
```

### 原版 vs 1.0 vs 2.0 对比

| 维度 | 原版 Hermes | 记忆体1.0 | ⭐ 记忆体2.0 |
|------|------------|----------|------------|
| **存储** | 单一文本 | Markdown + SQLite FTS5 | Markdown + SQLite FTS5 + **gbrain 知识图谱** |
| **检索** | LLM 上下文窗口 | FTS5 全文搜索 | **FTS5 + 向量相似度 + 图遍历** 三路检索 |
| **自动化** | 无 | 定时 cron | Cron + **自动摘要 + 知识图谱 + 自进化** |
| **上下文** | 仅当前会话 | 延迟加载档案 | **双层语义召回 + 跨平台 + 知识图谱** |
| **可观测性** | 不可查看 | Markdown 编辑器 | Markdown + **gbrain 仪表盘 + 健康指标** |
| **扩展性** | 改核心代码 | Skill + 模板 | Skill + MCP 工具 + **gbrain API + 插件** |
| **安装** | 手动配置 | 30秒一键 | 30秒一键 + **可选 gbrain 配置** |
| **资源占用** | 极小 | ~50MB + SQLite | ~200MB + SQLite + 可选 Bun/gbrain |

## v2.1.0 更新日志

### 🔤 A. 多语言检索引擎

嵌入模型从仅支持英文的 `all-MiniLM-L6-v2`（384维）升级为 **BAAI/bge-small-zh-v1.5**（512维，33MB）。单一模型原生支持**中文和英文**检索，无需双模型切换。

- 新增：`scripts/embedding_server.py` — OpenAI 兼容的嵌入服务器（端口 8766）
- 更新：`scripts/sync_embeddings.py` — 默认使用 BAAI/bge-small-zh-v1.5
- 更新：`scripts/gbrain_init.sh` — `--embed` 参数自动部署嵌入服务器

### 🛠️ B. 生产级脚本补齐

| 脚本 | 功能 |
|------|------|
| `scripts/daily_archive.py` | 每日会话归档 + 数据库备份 |
| `scripts/weekly_cleanup.py` | 每周 FTS5 索引重建 + 过期数据清理 + 孤立页面检测 |
| `scripts/backup.py` | 完整备份/恢复，支持 `backup`/`restore`/`list` 子命令 |
| `scripts/test_router.py` | 验证 FTS5 → 嵌入 → gbrain 全链路召回 |
| `bin/hermes-memory` | CLI 工具，支持 `new`/`doctor`/`init` 命令 |

### 🏠 C. 跨平台路径支持

修复了硬编码 `/root/.hermes` 导致非 root 用户（如 `/home/keko/.hermes`）安装失败的问题。

- 所有脚本改用 `$HOME` / `Path.home()`（零硬编码路径）
- `install.sh` 新增 `detect_hermes_home()` 预检测函数
- 安装时自动检测并调整路径
- 非 root 用户无缝安装

### 📦 从 v2.0.0 升级

```bash
cd /tmp && git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer && git checkout v2.1.0
# 复制新脚本
cp scripts/daily_archive.py scripts/weekly_cleanup.py scripts/backup.py ~/.hermes/scripts/
cp scripts/test_router.py scripts/embedding_server.py ~/.hermes/scripts/
cp bin/hermes-memory ~/.local/bin/
# 安装嵌入服务器
python3 ~/.hermes/scripts/embedding_server.py &
```

### gbrain 知识图谱引擎（v2.0 核心）

记忆体2.0 引入 **gbrain**（Postgres 原生知识图谱）作为第三层检索引擎：

- **存储**: PGLite（零配置，默认）或 PostgreSQL 16+ + pgvector
- **检索**: 关键词 (tsvector) + 向量语义 (pgvector) + 图遍历（三路混合）
- **接入**: 通过 Hermes MCP 协议，Gateway 自动启动 gbrain sidecar
- **自动化**: 每日自动归档会话到 gbrain 页面 + 时间线条目

```
用户查询 -> FTS5 全文检索 (state.db, 毫秒级)
        -> 语义向量检索 (embeddings, ~200ms)
        -> gbrain 知识图谱 (向量+关键词+图, 兜底)
```

### 组件对比

| 维度 | 记忆体1.0 | 记忆体2.0 |
|------|----------|------------|
| **检索路径** | FTS5 单路 | FTS5 + 向量 + 图 三路 |
| **知识引擎** | 无 | gbrain (PGLite/Postgres + pgvector) |
| **会话归档** | 仅本地文件 | 自动写入 gbrain 页面 + 时间线 |
| **维护** | 手动 | gbrain_maintain.sh 每日自动 |
| **搜索** | 本地 FTS5 | gbrain query 混合搜索 |
| **可观测性** | 文件目录 | gbrain doctor + dashboard |



### 安装方式

#### 方式 A：一键脚本（推荐小白）

```bash
curl -fsSL https://raw.githubusercontent.com/mage0535/hermes-memory-installer/main/install.sh | bash
```

#### 方式 B：手动安装（推荐老手）

详见 [MANUAL_INSTALL.md](MANUAL_INSTALL.md)

### 参考与致谢

| 项目 | 借鉴内容 |
|------|---------|
| **[mem0](https://github.com/mem0ai/mem0)** | 记忆分层架构 |
| **[LangChain Memory](https://python.langchain.com/docs/modules/memory/)** | 混合检索策略 |
| **[Obsidian](https://obsidian.md/)** | 本地优先 Markdown 哲学 |
| **[SQLite FTS5](https://sqlite.org/fts5.html)** | 嵌入式全文检索引擎 |
| **[Karpathy's llm-wiki](https://github.com/karpathy/llm-wiki)** | 知识库组织方式 |
| **[gbrain](https://github.com/garrytan/gbrain)** | 知识图谱引擎（2.0 新增） |

**特别感谢** Hermes Agent 团队提供的原生扩展 API。

### 版本历史

| 版本 | 日期 | 亮点 |
|------|------|------|
| v2.1.0 | 2026-05 | 🔤 BAAI/bge-small-zh-v1.5 多语言检索引擎，🛠️ 5个生产级脚本，🏠 跨平台路径自动检测 |
| v2.0.0 | 2026-05 | gbrain 集成、双路搜索、自动摘要、策展人、自进化 |
| v1.0.0 | 2026-04 | FTS5 检索、3 个 Skill、一键安装、Markdown 档案 |


### 许可证

MIT
