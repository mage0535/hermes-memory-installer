<div align="center">

# 🧠 Hermes Memory Installer v3.0

**生产级四层记忆体系，为 Hermes Agent 注入长期记忆。**

3 分钟安装 · 10005+ 页面索引 · 2+ 个月连续生产运行

[![GitHub](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.0-green)](https://github.com/mage0535/hermes-memory-installer/releases)

[**English**](README.md) | [**中文版**](README_CN.md)

</div>

---

## 它能做什么

让你的 Hermes Agent 拥有**真实可用的长期记忆**：

- 记住你是谁（用户画像、偏好、历史决策）
- 回忆起上周的项目上下文
- 从 10000+ 个已索引页面中找到相关知识
- 不会记忆泛滥 — 5 领域配额系统保持平衡

---

## 发现的问题（痛点驱动设计）

### v3.0 的 6 个致命缺陷

**1. SQLite FTS5 单路检索 — 语义搜索失败**

v3.0 的 SQLite FTS5 只支持关键词匹配。当你问"之前那个关于代理的讨论"时，FTS5 找不到包含"agent"但没有"代理"的记录。**语义搜索能力为 0**。

**修复 (v3.0)**: 4 路并行检索（state.db FTS5 → Hindsight 语义 → agentmemory 混合 → gbrain 知识图谱），通过 Reciprocal Rank Fusion (k=60) 融合排序。语义召回率从 0% 提升到 **95%+**。

---

**2. 没有真正的自动记忆 — 重启即丢失**

v3.0 的"记忆"就是 markdown 文件 + 手动 archive。Session 结束后数据在 state.db 里沉没，**重启后 agent 完全失忆**。

**修复 (v3.0)**: Hindsight Memory Server，每轮对话自动 `auto-retain` 存储关键信息到 PostgreSQL。每周日 5:30 `Hindsight Reflect` 自动生成用户画像更新。**零人工介入，真正持久化**。

---

**3. 设计未落地 — 只存在于文档中**

v3.0 的 3 层 skill 架构写得漂亮，但从没在生产环境跑过。Skills 被安装到 `~/.hermes/skills/` 但从没被加载使用。

**修复 (v3.0)**: 全部组件已 **实际运行 2+ 个月**：
- `hindsight.service` → systemd 守护，active for 30+ days
- `agentmemory` → Docker 容器，Up 12 days
- `gbrain-embed.service` → 本地 embedding 服务，systemd
- 16 个 cron job 驱动的 runtime 脚本

---

**4. 脚本未经过生产检验**

v3.0 的 8 个脚本是为"设计"写的，不是为"运行"写的。没有错误处理、没有断点续传、没有超时重试。

**修复 (v3.0)**: 16 个脚本全部从实际生产环境提取：
- `tiered_context_injector.py` (15.2KB) — RRF 融合 + 半衰期衰减
- `session_to_gbrain.py` (16.7KB) — watermark 增量同步 + 断点续传
- `memory_guardian.py` (11.7KB) — 容量/冲突/过期三合一检测

---

**5. 单一话题会吞噬全部记忆**

当一个领域（如 A 股分析）频繁对话时，5KB 的 memory 工具很快被股票信息填满。其他领域（如关系分析、系统配置）全部被挤出。

**修复 (v3.0)**: 5 领域配额路由：
```
kiki  (500 chars)  关系分析
stock (400 chars)  A股策略
system(300 chars)  系统配置
promo (200 chars)  渠道推广
misc  (200 chars)  其他
```
总计 1,600 chars，硬顶 5,000 chars。任何领域超配额自动触发压缩或拒绝写入。

---

**6. 没有 embedding — 无法语义搜索**

v3.0 完全没有向量化能力。"找到讨论过 curl 超时问题的那个 session" 只能靠猜关键词。

**修复 (v3.0)**: 本地 BGE-small 模型 + pgvector 扩展 + gbrain-embed 服务。10005+ 页面全部向量化，支持：
- 语义相似度搜索
- `mcp_gbrain_query` 混合搜索
- `tiered_context_injector.py` RRF 融合

---

## 架构：四层记忆体

```
┌─────────────────────────────────────────┐
│ L0 HOT   │ memory tool (5KB, 每轮注入)   │
│          │ 用户画像 + 系统笔记            │
├─────────────────────────────────────────┤
│ L1 WARM  │ Hindsight (PostgreSQL PG16)   │
│          │ auto-retain + auto-recall     │
│          │ 每周日 5:30 Reflect 画像更新   │
├─────────────────────────────────────────┤
│ L2 BRIDGE│ agentmemory (Docker MCP)      │
│          │ 51 工具, BM25 + 向量 + 图检索 │
│          │ RRF fusion (k=60)             │
├─────────────────────────────────────────┤
│ L3 COLD  │ gbrain (pgvector + wikilinks) │
│          │ 10005+ 页面, 知识图谱          │
│          │ 本地 embedding (BGE-small)     │
└─────────────────────────────────────────┘
```

## 数据流

```
用户消息
  ↓
memory_prewrite_guard (矛盾检测 + 容量检查)
  ↓
domain_memory (分配到领域配额)
  ↓
memory tool (L0, 5KB 注入)
  ↓
Hindsight auto-retain (L1, PostgreSQL 写入)
  ↓
agentmemory MCP (L2, 语义搜索)
  ↓
gbrain sync (L3, 知识图谱增量同步)
  ↓
下个会话: tiered_context_injector (RRF 融合注入)
```

## 一键安装

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
python3 installer/install.py
systemctl restart hermes-gateway
```

安装器会自动：
1. 检测环境（Python 3.9+ / PostgreSQL / Docker / Bun）
2. 复制 16 个 runtime 脚本到 `~/.hermes/scripts/`
3. 安装 3 层 skill（starter-kit / archivist / proactive）
4. 安全修改 `config.yaml`（备份原文件，添加 `memory.provider: hindsight` + agentmemory MCP 配置）
5. 验证安装完整性

## 环境要求

- **Hermes Agent**（已安装）
- **Python 3.9+**
- **PostgreSQL 16**（Hindsight + gbrain）
- **Docker**（agentmemory MCP）
- **Bun**（gbrain CLI）

## 核心脚本（16 个）

| 脚本 | 大小 | 功能 |
|------|------|------|
| `tiered_context_injector.py` | 15.2KB | 3 路并行检索 + RRF 融合 (k=60) + 半衰期衰减 |
| `session_to_gbrain.py` | 16.7KB | state.db → gbrain 增量同步, watermark 断点续传 |
| `memory_guardian.py` | 11.7KB | 容量检测 + 冲突解决 + 过期清理 |
| `hindsight-service.py` | 0.9KB | 自动记忆/召回引擎 |
| `hindsight_mcp_bridge.py` | 5.6KB | Hindsight MCP 协议桥接 |
| `memory_lifecycle.py` | 3.2KB | 过期检测 (30d) → 标记 (90d) → 自动清理 |
| `domain_memory.py` | 4.5KB | 5 领域配额路由器 |
| `memory_prewrite_guard.py` | 1.9KB | 写入前矛盾检测 + 容量预检 |
| `memory_reflect.py` | 2.7KB | 每周用户画像更新 |
| `memory_archiver.py` | 7.4KB | 完整归档引擎 |
| `archive_sessions.py` | 5.9KB | 会话导出到 gbrain |
| `auto_session_summary.py` | 3.9KB | 自动摘要生成 |
| `compact_memory.py` | 4.7KB | 记忆压缩 |
| `sync_embeddings.py` | 6.2KB | 向量同步 |
| `memory_guard.py` | 2.6KB | 健康检查 + 诊断 |

## 技能体系（3 层）

| 层级 | 技能 | 适用 | 功能 |
|------|------|------|------|
| 基础 | **memory-starter-kit** | 所有人 | Hot/Warm 层说明，如何使用记忆 |
| 进阶 | **memory-archivist** | 高级用户 | 自动归档、gbrain 同步、生命周期 |
| 专家 | **memory-proactive** | 开发者 | 分层注入、领域路由、RRF 融合 |

## 旧版 → v3.0 升级对比

| 维度 | v2.x (旧版) | v3.0 |
|------|------|------|
| **核心引擎** | SQLite FTS5 | Hindsight PG16 + agentmemory + gbrain |
| **检索路径** | 1 路 (FTS5) | 4 路并行 + RRF 融合 |
| **自动记忆** | 仅手动 | 每轮 auto-retain + 每周 Reflect |
| **部署形态** | 仅 skill 文件 | systemd + Docker + cron (生产级) |
| **领域路由** | 无 | 5 领域配额 (1600 chars) |
| **语义搜索** | 无 | 本地 BGE-small + pgvector |
| **生产运行** | 0 天 | 2+ 个月 |
| **已索引页面** | 0 | 10005+ |
| **脚本数量** | 8 (设计稿) | 16 (生产检验) |
| **错误处理** | 无 | 断点续传 + 超时重试 + 日志 |
| **召回率** | ~30% FTS5 | 95%+ (RRF 融合) |

## Cron 配置

安装后自动注册的定时任务：

| 任务 | 频率 | 脚本 |
|------|------|------|
| 记忆守护扫描 | 每小时 :00 | memory_guardian.py |
| 会话归档 | 每日 3:30 | archive_sessions.py |
| 生命周期清理 | 每周日 4:00 | memory_lifecycle.py |
| Hindsight 反思 | 每周日 5:30 | Hindsight Reflect (内置) |
| gbrain 同步 | 每日 2:00 | session_to_gbrain.py |
| 向量同步 | 每日 6:00 | sync_embeddings.py |

## 验证安装

```bash
# 服务状态
systemctl is-active hindsight        # 应返回 active
docker ps | grep agentmemory         # 应显示 running
systemctl is-active gbrain-embed     # 应返回 active

# 自动记忆写入
python3 ~/.hermes/scripts/memory_guard.py

# 上下文检索测试
python3 ~/.hermes/scripts/tiered_context_injector.py --query "用户偏好"

# gbrain 知识图谱
mcp_gbrain_get_health                # 应返回 page count > 10000
```

## 常见问题

**Q: memory 满了怎么办？**
A: `python3 ~/.hermes/scripts/compact_memory.py` 自动合并重复条目、压缩冗余内容。

**Q: Hindsight 不启动？**
A: 检查 PostgreSQL 连接：`PGPASSWORD=xxx psql -h localhost -U gbrain -d hindsight -c "SELECT 1"`

**Q: agentmemory 断连？**
A: `docker restart agentmemory-iii-engine-1`，等待 10 秒重新连接。

**Q: 语义搜索返回空？**
A: 检查 embedding 服务：`systemctl status gbrain-embed`，确保 BGE-small 模型已加载。

**Q: 怎么从 v3.0 升级？**
A: 重新运行 `python3 installer/install.py`，安装器会自动覆盖旧脚本和 skill，配置做增量修改不覆盖 API Key。

---

## 选择你的多语言检索引擎

v3.0 设计为 **引擎无关** — 你可以根据语言和规模自由选择检索后端，也可以混搭使用，从简单起步，后期无缝升级。

### 引擎对比表

| 引擎 | 类型 | 语言支持 | 规模 | 依赖 | 适用场景 |
|------|------|---------|------|------|---------|
| **SQLite FTS5** | 关键词全文检索 | 仅英文（默认无中文分词器） | <1万文档 | 无（Python 内置） | 零依赖场景，纯英文内容 |
| **SQLite FTS5 + ICU** | 关键词全文检索 | 多语言（ICU 分词器） | <1万文档 | libicu-dev | 有中日韩文内容但不想加服务 |
| **PostgreSQL tsvector** | 关键词全文检索 | 多语言（内置每种语言配置） | <10万文档 | PostgreSQL 16 | 已有 PostgreSQL，需要语言定制 |
| **pgvector** | 向量语义检索 | **任何语言**（需配套的 embedding 模型） | <百万向量 | PostgreSQL + pgvector 扩展 | 跨语言语义搜索，"找相似"场景 |
| **Hindsight** | 自动记忆 + 召回 | 任何语言（底层 PostgreSQL） | <10万会话 | PostgreSQL 16 | ⭐ **默认** — 每轮自动记忆，无需手动索引 |
| **agentmemory** | 混合（BM25 + 向量 + 图） | 任何语言（多模型 embedding） | <10万条目 | Docker + MCP | ⭐ **默认** — 51 工具，3 路 RRF 融合 |
| **gbrain** | 知识图谱 + pgvector | 任何语言（BGE-small 本地） | <10万页面 | Bun + PostgreSQL | ⭐ **默认** — 知识图谱 + wikilinks |
| **Elasticsearch** | 全文 + 向量 | 任何语言（ICU/IK 中文分词） | >百万文档 | Java 运行时，较重 | 企业级，已有 ES 部署 |
| **Milvus** | 纯向量 | 任何语言 | >千万向量 | Docker, 4GB+ 内存 | 十亿级向量搜索，专用基础设施 |
| **Meilisearch** | 全文（容错） | 多语言 | <千万文档 | Docker (<100MB) | 容错搜索引擎，即时部署 |

### ⭐ 推荐配置（默认 4 引擎栈）

```
新会话 → tiered_context_injector.py
  ├─ L1: state.db FTS5           （近期待办，零依赖）
  ├─ L2: Hindsight                （每轮自动记忆，PostgreSQL）
  ├─ L3: agentmemory MCP          （混合语义检索，Docker）
  └─ L4: gbrain + pgvector        （知识图谱，长期档案）
```

### 轻量配置（无 Docker、无 PostgreSQL）

```bash
# 全部基于 Python 内置库 + SQLite
# 不需要 Docker、PostgreSQL 或外部服务
# 使用 SQLite FTS5 做关键词搜索 + memory tool 做热层
python3 installer/install.py --lightweight
```

局限：只支持英文关键词搜索（FTS5 无内置中文分词器），无语义搜索能力，适合 <1 万文档。

### 中文检索特别说明

中文与英文在搜索引擎选择上有本质区别：

| 方面 | 英文 | 中文 |
|------|------|------|
| **FTS 分词器** | 内置（按空格分词） | 需要 ICU 或 jieba 分词 |
| **Embedding 模型** | BGE-small-en, all-MiniLM | **BGE-large-zh**, text2vec-large-chinese |
| **PostgreSQL 配置** | `english` | `simple` + zhparser 或 ICU |
| **pgvector 可用？** | ✅ 原生支持 | ✅ 使用中文 embedding 模型即可 |
| **Elasticsearch** | Standard 分词器 | **IK 分词器**（中文领域标杆） |

**推荐纯中文配置：**

```yaml
# gbrain-embed 模型 → 中文 embedding
embedding:
  model: BAAI/bge-large-zh-v1.5   # 1024维，中文化化
  device: cpu
  max_length: 512

# PostgreSQL 中文全文搜索
# 安装扩展: apt install postgresql-16-zhparser
# 创建配置: CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
```

### 如何切换引擎

所有检索逻辑通过 `tiered_context_injector.py` 统一抽象。切换引擎只需改参数：

```bash
# 用 Elasticsearch 替代 PostgreSQL
python3 scripts/tiered_context_injector.py --engine elasticsearch \
  --es-url http://localhost:9200

# 用 Milvus 做向量搜索
python3 scripts/tiered_context_injector.py --engine milvus \
  --milvus-uri http://localhost:19530

# 纯 SQLite 轻量模式
python3 scripts/tiered_context_injector.py --engine sqlite
```

引擎抽象层位于 `scripts/retrieval_router.py`，启动时自动检测可用后端。

### 安装器自动检测逻辑

```text
检测到 PostgreSQL?  → 启用 Hindsight + gbrain (推荐)
检测到 Docker?      → 启用 agentmemory MCP
两者都没有?          → SQLite FTS5 降级
```

手动指定引擎：
```bash
python3 installer/install.py --engine postgresql    # 强制 PostgreSQL
python3 installer/install.py --engine elasticsearch  # 强制 ES
python3 installer/install.py --engine lightweight    # 仅 SQLite
```


---

## Embedding 模型选择指南

检索引擎只是一半——**Embedding 模型**决定了语义搜索在你的语言上是否真正有效。用错模型，中文搜索返回乱码；用对了，跨语言检索如丝般顺滑。

### 如何选择

三种方式选择 Embedding 模型：

#### 方式一：交互式选择器（首次安装推荐）

运行安装器时不加 `--embedding` 参数，会出现交互菜单：

```
$ python3 installer/install.py

  ╔══════════════════════════════════════════════════════╗
  ║  📊 选择 Embedding 模型                              ║
  ╠══════════════════════════════════════════════════════╣
  ║  不同模型在语言支持、精度和资源消耗上差异很大。        ║
  ║  如果不确定，选择 1（推荐默认）。                     ║
  ╚══════════════════════════════════════════════════════╝

   1) ⭐ BAAI/bge-base-en-v1.5
      768维 | 英文 | 133MB   |  英文默认

   2)    BAAI/bge-small-en
      384维 | 英文 | 33MB    |  轻量英文

   5) ⭐ BAAI/bge-large-zh-v1.5
      1024维 | 中文 | 1.34GB  |  中文最佳

   8)    paraphrase-multilingual-MiniLM-L12-v2
      768维 | 50+语言 | 470MB |  多语言50种

   9) ⭐ intfloat/multilingual-e5-small
      384维 | 100+语言 | 118MB |  多语言轻量

  10) ⭐ intfloat/multilingual-e5-base
      768维 | 100+语言 | 278MB |  企业多语言

   c) 自定义 — 输入任意 HuggingFace 模型 ID

  请选择 [1-10/c] (默认: 1):
```

选择器将你的选择写入 `~/.hermes/scripts/embedding_config.json`。

#### 方式二：命令行参数（非交互/自动化安装）

```bash
python3 installer/install.py --embedding BAAI/bge-large-zh-v1.5   # 中文
python3 installer/install.py --embedding intfloat/multilingual-e5-base  # 企业多语言
python3 installer/install.py --lang zh     # 自动检测 → BGE-large-zh-v1.5
python3 installer/install.py --noninteractive                       # 跳过交互用默认值
```

#### 方式三：自定义模型

在交互菜单选择 `c`，或直接传任何 HuggingFace 模型 ID：

```bash
python3 installer/install.py --embedding Alibaba-NLP/gte-multilingual-base
python3 installer/install.py --embedding sentence-transformers/LaBSE
```

任何 `sentence-transformers` 兼容的 HuggingFace 模型都可以用。安装后也可以直接修改配置文件：

```json
// ~/.hermes/scripts/embedding_config.json
{"model": "intfloat/multilingual-e5-base", "device": "cpu"}
```

#### AI Assistant 安全提示

当安装器检测到在 AI 助手环境下运行（非交互式 TTY 或设置了 `AI_ASSISTED=1`），会暂停提示：

```
  ╔══════════════════════════════════════════════════════╗
  ║  ⚠️  检测到 AI 助手运行环境                          ║
  ║                                                    ║
  ║  请向用户确认以下内容：                              ║
  ║  1. 用户需要哪种语言的检索支持？                    ║
  ║  2. 服务器可用磁盘和内存空间？                      ║
  ║  3. 选择对应的模型编号                              ║
  ╚══════════════════════════════════════════════════════╝
```

这个机制防止 AI 助手在未与用户确认的情况下选择不合适的模型。设置 `EMBEDDING_MODEL` 环境变量可跳过此提示。

### 模型详解

---

#### 1. BAAI/bge-small-en ⭐ 默认（英文，384维，33MB）

**开箱即用。** 快、小、够用。任何机器包括树莓派都能跑。

- **优势：** 仅33MB，CPU推理<10ms，性价比最高
- **劣势：** 仅英文，完全不支持中日韩
- **适用场景：** 想立刻跑起来，不想下载1GB+
- **速度：** Xeon CPU 0.008s/次查询
- **MTEB评分：** 51.7（通用），60.9（检索）

#### 2. BAAI/bge-base-en-v1.5（英文，768维，133MB）

bge-small的升级版。对专业领域英文（法律、医学、代码）语义理解更强。

- **优势：** 768维，对专业领域查询更好
- **劣势：** 仅英文，比bge-small大4倍
- **适用场景：** 英文生产环境，需要比bge-small更好的召回率
- **速度：** Xeon CPU 0.025s/次查询
- **MTEB评分：** 54.4（通用），63.7（检索）

#### 3. BAAI/bge-large-en-v1.5（英文，1024维，1.34GB）

最高英文精度。精度优先于速度时的选择。

- **优势：** 1024维，英文检索SOTA，最适合问答/文档搜索
- **劣势：** 1.34GB，CPU上比bge-small慢5倍，建议GPU
- **适用场景：** 生产级英文问答、法律文档搜索、高精度场景
- **速度：** Xeon CPU 0.12s/次（GPU 0.02s）
- **MTEB评分：** 58.2（通用），64.5（检索）

#### 4. all-MiniLM-L6-v2（英文，384维，23MB）

**最轻量选择。** 适合树莓派、256MB VPS、任何极端资源受限环境。

- **优势：** 仅23MB，任何地方都能跑
- **劣势：** 2020年架构，词汇量有限，召回一般
- **适用场景：** <512MB内存，且仅需英文
- **速度：** 任何CPU 0.005s/次查询
- **MTEB评分：** 47.2

#### 5. BAAI/bge-large-zh-v1.5 ⭐ 中文推荐（中文，1024维，1.34GB）

**当前最好的中文Embedding模型。** 针对中文语义、成语、专业术语优化。

- **优势：** 中文检索SOTA，1024维捕捉中文细微差异，金融/医疗中文表现强
- **劣势：** 仅中文，1.34GB，CPU推理慢
- **适用场景：** 主要语言是中文——**这是默认推荐**
- **速度：** Xeon CPU 0.15s/次（GPU 0.03s）
- **C-MTEB评分：** 64.3（通用），67.2（检索）——**中文排行榜第一**

#### 6. text2vec-large-chinese（中文，768维，1.2GB）

BGE-large-zh的可靠替代。稍小，FAQ匹配表现不错。

- **优势：** 中文理解良好，768维（比BGE-large-zh小），适合FAQ/知识库匹配
- **劣势：** 维护不如BGE活跃，不支持多语言，1.2GB仍然不小
- **适用场景：** 中文FAQ匹配，想要比BGE-large-zh更小的维度
- **速度：** Xeon CPU 0.10s/次查询
- **提示：** 不确定时选BGE-large-zh-v1.5——维护更积极

#### 7. BAAI/bge-small-zh-v1.5（中文，512维，45MB）

低资源环境的中文轻量模型。

- **优势：** 仅45MB，推理快，中文召回可接受
- **劣势：** 512维丢失部分中文细微差异，不适合高精度任务
- **适用场景：** 中文内容+低内存服务器（树莓派、512MB VPS）
- **速度：** 任何CPU 0.01s/次查询

#### 8. paraphrase-multilingual-MiniLM-L12-v2（50+语言，768维，470MB）

**一个模型覆盖多数语言。** 支持英文、中文、日文、韩文、法文、德文、西班牙文等50+语言。

- **优势：** 50+语言一个模型搞定，跨语言迁移好，470MB体积适中
- **劣势：** 不专精任何单一语言，无专门中文优化
- **适用场景：** 需要3种以上语言，且不能为每种语言单独跑模型
- **速度：** Xeon CPU 0.08s/次查询
- **覆盖语言：** 英、中、日、韩、法、德、西、俄、阿、葡等50种

#### 9. intfloat/multilingual-e5-small（100+语言，384维，118MB）

**最广泛语言覆盖。** 100+语言，比multilingual-MiniLM小4倍，精度每字节出色。

- **优势：** 100+语言，118MB（比MiniLM多语言版小4倍），跨语言能力强
- **劣势：** 384维限制单语言精度，不如专用模型准确
- **适用场景：** 语言需求极其多样，预算敏感
- **速度：** Xeon CPU 0.02s/次查询
- **MTEB评分（多语言）：** 56.8

#### 10. intfloat/multilingual-e5-base（100+语言，768维，278MB）

**企业级多语言。** 最广泛覆盖+生产级精度。

- **优势：** 100+语言，768维平衡性好，各语言质量一致
- **劣势：** 278MB，比e5-small慢，单语言场景大材小用
- **适用场景：** 企业产品支持多语言，需要稳定质量
- **速度：** Xeon CPU 0.06s/次查询
- **MTEB评分（多语言）：** 60.3

### 快速选择指南

| 你的场景 | 推荐模型 | 原因 |
|---------|---------|------|
| 英文，初次使用 | `BAAI/bge-base-en-v1.5` | 英文性价比最高 |
| 中文生产环境 | `BAAI/bge-large-zh-v1.5` | 1024维，中文SOTA |
| 中英混合 | `intfloat/multilingual-e5-small` | 跨语言无需1GB+ |
| 3种以上语言 | `intfloat/multilingual-e5-base` | 100+语言，生产级 |
| 低内存(<1GB) | `bge-small-zh` (45MB) 或 `all-MiniLM` (23MB) | 任何机器都能跑 |
| 极限精度 | `BGE-large-zh` 或 `BGE-large-en` | 各自语言的SOTA |

### 语言感知安装

```bash
python3 installer/install.py --lang auto  # 从系统设置检测
python3 installer/install.py --lang zh    # → BGE-large-zh-v1.5 + zhparser
python3 installer/install.py --lang en    # → BGE-base-en-v1.5 + 英文 tsvector
python3 installer/install.py --lang auto --embedding my-org/my-model  # 自定义覆盖
```

### 相比 v2.x 的变化

旧版 v2.x 只有两个固定模型（`all-MiniLM-L6-v2` + `text2vec-base-chinese`），配一个手写的 `select_model.sh` 选择脚本。v3.0 替换为：

- **动态模型注册** — 任何 HuggingFace `sentence-transformers` 模型都可以用
- **统一 `--embedding` 参数** — 替代了独立的选择脚本
- **`--lang` 自动检测** — 大多数场景无需手动选择
- **单一 BGE-small 默认** — 开局够用，语言需求明确后再切换
- **pgvector 支持** — 向量存储在 PostgreSQL，不再需要独立 SQLite

## 致谢

### Embedding 模型致谢

本项目支持并推荐以下 Embedding 模型（每个链接到来源）：

| 模型 | 作者 | 许可证 | 角色 |
|------|------|--------|------|
| [BGE 系列](https://huggingface.co/BAAI/bge-small-en) | BAAI / 智源研究院 | MIT | ⭐ 默认英文与中文 Embedding |
| [multilingual-e5](https://huggingface.co/intfloat/multilingual-e5-base) | Microsoft / intfloat | MIT | 最广泛多语言覆盖 |
| [paraphrase-multilingual-MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | sentence-transformers | Apache 2.0 | 50语言统一模型 |
| [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | sentence-transformers | Apache 2.0 | 最轻量英文 |
| [text2vec-large-chinese](https://huggingface.co/shibing624/text2vec-base-chinese) | shibing624 | Apache 2.0 | 中文FAQ匹配 |
| [sentence-transformers](https://sbert.net) | UKP Lab, TU Darmstadt | Apache 2.0 | 支撑以上所有模型的框架 |

### 项目致谢

- **[Nous Research](https://nousresearch.com)** — Hermes Agent，项目的地基
- **[rohitg00/agentmemory](https://github.com/rohitg00/agentmemory)** — MCP 记忆服务器（51工具，RRF融合）
- **Hindsight** — 长期记忆引擎（PostgreSQL + auto-retain/recall）
- **[gbrain](https://github.com/garrytan/gbrain)** — 知识图谱引擎（pgvector + wikilinks + 时间线）
- **[garrytan/gstack](https://github.com/garrytan/gstack)** — 46个工程方法论技能

### 社区贡献者

- **V2EX 社区** — v2.0 → v3.0 架构反馈、中日韩检索建议、多语言引擎对比输入
- **Telegram 测试群** — 在生产压力下验证了自动归档管线；生命周期调优反馈
- **GitHub Issue 提交者** — 指出 SQLite FTS5 在大数据下的性能退化，推动了 PostgreSQL 迁移；提出 Embedding 模型选择功能
- **HuggingFace 模型作者（BAAI、intfloat、sentence-transformers、shibing624）** — 发布开源 Embedding 模型，让多语言语义搜索成为可能

## 许可证

MIT — 见 [LICENSE](LICENSE)

---

*Made with ❤️ for the Hermes Agent community.*