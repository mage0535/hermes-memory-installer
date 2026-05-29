<div align="center">

# Memory Sidecar Installer v3.0

**一个面向任意 AI 智能体的生产级外挂记忆体 sidecar。**

[**English**](README.md) | [**中文文档**](README_CN.md)

</div>

---

## v3.0 是什么

Memory Sidecar v3.0 不是改智能体核心代码，而是一个**外挂 sidecar 记忆系统**。  
它运行在智能体旁边，负责：

- 持久保存会话相关记忆
- 将高价值会话归档到 gbrain
- 生成 canonical memory object 与治理索引
- 为重要人物 / 项目 / 主题建立 dossier（重点档案）
- 为智能体提供分层召回参考
- 监控健康状态、执行验收和处理 sticky backlog

当前兼容任意 AI 智能体（Hermes、Claude Code、Cursor、Codex 等），只需配置环境变量即可挂载。

当前这个仓库已经按**服务器最终运行版**整理，而不是旧草稿。

## 它解决什么问题

Hermes 的对话循环很强，但只靠 prompt 内热记忆，不足以支撑长期项目、复杂关系和跨周任务。

v3.0 增加了：

- **长期保留**：跨会话、跨重启、跨周保存记忆
- **分层组织**：用 hub、object、dossier 和 archive page 管理记忆
- **分层召回**：不是乱搜，而是按 query family 融合多层证据
- **运维安全**：外挂系统可观测、可回归、可独立修复

## 最终 v3.0 架构

```text
Hermes Core
  └─ 写入 state.db + session JSON

Sidecar Capture Layer
  └─ session_to_gbrain.py

Sidecar Governance Layer
  ├─ memory_family_registry.py
  ├─ memory_governance_rebuild.py
  └─ memory_guardian.py

Sidecar Recall Layer
  └─ tiered_context_injector.py

Sidecar Maintenance + Acceptance
  ├─ memory_maintenance_cycle.py
  └─ sidecar_acceptance_check.py
```

技术细节见 [ARCHITECTURE_CN.md](ARCHITECTURE_CN.md)。

## 快速开始

### 安装

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
python3 installer/install.py
```

非交互方式并显式指定 Embedding Model：

```bash
python3 installer/install.py --noninteractive --embedding intfloat/multilingual-e5-small
```

安装器会把最终支持的 sidecar 脚本部署到 `~/.hermes/scripts/`（默认），修补 `~/.hermes/config.yaml`，并把安装元数据写入 `~/.hermes/memory-sidecar/install-profile.json`。

### 挂载到不同智能体

本 sidecar 支持任意智能体，通过以下环境变量切换：

```bash
# 必选：智能体数据目录（默认 ~/.hermes，向后兼容 HERMES_HOME）
export AGENT_HOME=/home/user/.my-agent

# 可选：Hindsight bank 名称（默认 hermes）
export HINDSIGHT_BANK=my-agent

# 可选：Hindsight 服务地址（默认 http://127.0.0.1:8890）
export HINDSIGHT_BASE_URL=http://127.0.0.1:8890
```

非交互安装到指定智能体：

```bash
python3 installer/install.py --noninteractive --agent-home ~/.my-agent --embedding intfloat/multilingual-e5-small
```

兼容旧版 `--hermes-home` 参数和 `HERMES_HOME` 环境变量。

### 运行一次维护周期

```bash
~/.hermes/scripts/memory_maintenance_cycle.py
```

### 运行验收检查

```bash
~/.hermes/scripts/sidecar_acceptance_check.py
```

## v3.0 实际安装的脚本

当前生产版 sidecar 只支持下面这组脚本：

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

这就是服务器上已验证通过的最终运行集。

## 这个外挂记忆体如何工作

### 1. 会话采集

Hermes 继续正常写入 `state.db` 和 session JSON。  
sidecar 通过 checkpoint 增量读取这些数据。

### 2. 长期归档

`session_to_gbrain.py` 把高价值会话写成 gbrain page，并补充：

- tags
- timeline entry
- topic hub 链接

### 3. 治理重建

`memory_governance_rebuild.py` 会重建：

- session index
- hindsight index
- memory hubs
- canonical memory objects（含 valid_from / valid_to 时效治理字段）
- dossier 元数据
- recall metrics

同时还维护内存治理的修复基础设施：
- `orphan_messages` — 孤儿消息审计
- `session_repair_map` — 消息→session 修复映射
- `session_lineage_repair` — 会话父链修复
- `recovered_fragments` — 无法归属的记忆碎片归档
- `memory_aliases` / `memory_relations` — 内存别名与关系图
- `sessions_effective` view — 修复后的会话视图

### 4. 分层召回

`tiered_context_injector.py` 会先判断 query family，再融合：

- hub summary
- canonical object
- hindsight cache
- live hindsight（当策略需要时）
- 必要时才允许弱 fallback 层进入

### 5. 健康与修复

`memory_guardian.py` 会暴露：

- capacity / usage
- duplicate count
- sync lag
- consolidation backlog 趋势
- stuck operation 检测
- backlog 排空与安全重启保护

## Focused Dossier（重点档案）

v3.0 引入了 **Focused Dossier** 概念。

它把某个重要的人、关系、项目、事件或主题提升成一级记忆对象。  
当前生产版已经验证了一个 relationship dossier（`kiki`），后续可以通过共享 registry 扩展到更多重点对象。

## Embedding Model Selection

Embedding Model 会直接影响：

- 语义召回质量
- 中英混合检索质量
- dossier 聚类质量
- 长期 archive 检索质量
- CPU / RAM / 磁盘占用

### 安装时如何选择

安装器支持三种方式：

- 交互选择
- `--embedding <model-id>` 显式指定
- `--noninteractive` 使用默认推荐模型

### 当前支持的模型

| 模型 | 语言 | 体积 | 适合场景 |
|---|---|---:|---|
| `intfloat/multilingual-e5-small` | 100+ 语言 | ~470MB | 默认推荐，适合中英混合 Hermes 部署 |
| `BAAI/bge-small-zh-v1.5` | 中文优先 | ~96MB | 资源极紧、中文为主 |
| `paraphrase-multilingual-MiniLM-L12-v2` | 50+ 语言 | ~471MB | 生态成熟的 multilingual sentence-transformers |
| `Alibaba-NLP/gte-multilingual-base` | 75+ 语言 | ~610MB | 更高多语言召回质量 |
| `sentence-transformers/LaBSE` | 109 语言 | ~471MB | 强跨语种对齐场景 |
| `BAAI/bge-m3` | 100+ 语言 | ~2GB | 硬件充裕时追求最高精度 |

### 默认推荐模型

默认推荐：

```text
intfloat/multilingual-e5-small
```

原因：

- 多语言覆盖广
- 适合中文 + 英文混合工作流
- 资源占用适中
- 对当前 v3.0 sidecar 的生产场景足够稳

如果部署环境是纯中文且机器较弱，可以考虑 `BAAI/bge-small-zh-v1.5`。

## Choosing Your Retrieval Engine

在最终的 v3.0 设计里，“Retrieval Engine” 不再等于“换一个数据库”。  
它真正指的是 **sidecar 采用什么检索剖面来组织多层证据**。

### 当前受支持的生产剖面：Hybrid Sidecar

本仓库当前只维护一个正式部署剖面：

- **Hybrid Sidecar**（推荐）

它组合了：

- Hermes 自带的 `state.db` / session 历史
- Hindsight 的实时语义记忆
- governance object 的 canonical 长期记忆
- gbrain 的 archive page 与 topic hub

这就是服务器上已经验证通过的生产模式。

### 实际检索时各层怎么分工

| 需求 | 常见主导层 |
|---|---|
| 当前 system / provider 状态 | governance object + system hub |
| 关系类记忆 | dossier hub + live hindsight + hindsight cache |
| 项目交付记忆 | canonical project object + hindsight cache |
| 探索型问题 | 更宽的 governance/object 证据，有限 fallback |
| 冷归档追溯 | gbrain session page + topic hub |

### 为什么 v3.0 不再宣传“任意引擎自由切换”

早期草稿曾把项目写成好像可以任意切换 PostgreSQL / Elasticsearch / SQLite / 其他引擎。  
但那并不是最终的生产现实。

最终稳定下来的版本是：

- **sidecar-first**
- **Hermes-compatible**
- **Hindsight-backed**
- **gbrain-archived**
- **governance-indexed**

这个收窄后的定义，反而让项目更干净、更可重部署。

## 运行流程

```text
智能体写入新会话
  -> session_to_gbrain.py 处理归档候选
  -> memory_governance_rebuild.py 重建 object / hub / metrics
  -> memory_guardian.py 检查 backlog 和健康状态
  -> tiered_context_injector.py 生成分层记忆上下文
  -> 智能体在需要时消费这些上下文
```

## 验证流程

建议的生产变更流程：

1. 本地开发
2. 本地编译
3. 备份服务器脚本
4. 部署到 `~/.hermes/scripts/`
5. 运行 `memory_maintenance_cycle.py`
6. 运行 `sidecar_acceptance_check.py`
7. 确认关键业务回归 query 仍然正常

## 当前运行状态说明

当前生产环境中，有一个刻意保留可观测性的运维信号：

- Hindsight consolidation backlog 可能处于 **flat / controlled** 状态
- sidecar 已经提供 stuck 检测、排空逻辑和安全重启保护
- 这个信号是显式暴露的，不会被静默隐藏

也就是说，v3.0 更强调“看见真实状态并可控处理”，而不是假装系统永远没有积压。

## 仓库结构

```text
installer/   安装入口与 config patch 辅助
scripts/     最终 sidecar 运行脚本
skills/      Hermes 端记忆技能
templates/   模板
tests/       仓库导入与 smoke 校验
```

## 致谢

### 核心参考项目与生态

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
- [sentence-transformers](https://www.sbert.net/)
- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [sentence-transformers/LaBSE](https://huggingface.co/sentence-transformers/LaBSE)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
- [PostgreSQL](https://www.postgresql.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [SQLite](https://www.sqlite.org/)

### 社区反馈致谢

感谢通过以下渠道持续提出问题、反馈召回缺陷、推动架构演进的用户：

- GitHub Issues
- GitHub Discussions
- Reddit
- V2EX 与其他社区论坛
- 直接在 Hermes 生产使用中反馈问题的用户

这些反馈直接推动了最终 v3.0 sidecar 的形成。
