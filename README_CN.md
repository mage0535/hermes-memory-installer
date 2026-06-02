<div align="center">

# Memory Sidecar v3.1.0

**面向任意 AI 智能体的生产级外挂记忆系统。让智能体跨会话记住一切，不碰智能体核心代码。**

[![Version](https://img.shields.io/badge/version-3.1.0-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**English**](README.md) | [**架构文档**](ARCHITECTURE.md)

</div>

---

## 这是什么

AI 智能体会忘事。每次新会话都是白纸一张。

Memory Sidecar 跑在你的智能体旁边——不管是 Hermes、Claude Code、Cursor 还是 Codex——给它装上真正的记忆系统。保存重要对话、构建长期知识库、在需要时把相关上下文喂回去。

不修改智能体代码，纯外挂。独立进程，共享数据目录。

**三件事：**

1. **归档会话到永久知识层**——重启不丢对话
2. **分层召回**——近期上下文 → 语义搜索 → 知识图谱，哪层命中用哪层
3. **重点档案追踪**——重要的人、项目、反复出现的问题，各自有专属"档案"

## 架构一览

```
智能体写入会话 → state.db + 会话文件
              ↓
Sidecar 增量读取，处理新会话
              ↓
  ┌───────────┼───────────┐
  │           │           │
  ▼           ▼           ▼
热层        温层        冷层
(memory     (Hindsight  (gbrain 图谱
 tool,      PostgreSQL)  + FTS5 搜索)
 5KB cap)               
              ↓
  分层上下文注入 → 注入到智能体 system prompt
```

完整技术细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。简版：

| 层 | 存什么 | 技术 | 速度 |
|-------|------|-----------|-------|
| 热 | 当前用户画像 + 系统配置 | memory tool 注入 | 0ms |
| 温 | 提取的事实、重复模式 | Hindsight (PostgreSQL 16) | ~50ms |
| 冷 | 永久归档、知识图谱 | gbrain + FTS5 全文搜索 | ~500ms–2s |

v3.1.0 比 v3.0 精简了一层——去掉了 agentmemory 桥接层。那个 Docker 中间层挂着 13 条过期数据，除了增加延迟没别的用。现在的三层更干净，故障点更少。

## 快速开始

### 你需要什么

- Python 3.9+
- [gbrain](https://github.com/hi-ogawa/gbrain) — 知识图谱，跑在 8787 端口
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) — 事实存储，8890 端口
- PostgreSQL 16 — 上面两者的后端存储
- 一台正在产生会话的 AI 智能体（Hermes / Claude Code / Cursor 等）

### 安装

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

# 设 AGENT_HOME 指向智能体的数据目录
export AGENT_HOME="$HOME/.hermes"   # 也可以是 ~/.claude、~/.cursor 等
./install.sh
```

安装器会：

1. **检查环境** — Python 版本、PostgreSQL 连通性、Hindsight/gbrain 可达性
2. **让你选 Embedding 模型** — 语义搜索用（可选，但推荐）
3. **部署侧车脚本** — 到 `$AGENT_HOME/scripts/`
4. **修补智能体配置** — 如果发现 config.yaml 就加上 memory provider 设置

非交互：

```bash
./install.sh --noninteractive --agent-home "$HOME/.my-agent"
```

### 装完之后

```bash
# 跑一次归档
python3 $AGENT_HOME/scripts/session_to_gbrain.py --resume

# 完整维护周期
python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py

# 验收检查
python3 $AGENT_HOME/scripts/sidecar_acceptance_check.py
```

日常运行建议配个 cron。推荐调度见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 七个核心脚本

| 脚本 | 职责 |
|--------|------|
| `session_to_gbrain.py` | 增量归档会话到 gbrain，含 MCP API 桥接 |
| `memory_governance_rebuild.py` | 重建会话索引、中枢、规范对象、向量索引 |
| `memory_guardian.py` | 容量监控、积压检测、卡住操作恢复 |
| `memory_family_registry.py` | 查询意图分类 + Focused Dossier 路由 |
| `tiered_context_injector.py` | 分层召回：热 → 温 → 冷 → RRF 融合 |
| `memory_maintenance_cycle.py` | 编排器：归档 → 重建 → 排空 → 召回 → 健康 |
| `sidecar_acceptance_check.py` | 生产验证套件 |

## Focused Dossier（重点档案）

有些东西比其他东西重要。一个关键的人。一个长期项目。一个反复出的事故。

v3.1.0 支持声明 **Focused Dossier**——高优先级记忆档案，在召回时得到特殊待遇。一个 dossier 包含：

- **别名列表** — 所有叫法都认得
- **主题标记** — 命中这些关键词就优先走 dossier 检索
- **保留优先级** — 不会被清理
- **时间线追踪** — 大事件按时间排列

第一个投产的 dossier 是 `kiki`——一个关系记忆档案，验证了这套模式在数百个会话、数千条提取事实的规模下工作正常。

加你自己的：编辑 `memory_family_registry.py`，按现有格式加一条 profile 就行。

## Embedding 模型选择

语义搜索需要向量嵌入。侧车支持通过 sentence-transformers 接入不同模型。

安装时选一个。安装器记录你的选择但不部署模型——你需要单独跑 embedding 服务。

**对召回质量的影响：**
- 语义匹配抓的是含义，不是关键词重叠
- 跨语言：中文查询能命中英文内容
- 同一主题即使表述不同也会被聚类

**支持的模型：**

| 模型 | 语言 | 维 | 大小 | 适合场景 |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` ★ | 100+ | 384d | ~470MB | 默认推荐，中英混合 |
| `BAAI/bge-small-zh-v1.5` | 中文 | 512d | ~96MB | 纯中文、资源紧张 |
| `paraphrase-multilingual-MiniLM-L12-v2` | 50+ | 384d | ~471MB | 生态成熟 |
| `Alibaba-NLP/gte-multilingual-base` | 75+ | 768d | ~610MB | 高质量召回、内存充裕 |
| `sentence-transformers/LaBSE` | 109 | 768d | ~471MB | 强跨语言对齐 |
| `BAAI/bge-m3` | 100+ | 1024d | ~2GB | 极致精度、资源充沛 |

### 部署 Embedding 服务

```bash
pip install sentence-transformers flask
```

最小服务器：

```python
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
        self.wfile.write(json.dumps(
            {"data": [{"embedding": e} for e in emb]}
        ).encode())

HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
```

配置好后重建治理索引：

```bash
export EMBEDDING_API_URL=http://127.0.0.1:8766/v1/embeddings
python3 $AGENT_HOME/scripts/memory_maintenance_cycle.py
```

不装 embedding 服务也能用——文本检索（FTS5、LIKE、Hindsight、gbrain）本身就够用。

## 适配任意智能体

Memory Sidecar 和智能体品牌无关。它只读 `$AGENT_HOME/state.db` 和会话文件，完全在智能体进程外运行。

已验证的智能体：
- **Hermes Agent** — 最早适配，2 个月+ 生产运行
- **Claude Code** — 设 `AGENT_HOME=~/.claude` 即可
- **Cursor / Codex** — 共享数据目录模式

安装器优先用 `AGENT_HOME`（向后兼容 `HERMES_HOME`）。如果你的智能体数据目录不标准，`--agent-home` 直接指定。

## 生产数据

不是原型。当前栈在 Hermes 生产环境从 2026 年 4 月起持续运行至今：

- **10,885 个 gbrain 页面** — 完整知识图谱，含时间线
- **42,481 个 Hindsight 节点** — 提取的事实，自动保留/召回/反思
- **105,601 条索引消息** — FTS5 全文搜索覆盖全部会话
- **100% 嵌入覆盖率** — 跨全部内容的向量搜索
- **脑分 73** — gbrain 内容质量评分

## 仓库结构

```
installer/     安装入口、配置修补、环境检查
scripts/       7 个支持的侧车脚本
skills/        智能体端记忆技能（入门套件、主动层、归档员）
templates/     记忆模板
```

## 致谢

### 核心项目

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — 本 sidecar 搭建其旁的智能体
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight) — 短中期事实图谱
- [gbrain](https://github.com/hi-ogawa/gbrain) — 个人知识图谱引擎
- [sentence-transformers](https://www.sbert.net/) — 嵌入模型框架
- [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) — 向量存储骨干
- [OpenCode](https://opencode.ai) — 指导架构设计和生产迭代

### Embedding 模型

- [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [sentence-transformers/LaBSE](https://huggingface.co/sentence-transformers/LaBSE)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)

### 社区

感谢通过 Issues、Discussions、Reddit (r/LocalLLaMA、r/MachineLearning)、V2EX 和生产反馈持续推动架构演进的所有人。你们的反馈直接塑造了 v3.1.0——从四层架构精简到三层，从专人专用到 agent-agnostic，从理论设计到连续生产验证。

---

如果这个项目对你有用，[给个 star ⭐](https://github.com/mage0535/hermes-memory-installer)——别人也能看到它。

## License

MIT。各依赖项见其各自的许可证。
