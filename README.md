<div align="center">

# 🧠 Hermes Memory Installer

**一键为 Hermes AI Agent 注入持久记忆**

[中文](#-项目介绍) | [English](#-about)

</div>

---

## 🇨🇳 项目介绍

### 为什么做这个项目？

AI 助理最常见的痛点——**聊着聊着就忘了**。昨天的项目细节、上个月的人物关系、上周的决策理由……每次重启对话都像重新认识一个陌生人。Hermes Agent 原生提供了 `memory` 工具和 `skill` 系统，但缺乏一个**开箱即用、结构化的长期记忆管理方案**。

本项目旨在为 Hermes 补充一套完整的记忆体管理体系：从档案模板、自动归档到上下文智能路由，让 AI 真正"记住"你。

### 参考与致谢

本项目在设计和实现过程中，参考并借鉴了以下优秀项目的具体部分：

| 项目 | 借鉴内容 | 致谢 |
|------|---------|------|
| **[mem0](https://github.com/mem0ai/mem0)** | 用户/会话/系统三层记忆分层架构 | 其分层抽象启发了我们的 Skill 三层设计（starter-kit / archivist / proactive） |
| **[LangChain Memory](https://python.langchain.com/docs/modules/memory/)** | `ConversationBufferMemory` + `VectorStoreRetrieverMemory` 的组合模式 | 启发了"延迟加载 + FTS5 全文检索"的混合检索策略 |
| **[Obsidian](https://obsidian.md/)** | 本地优先、纯文本 Markdown 档案哲学 | 所有档案均以 Markdown 格式存储，用户可直接用任意编辑器查看和修改 |
| **[SQLite FTS5](https://sqlite.org/fts5.html)** | 嵌入式全文检索引擎 | 零外部依赖，利用 Python 内置 SQLite 实现毫秒级档案检索 |
| **[Karpathy's llm wiki](https://github.com/karpathy/llm-wiki)** | 个人知识库的极简组织方式 | 档案目录结构（people / projects / knowledge）直接借鉴 |

**特别感谢** Hermes Agent 开发团队提供的原生 `memory` 和 `skill` 扩展机制，使本项目得以在不修改任何核心代码的前提下实现零侵入部署。

### 核心架构

```
┌─────────────────────────────────────────────────────────┐
│  对话层  │  用户输入 → Hermes Gateway → 生成回复                    │
│  ───────  │                                                        │
│  技能层  │  ▶ memory-starter-kit → 档案模板 + 存储规范              │
│           │  ▶ memory-archivist    → 定时归档 + 自动清理              │
│           │  ▶ memory-proactive    → 上下文路由 + 智能加载（可选）      │
│  ───────  │                                                        │
│  数据层  │  ~/.hermes/archives/     → Markdown 档案库                  │
│           │  ~/.hermes/pool.db       → SQLite + FTS5 索引                │
│           │  ~/.hermes/config.yaml   → 配置自动插入 Skill 路径        │
└─────────────────────────────────────────────────────────┘
```

### 原版 vs 增强版对比（基于 Hermes v0.11+）

| 能力维度 | 原版 Hermes | ⭐ 增强版（本项目） |
|---------|------------|------------------|
| **记忆存储** | 单一文本字符串，无结构 | 分类档案（人物/项目/知识）+ 模板化 Markdown |
| **记忆检索** | 完全依赖 LLM 上下文窗口 | **FTS5 全文检索** + 关键词匹配，毫秒级定位 |
| **自动化** | 无 | 定时归档、自动清理、备份回滚机制 |
| **上下文感知** | 仅当前对话 | 延迟分析上一轮对话，自动加载相关档案 |
| **可视化** | 不可直接查看 | Markdown 档案可用任意编辑器打开 |
| **扩展性** | 需修改核心代码 | **零侵入**，纯 Skill 扩展 |
| **安装难度** | 手动配置 | **30 秒一键安装** |

### 安装方式

#### 方式 A：一键脚本（推荐小白）

```bash
curl -fsSL https://raw.githubusercontent.com/mage0535/hermes-memory-installer/main/install.sh | bash
```

- 自动检测环境（Python >= 3.9、SQLite FTS5）
- 自动备份 `config.yaml`
- 自动创建目录 + 初始化数据库 + 安装 Skill
- 约 30 秒完成

#### 方式 B：手动安装（推荐老手）

详见 [MANUAL_INSTALL.md](MANUAL_INSTALL.md)

```bash
cd hermes-memory-installer
cp -r skills/memory-starter-kit ~/.hermes/skills/
cp -r skills/memory-archivist ~/.hermes/skills/
python3 scripts/init_db.py
# 手动编辑 config.yaml 添加 skills
```

- 完全可控，每步手动决策
- 适合有自定义配置的高级用户

### 原理与开发文档

📖 [详细设计与开发文档（中文）](docs/hermes-memory-system-design.md)  
📖 [Design & Development Documentation (English)](docs/hermes-memory-system-design-en.md)

---

## 🇺🇸 About

### Why This Project?

The #1 pain point of AI assistants — **they forget**. Yesterday's project details, last month's relationships, last week's decisions... every new session feels like meeting a stranger. Hermes Agent provides native `memory` and `skill` mechanisms, but lacks an **out-of-the-box, structured long-term memory solution**.

This project fills that gap with a complete memory management system: archival templates, automated archiving, and intelligent context routing — so your AI truly *remembers* you.

### Credits & Inspirations

| Project | What We Borrowed | Thanks For |
|---------|-----------------|------------|
| **[mem0](https://github.com/mem0ai/mem0)** | User / session / system memory layering | Inspired our 3-tier Skill design (starter-kit / archivist / proactive) |
| **[LangChain Memory](https://python.langchain.com/docs/modules/memory/)** | `ConversationBufferMemory` + `VectorStoreRetrieverMemory` hybrid | Inspired our "lazy loading + FTS5 full-text search" retrieval strategy |
| **[Obsidian](https://obsidian.md/)** | Local-first, plain-text Markdown philosophy | All archives are Markdown — viewable in any editor |
| **[SQLite FTS5](https://sqlite.org/fts5.html)** | Embedded full-text search engine | Zero external deps, millisecond-level archive retrieval |
| **[Karpathy's llm wiki](https://github.com/karpathy/llm-wiki)** | Minimalist knowledge base organization | Archive directory structure (people / projects / knowledge) |

**Special thanks** to the Hermes Agent team for the native `memory` and `skill` extension APIs, enabling this project to deploy with **zero core code modification**.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Dialog    │  User Input → Hermes Gateway → AI Response              │
│  Layer     │                                                        │
│  ───────  │                                                        │
│  Skill     │  ▶ memory-starter-kit → Templates + Storage Standards   │
│  Layer     │  ▶ memory-archivist    → Auto-archive + Cleanup         │
│           │  ▶ memory-proactive    → Context Routing (optional)     │
│  ───────  │                                                        │
│  Data      │  ~/.hermes/archives/     → Markdown Archive Library     │
│  Layer     │  ~/.hermes/pool.db       → SQLite + FTS5 Index          │
│           │  ~/.hermes/config.yaml   → Auto-inserted Skill Paths    │
└─────────────────────────────────────────────────────────┘
```

### Original vs Enhanced (Hermes v0.11+)

| Dimension | Original Hermes | ⭐ Enhanced (This Project) |
|-----------|----------------|---------------------------|
| **Storage** | Single text blob, no structure | Categorized archives (people/projects/knowledge) + Templated Markdown |
| **Retrieval** | Relies entirely on LLM context window | **FTS5 full-text search** + keyword matching, millisecond accuracy |
| **Automation** | None | Scheduled archiving, auto-cleanup, backup rollback |
| **Context Awareness** | Current session only | Delayed analysis of prior conversation, auto-load relevant archives |
| **Observability** | Not directly viewable | Markdown archives editable in any editor |
| **Extensibility** | Requires core code changes | **Zero intrusion**, pure Skill extension |
| **Install Time** | Manual configuration | **30-second one-click install** |

### Installation

#### Method A: One-liner (Beginner-friendly)

```bash
curl -fsSL https://raw.githubusercontent.com/mage0535/hermes-memory-installer/main/install.sh | bash
```

- Auto-detects environment (Python >= 3.9, SQLite FTS5)
- Auto-backs up `config.yaml`
- Auto-creates dirs + init DB + install Skills
- ~30 seconds total

#### Method B: Manual Install (Advanced users)

See [MANUAL_INSTALL.md](MANUAL_INSTALL.md)

```bash
cd hermes-memory-installer
cp -r skills/memory-starter-kit ~/.hermes/skills/
cp -r skills/memory-archivist ~/.hermes/skills/
python3 scripts/init_db.py
# Manually edit config.yaml to add skills
```

- Full control, step-by-step decisions
- Best for users with custom configurations

### Documentation

📖 [Detailed Design & Development Docs (Chinese)](docs/hermes-memory-system-design.md)  
📖 [Design & Development Documentation (English)](docs/hermes-memory-system-design-en.md)

---

## 📦 Releases

| Version | Package | Description | Download |
|---------|---------|-------------|----------|
| **v0.1.0** | `hermes-memory-installer-v0.1.0-oneclick.sh` | 一键安装脚本 / One-click installer | [Download](https://github.com/mage0535/hermes-memory-installer/releases/download/v0.1.0/hermes-memory-installer-v0.1.0-oneclick.sh) |
| **v0.1.0** | `hermes-memory-installer-v0.1.0-manual.zip` | 手动安装套件 / Manual install bundle | [Download](https://github.com/mage0535/hermes-memory-installer/releases/download/v0.1.0/hermes-memory-installer-v0.1.0-manual.zip) |

> 发布页: https://github.com/mage0535/hermes-memory-installer/releases

---

## License

MIT
