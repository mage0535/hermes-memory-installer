<div align="center">

# Memory Sidecar Installer v3.0

**一个面向任意 AI 智能体的生产级外挂记忆体 sidecar。**

[**English**](README.md) | [**中文文档**](README_CN.md)

</div>

---

## v3.0 是什么

Memory Sidecar v3.0 是一个**外挂记忆系统**，兼容 Hermes、Claude Code、Cursor、Codex 等任意 AI 智能体。  
它不修改智能体核心代码，而是运行在智能体旁边，负责：

- 持久保存会话记忆，跨重启不丢失
- 将高价值会话归档到 gbrain 长期知识层
- 生成 canonical memory object 与治理索引
- 为重要人物 / 项目 / 主题建立 Focused Dossier（重点档案）
- 分层召回（L1/L2/L3），意图识别 + RRF 融合 + 重排序
- 健康监控、验收检查和 sticky backlog 排空
- **可选语义检索**（通过向量索引 + cosine similarity）

**多智能体兼容**：全部脚本使用 `AGENT_HOME` 环境变量（向后兼容 `HERMES_HOME`）。  
只需设置 `AGENT_HOME` 指向智能体数据目录即可挂载。

---

## 架构

```text
智能体核心
  └─ 写入 state.db + session JSON

Sidecar 采集层
  └─ session_to_gbrain.py            — 增量会话采集 → gbrain 归档

Sidecar 治理层
  ├─ memory_family_registry.py       — 查询意图分类 + Focused Profile
  ├─ memory_governance_rebuild.py    — canonical 对象、hub、多版本状态、向量索引
  └─ memory_guardian.py              — 容量监控、consolidation 排空、stuck 操作恢复

Sidecar 召回层
  └─ tiered_context_injector.py      — 分层召回（L1/L2/L3）、RRF 融合、重排序

Sidecar 运维 + 验收
  ├─ memory_maintenance_cycle.py     — 编排器：归档 → 重建 → 排空 → 召回 → 健康
  └─ sidecar_acceptance_check.py     — 生产验证套件
```

技术细节见 [ARCHITECTURE_CN.md](ARCHITECTURE_CN.md)。

---

## 快速开始

### 前提条件

- Python 3.9+
- [gbrain](https://github.com/hi-ogawa/gbrain) 已安装并运行
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) 正在运行（默认端口 8890）
- 已有智能体（Hermes / Claude Code 等）正在产生会话

### 安装

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
python3 installer/install.py
```

非交互方式并指定 Embedding Model：

```bash
python3 installer/install.py --noninteractive --embedding intfloat/multilingual-e5-small
```

安装器会将脚本部署到 `$AGENT_HOME/scripts/`，修补 `$AGENT_HOME/config.yaml`，并将元数据写入 `$AGENT_HOME/memory-sidecar/install-profile.json`。

### 挂载到不同智能体

```bash
export AGENT_HOME=/home/user/.my-agent
python3 installer/install.py --noninteractive
```

向后兼容 `--hermes-home` 参数和 `HERMES_HOME` 环境变量。

### 运行一次维护周期

```bash
AGENT_HOME=/root/.hermes python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py
```

### 运行验收检查

```bash
AGENT_HOME=/root/.hermes python3 /root/.hermes/scripts/sidecar_acceptance_check.py
```

---

## 实际安装的脚本

当前生产版 sidecar 只支持这 7 个脚本：

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

---

## 这个外挂记忆体如何工作

### 1. 会话采集

智能体正常写入 `state.db` 和 session JSON。  
Sidecar 通过 checkpoint 增量读取。

### 2. 长期归档

`session_to_gbrain.py` 把高价值会话转为 gbrain page，添加 tags、timeline entry、topic hub 链接。

### 3. 治理重建

`memory_governance_rebuild.py` 重建：

- session 索引（FTS5）
- hindsight 索引
- memory hub（主题聚合器）
- canonical memory object，含多版本状态（`active` / `superseded`）和时间有效性（`valid_from` / `valid_to`）
- conflict group（去重分组）
- dossier 元数据
- recall metrics
- **向量嵌入**（配置 `EMBEDDING_API_URL` 后自动生成）

同时维护修复基础设施：
- `orphan_messages` — 孤儿消息审计表
- `session_repair_map` — 消息→会话修复映射
- `session_lineage_repair` — 会话父链修复
- `recovered_fragments` — 无法归属的记忆碎片归档
- `memory_aliases` / `memory_relations` — 别名与关系图
- `sessions_effective` 视图 — 修复后的会话视图

### 4. 分层召回

`tiered_context_injector.py` 先判断 query intent，再融合多层证据：

- hub summary（主题级）
- canonical object（事实级，已过滤 superseded 版本）
- hindsight cache（预索引的 hindsight 记忆）
- live hindsight（实时召回，按策略触发）
- **语义搜索**（向量索引可用时）
- 必要时才允许弱 fallback 层（FTS5 / LIKE / semantics）

### 5. 健康与修复

`memory_guardian.py` 暴露容量 / 使用率、重复计数、同步延迟、consolidation backlog 趋势、stuck 操作检测，并提供安全排空逻辑。

---

## Focused Dossier（重点档案）

v3.0 引入了 **Focused Dossier** 概念。  
它将重要人物、关系、项目、事件或主题提升为一级记忆对象。  
生产版已验证了 relationship dossier（`kiki`），共享 registry 支持扩展到更多重点对象。

---

## Embedding Model 选择

Embedding model 为 L3 召回提供**语义向量检索**能力。  
配置 `EMBEDDING_API_URL` 后，governance rebuild 会自动为每个 active `memory_object` 生成 384–1024 维向量，存入 `canonical_semantic_index` 表。召回时通过 cosine similarity 与基于关键词的 FTS5、LIKE 路径一起参与 RRF 融合。

### 对召回质量的影响

- **语义匹配**：向量捕获含义而非关键词重叠，中文查英文内容也能命中
- **跨语言检索**：中英混合查询质量显著提升
- **Dossier 聚类**：即使表述不同，关于同一主题的对象也会被聚合
- **减少 fallback 依赖**：语义索引充分时，弱 FTS5 / LIKE fallback 触发更少

### 部署 Embedding 服务

Sidecar 不捆绑 embedding 服务。你需要独立运行一个，然后把地址告诉 sidecar。

**推荐方式：使用 sentence-transformers**

```bash
pip install sentence-transformers flask
```

创建一个提供 OpenAI 兼容 `/v1/embeddings` 端点的简单服务：

```python
# embedding_server.py（示例 — 使用你选择的模型）
from sentence_transformers import SentenceTransformer
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

model = SentenceTransformer("intfloat/multilingual-e5-small")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        texts = body.get("input", [])
        emb = model.encode(texts, normalize_embeddings=True).tolist()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"embedding": e} for e in emb]}).encode())

HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
```

设置环境变量并运行 governance rebuild：

```bash
export EMBEDDING_API_URL=http://127.0.0.1:8766/v1/embeddings
python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py
```

**不配置 `EMBEDDING_API_URL` 时，sidecar 完全无需向量索引即可运行**——所有基于文本的检索（FTS5 / LIKE / hindsight / gbrain）正常工作。

### 安装时如何选择

安装器支持三种方式：
- 交互式选择
- `--embedding <model-id>` 显式指定
- `--noninteractive` 使用默认推荐模型

选择的模型记录在 `install-profile.json` 中作为元数据。**安装器不会自动部署模型服务**——你需要用所选模型自己运行 embedding 服务。

### 当前支持的模型

| 模型 | 语言 | 维度 | 体积 | 适合场景 |
|---|---|---|---:|---|
| `intfloat/multilingual-e5-small` | 100+ 语言 | 384d | ~470MB | **默认推荐**，适合中英混合部署 |
| `BAAI/bge-small-zh-v1.5` | 中文优先 | 512d | ~96MB | 资源极紧、中文为主 |
| `paraphrase-multilingual-MiniLM-L12-v2` | 50+ 语言 | 384d | ~471MB | 生态成熟的 multilingual sentence-transformers |
| `Alibaba-NLP/gte-multilingual-base` | 75+ 语言 | 768d | ~610MB | 更高多语言召回质量 |
| `sentence-transformers/LaBSE` | 109 语言 | 768d | ~471MB | 强跨语种对齐场景 |
| `BAAI/bge-m3` | 100+ 语言 | 1024d | ~2GB | 硬件充裕时追求最高精度 |

### 默认推荐

```text
intfloat/multilingual-e5-small
```

原因：
- 多语言覆盖广（100+ 语言）
- 对生产级记忆召回足够稳定
- 资源占用适中（~470MB）
- 安全的中英混合默认选择

如果纯中文部署且机器资源紧张，可用 `BAAI/bge-small-zh-v1.5`（仅 96MB）。

---

## Choosing Your Retrieval Engine（检索引擎选择）

在 v3.0 中，"检索引擎"不等于"换一个数据库"。  
它真正指的是 **sidecar 采用什么检索剖面来组织多层证据**。

### 当前生产剖面：Hybrid Sidecar

本仓库只维护一个正式部署剖面：

- **Hybrid Sidecar**（推荐）

它组合了以下各层：

| 层级 | 来源 | 职责 |
|---|---|---|
| L1: 最近会话 | `state.db` sessions 表 | 即时上下文 |
| L2: FTS5 + LIKE 搜索 | `state.db` messages_fts / messages / sessions | 基于关键词的会话检索 |
| L3: 治理对象 | `memory_governance.db`（FTS5） | Canonical 长期记忆，含多版本过滤 |
| L3: Hindsight 缓存 | `memory_governance.db` hindsight_index | 预索引的 Hindsight 记忆 |
| L3: 主题 Hub | `memory_governance.db` memory_hubs | 主题级聚合器 |
| L3: **语义向量** | `canonical_semantic_index` | Cosine similarity 语义搜索 |
| Live Hindsight | Hindsight HTTP API | 实时事实召回（按策略触发） |
| Fallback: semantics | `semantics.db` | 基于 LIKE 的嵌入内容搜索 |
| Fallback: archives | `state.db` archives_fts | 归档会话摘要的 FTS5 搜索 |

所有层通过 **RRF（Reciprocal Rank Fusion）** 融合，并经过意图感知重排序。

### 检索如何适配不同意图

| 需求 | 主导层 |
|---|---|
| 当前 system / provider 状态 | governance object + system hub |
| 关系类记忆 | dossier hub + live hindsight + hindsight cache + **语义向量** |
| 项目交付 | canonical project object + hindsight cache |
| 探索型问题 | 更宽的 governance/object 证据，有限 fallback |
| 冷归档追溯 | gbrain session page + topic hub |
| 最近对话 | L1 最近会话 + L2 FTS5 |

### 为什么不再宣传"引擎自由切换"

早期草稿曾把项目写成可以任意切换 PostgreSQL / Elasticsearch / SQLite 等引擎。  
但那不是最终的生产现实。最终稳定下来的版本是：

- **sidecar-first**
- **agent-agnostic**（基于 `AGENT_HOME`）
- **Hindsight-backed**
- **gbrain-archived**
- **governance-indexed**
- **semantically-enhanced**（可选向量索引）

这个收窄定义让项目更干净、更可维护、更可可靠地重部署。

---

## 运行流程

```text
智能体写入新会话
  -> session_to_gbrain.py 处理归档候选
  -> memory_governance_rebuild.py 重建 object / hub / metrics / 向量
  -> memory_guardian.py 检查 backlog 和健康状态
  -> tiered_context_injector.py 生成分层记忆上下文
  -> 智能体在需要时消费这些上下文
```

## 验证流程

1. 本地开发
2. 本地编译
3. 备份服务器脚本
4. 部署到 `$AGENT_HOME/scripts/`
5. 运行 `memory_maintenance_cycle.py`
6. 运行 `sidecar_acceptance_check.py`
7. 确认关键业务回归 query 仍然正常

## 仓库结构

```text
installer/     安装入口、config patch 辅助、环境检查
scripts/       最终 sidecar 运行脚本（7 个受支持脚本）
skills/        智能体端记忆技能
templates/     模板
tests/         仓库导入与 smoke 校验
```

---

## 致谢

### 核心参考项目与生态

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — 本 sidecar 最初与之并肩构建的智能体
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) — 短中期事实图谱
- [gbrain](https://github.com/hi-ogawa/gbrain) — 个人知识图谱引擎
- [sentence-transformers](https://www.sbert.net/) — 嵌入模型框架
- [OpenCode](https://opencode.ai) — 指导设计的智能编程助手
- [PostgreSQL](https://www.postgresql.org/) — gbrain 后端存储
- [pgvector](https://github.com/pgvector/pgvector) — PostgreSQL 向量扩展
- [SQLite](https://www.sqlite.org/) — state.db 和 governance.db 后端存储
- [FTS5](https://www.sqlite.org/fts5.html) — 会话和对象索引的全文检索引擎

### Embedding 模型提供方

- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [sentence-transformers/LaBSE](https://huggingface.co/sentence-transformers/LaBSE)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)

### 社区反馈致谢

感谢通过以下渠道持续提出问题、反馈召回缺陷、推动架构演进的用户：

- **GitHub Issues** — Bug 报告、功能请求和架构讨论
- **GitHub Discussions** — 设计评审和部署问题
- **Reddit** — r/LocalLLaMA、r/MachineLearning 等社区
- **V2EX** — 中文用户反馈和问题报告
- **直接服务器端生产反馈** — 分享真实召回缺失和性能数据的 Hermes 用户

这些反馈直接推动了最终 v3.0 sidecar 的形成——从最初的 4 层架构，到多智能体支持、conflict group 去重、多版本状态、时间有效性治理，再到可选向量索引。

---

## License

本项目供参考和部署使用。  
各依赖项请参阅其各自的许可证。
