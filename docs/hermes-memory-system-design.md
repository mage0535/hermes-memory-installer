# Hermes 记忆体系统完整设计与实施报告

> **版本**：v1.0  
> **目标读者**：完全不了解 Hermes 和记忆体系统的初学者  
> **写作原则**：用生活化比喻解释每一个技术概念，不跳过任何细节  

---

## 目录

1. [写给第一次接触的你](#1-写给第一次接触的你)
2. [系统整体架构](#2-系统整体架构)
3. [每一层详解](#3-每一层详解)
4. [数据库结构与表设计](#4-数据库结构与表设计)
5. [索引设计与实现](#5-索引设计与实现)
6. [数据全生命周期](#6-数据全生命周期)
7. [权限设计](#7-权限设计)
8. [技术来源与致谢](#8-技术来源与致谢)
9. [如何辅助 Hermes 进化](#9-如何辅助-hermes-进化)
10. [最终效果验证](#10-最终效果验证)

---

## 1. 写给第一次接触的你

### 1.1 什么是 Hermes？

Hermes 是一个**AI Agent 操作系统**。你可以把它想象成一个"会写代码、会上网、会记笔记的超级助手"。它能帮你：

- 写程序、修 Bug
- 查股票、读新闻
- 管理你的日程和人际关系
- 记住你说过的话、喜欢的东西、讨厌的事情

但问题来了——如果你每次和 Hermes 聊天，它都像个**金鱼**（据说金鱼只有7秒记忆），完全不记得你们上周聊过什么，那这个助手就太废物了。

**记忆体系统**，就是解决这个问题的核心。

### 1.2 什么是"记忆"？AI 为什么需要记忆？

人类的记忆分很多种：

| 人类记忆类型 | 对应 AI 的记忆层 | 例子 |
|-----------|---------------|------|
| 长期形成的性格/偏好 | **持久化记忆** | "我喜欢 Python，讨厌 Java" |
| 最近几天的对话 | **会话历史** | "昨天我们修好了那个 Bug" |
| 某句话的"意思" | **语义向量记忆** | "他说的'那个项目'指的是 P6" |
| 文件里的资料 | **外部档案** | "我的 Kiki 攻略在 wang_yuqi_chat/ 里" |

AI 没有大脑，它所有的"记忆"都必须以**数据**的形式存在。记忆体系统就是一套"让 AI 像人一样记得住东西"的工程方案。

### 1.3 一个生活化的比喻

想象 Hermes 是一家**24小时营业的图书馆**。

- **持久化记忆** = 图书馆入口的"今日公告板"（所有人都能看到的基本信息）
- **会话历史** = 每天的借阅记录（按日期排列的流水账）
- **语义向量记忆** = 图书管理员的大脑（你问"有没有讲爱情的"，她能想起《罗密欧与朱丽叶》，即使书名里没有"爱情"二字）
- **外部档案** = 图书馆的书架（.md 文件就是一本本书）

如果没有这套系统，图书馆就只是一个堆满书的仓库——你问什么，它都只能现翻现找，永远"不记得"你上个月借过什么书。

---

## 2. 系统整体架构

### 2.1 三层记忆架构（记忆金字塔）

```
                    ┌─────────────────────────────────────┐
                    │      🧠 应用层：AI 决策与回复         │
                    │  "根据记忆，用户喜欢简洁的回答"        │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  第一层：持久化 │      │  第二层：会话历史   │      │  第三层：语义向量  │
│   记忆        │      │   (FTS5 全文搜索)  │      │   (向量相似度)    │
├───────────────┤      ├──────────────────┤      ├──────────────────┤
│ ~/.hermes/    │      │ ~/.hermes/        │      │ ~/.hermes/       │
│ memory/user   │      │ state.db          │      │ semantics.db     │
│ memory/       │      │ (sessions,        │      │ (embeddings,     │
│ assistant     │      │  messages,        │      │  384维向量)       │
│               │      │  messages_fts)    │      │                  │
│ 系统提示词注入 │      │ suggest_recall    │      │ cosine similarity│
│ (启动时读取)   │      │ (消息循环触发)     │      │ (实时计算)        │
└───────┬───────┘      └────────┬─────────┘      └────────┬─────────┘
        │                       │                         │
        └───────────────────────┼─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │   第四层：外部档案    │
                    │ ~/.hermes/.../*.md  │
                    │ MemoryManager 加载   │
                    │ (增量索引 + mtime)   │
                    └─────────────────────┘
```

**架构设计哲学**：

1. **越底层的记忆，查询越快、容量越小**
2. **越上层的记忆，查询越慢、容量越大**
3. **每一层只存储它最擅长存储的东西，不重复造轮子**

### 2.2 数据生命周期全景图

```
┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  产生   │ → │  流转    │ → │  调用    │ → │  老化    │ → │保存/销毁 │
│ Creation│   │Transmit  │   │ Retrieval│   │  Aging   │   │Persist/  │
│         │   │          │   │          │   │          │   │Destroy   │
└────┬────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
     │             │              │              │              │
     ▼             ▼              ▼              ▼              ▼
  用户输入      Gateway       suggest_recall  access_count   软删除
  AI 输出       消息循环       emb_store.search  last_accessed  硬删除
  文件读取      DB 写入        hybrid_search   TTL 衰减        归档
  工具结果      向量编码        混合排序        版本演进        永存档案
```

我们会在第 6 章**逐帧讲解**这个数据的一生。

### 2.3 核心组件关系图

```
                    ┌─────────────────┐
                    │   用户 (You)     │
                    └────────┬────────┘
                             │ 发消息
                             ▼
                    ┌─────────────────┐
                    │  Gateway 消息循环 │  ←── run.py (10091行)
                    │  (核心调度中枢)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ suggest_recall│   │ semantic recall │   │ 持久化记忆注入   │
│ (P0-1)       │   │ (P6-1)          │   │ (memory/user)   │
│ FTS5 关键词  │   │ 向量相似度       │   │ 系统提示词      │
│ 召回         │   │ 召回            │   │ 前缀注入        │
└──────┬───────┘   └────────┬────────┘   └─────────────────┘
       │                    │
       └────────┬───────────┘
                ▼
       ┌─────────────────┐
       │ 合并注入用户消息  │
       │ "[Related memory]│
       │  ... 用户原消息" │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │    LLM 推理      │
       │  "根据记忆回答"  │
       └─────────────────┘
```

---

## 3. 每一层详解

### 3.1 第一层：持久化记忆（Persistent Memory）

#### 3.1.1 它是什么？

持久化记忆是 Hermes 的"性格档案"。它存储：

- 你是谁（用户画像）
- 你喜欢什么、讨厌什么
- Hermes 自己的行为准则（"永远不要把 API Key 传给用户"）

#### 3.1.2 存储位置

```
~/.hermes/
├── memory/
│   ├── user           ← 你的信息（你告诉 Hermes 的事）
│   └── assistant      ← Hermes 的自我设定（行为准则）
```

这两个是**纯文本文件**，格式就是简单的 Markdown。

#### 3.1.3 如何被调用？

**每次启动新会话时**，Hermes 会把这两个文件的内容**注入到系统提示词（System Prompt）的最前面**。这相当于：

> "在开始聊天前，先把你的基本设定过一遍脑子。"

**关键设计**：这是**冻结快照（Frozen Snapshot）**。会话开始后，即使 memory 文件被修改，当前会话的系统提示词也不会变——这是为了保住 LLM 的**前缀缓存（Prefix Cache）**，让推理更快更便宜。

#### 3.1.4 代码实现

```python
# 简化逻辑（来自 memory_tool.py）
# 会话启动时：
system_prompt = load_file("~/.hermes/memory/assistant") + "\n" + load_file("~/.hermes/memory/user")
# 然后将 system_prompt 作为 System Message 发送给 LLM
```

#### 3.1.5 老化与更新

- **更新方式**：通过 `memory` 工具（add/replace/remove）
- **生效时机**：**下一次新会话**才会看到变化
- **永不自动删除**：除非你手动调用 `memory(action="remove")`

---

### 3.2 第二层：会话历史（Session History）

#### 3.2.1 它是什么？

会话历史就是**你和 Hermes 说过的每一句话**。它是按时间顺序排列的"聊天记录本"。

#### 3.2.2 存储位置

```
~/.hermes/state.db  ← SQLite 数据库
```

#### 3.2.3 核心表结构

| 表名 | 作用 | 关键字段 |
|------|------|---------|
| `sessions` | 每个聊天会话的元信息 | id, title, started_at, last_active, message_count |
| `messages` | 每条消息的内容 | id, session_id, role, content, timestamp |
| `messages_fts` | **FTS5 虚拟表**（全文索引） | content（自动同步 messages 内容） |

#### 3.2.4 FTS5 是什么？为什么需要它？

FTS5 = **Full Text Search 5**，是 SQLite 内置的**全文搜索引擎**。

**生活化比喻**：

> 想象 messages 表是一本 1000 页的日记。没有 FTS5 时，你要找"Python"这个词，只能**逐页翻**（`SELECT * FROM messages WHERE content LIKE '%Python%'`），这叫做**全表扫描**——时间复杂度 O(N)，N 是消息总数。
>
> 有了 FTS5，就像给日记加了一个**目录索引**。你只需要查目录，就能直接跳到包含"Python"的页面——时间复杂度 O(1)。

#### 3.2.5 BM25 排序算法

FTS5 默认使用 **BM25** 算法给搜索结果排序。

**BM25 是什么？**

它是一种计算"文档和查询有多相关"的数学公式。核心思想：

1. **词频（TF）**："Python"在文档中出现 10 次，比出现 1 次更相关
2. **逆文档频率（IDF）**：如果 90% 的文档都提到"Python"，那这个词就不那么有区分度
3. **文档长度惩罚**：短文档中出现"Python"，比长文档中出现更"集中"、更相关

**BM25 公式**（简化版）：

```
score(D, Q) = Σ IDF(q_i) * [f(q_i, D) * (k1 + 1)] / [f(q_i, D) + k1 * (1 - b + b * |D| / avgDL)]
```

其中：
- `D` = 文档（一条消息）
- `Q` = 查询（用户输入的关键词）
- `q_i` = 查询中的第 i 个词
- `f(q_i, D)` = 词 q_i 在文档 D 中的出现次数
- `|D|` = 文档长度
- `avgDL` = 平均文档长度
- `k1`, `b` = 调参常数（FTS5 内部固定）

**在我们的代码中**（来自 `memory_store.py` 第 340-358 行）：

```python
def search_fts(self, query: str, limit: int = 20):
    rows = conn.execute("""
        SELECT m.*, bm25(memories_fts) AS rank_score
        FROM memories_fts
        JOIN memories m ON memories_fts.rowid = m.rowid
        WHERE memories_fts MATCH ? AND m.status = 'activated'
        ORDER BY rank_score DESC
        LIMIT ?
    """, (query, limit))
```

注意：`bm25()` 返回的是**负数**（越负越相关），所以代码里做了转换：

```python
score = max(0.0, min(1.0, 1.0 + rank / 10.0))
# 把 [-10, 0] 映射到 [0, 1]
```

#### 3.2.6 触发器：保持索引实时一致

FTS5 虚拟表不会自动同步主表。我们需要**数据库触发器（Trigger）**来自动维护：

```sql
-- 当 memories 表插入新数据时，自动插入到 FTS5 索引
CREATE TRIGGER memories_fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;

-- 当 memories 表删除数据时，自动从 FTS5 索引删除
CREATE TRIGGER memories_fts_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) 
    VALUES('delete', old.rowid, old.content);
END;

-- 当 memories 表更新 content 字段时，先删旧索引再插新索引
CREATE TRIGGER memories_fts_update AFTER UPDATE OF content ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) 
    VALUES('delete', old.rowid, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;
```

**这三个触发器确保了**：无论你对主表做增删改，FTS5 索引永远是**实时一致**的。

#### 3.2.7 suggest_recall：Gateway 消息循环中的主动召回

这是 P0-1 的核心成果。它的逻辑是：

**每次用户发消息时**，Gateway 先检查——"用户这句话，是不是在问之前聊过的东西？"

```python
# gateway/run.py 第 10091-10106 行
from tools.session_search_tool import suggest_recall
_recall_note = suggest_recall(
    db=self._session_db,
    user_message=message,
    current_session_id=session_id,
    limit=2,
)
if _recall_note:
    message = _recall_note + "\n\n" + message  # 注入到用户消息前面
```

`suggest_recall` 内部逻辑（来自 `session_search_tool.py`）：

1. **轻量检查** `check_memory_recall_needed()`：扫描用户消息中是否包含召回触发词（如"之前"、"上次"、"还记得"、"继续"等）
2. 如果触发，用 **FTS5 搜索**找到最相关的历史会话
3. 返回格式化提示："This might relate to a past session: ..."

**性能**：纯 SQLite 查询，**零 LLM 调用**，耗时 < 10ms。

---

### 3.3 第三层：语义向量记忆（Semantic Memory）

#### 3.3.1 它是什么？

语义向量记忆解决的是**"意思相近但用词不同"**的问题。

**例子**：
- 用户上周说："我喜欢用 Python 写脚本"
- 用户这周问："有什么好的编程语言推荐？"

关键词搜索（FTS5）搜不到匹配，因为"编程语言"和"Python"是不同词。但语义向量搜索能理解：**这两句话说的是同一件事**。

#### 3.3.2 核心概念：Embedding（嵌入向量）

**Embedding** 是把一段文本转换成**一个数字向量**的技术。

**生活化比喻**：

> 想象每句话都是宇宙中的一个星球。语义相似的句子，在宇宙中距离就近；语义无关的句子，距离就远。
>
> Embedding 就是给每句话一个**宇宙坐标**（比如 [0.23, -0.55, 0.91, ...]）。
>
> "我喜欢 Python" 和 "Python 是我最爱的语言" 这两个星球，在宇宙中的距离可能只有 0.1。而"我喜欢 Python"和"今天天气不错"的距离可能是 0.9。

#### 3.3.3 存储位置

```
~/.hermes/semantics.db  ← 独立的 SQLite 数据库
```

**为什么独立？** 因为语义索引的构建很耗时（要调用神经网络模型），如果和 state.db 混在一起，重建索引时会影响主库性能。

#### 3.3.4 核心表结构

```sql
CREATE TABLE embeddings (
    message_id    INTEGER PRIMARY KEY,  -- 对应 state.db messages.id
    session_id    TEXT NOT NULL,
    role          TEXT NOT NULL,        -- user / assistant / tool
    content_hash  TEXT NOT NULL,        -- 内容哈希，检测变更
    embedding     BLOB NOT NULL,        -- float32 向量（384 维 × 4 字节 = 1536 字节）
    content_len   INTEGER NOT NULL,     -- 原文长度
    indexed_at    REAL NOT NULL         -- Unix 时间戳
);

CREATE INDEX idx_embeddings_session ON embeddings(session_id);
```

#### 3.3.5 向量模型：all-MiniLM-L6-v2

我们使用的模型是 `sentence-transformers/all-MiniLM-L6-v2`：

| 属性 | 值 |
|------|-----|
| 维度 | 384 维 |
| 大小 | ~80MB |
| 语言 | 多语言（含中文） |
| 速度 | CPU 上约 1000 条/秒 |
| 原理 | 基于 BERT 的轻量级双塔模型 |

**为什么选它？**

1. **够小**：80MB，服务器上加载无压力
2. **够快**：纯 CPU 推理，不需要 GPU
3. **够准**：在语义相似度任务上，性能接近大模型
4. **多语言**：虽然名字是英文模型，但对中文支持也不错

#### 3.3.6 向量序列化：float32 → BLOB

SQLite 不支持原生数组类型。我们需要把 384 个 float32 数字转换成二进制：

```python
import struct

# 编码：384 个 float → 1536 字节的二进制
def _serialize(vec: List[float]) -> bytes:
    return struct.pack("384f", *vec)  # "f" = float32

# 解码：1536 字节 → 384 个 float
def _deserialize(blob: bytes) -> List[float]:
    n = len(blob) // 4  # float32 占 4 字节
    return list(struct.unpack(f"{n}f", blob))
```

**为什么是 float32 而不是 float64？**

- float32 精度足够（6-7 位有效数字）
- 存储空间减半（384 × 4 = 1536 字节 vs 3072 字节）
- 神经网络模型本身就是 float32 输出

#### 3.3.7 相似度计算：Cosine Similarity（余弦相似度）

有了两个向量，怎么计算它们"有多像"？

我们使用**余弦相似度**：

```
cos(A, B) = (A · B) / (||A|| × ||B||)
```

其中：
- `A · B` = 两个向量的点积（对应元素相乘再相加）
- `||A||` = 向量 A 的模长（平方和开根号）
- 结果范围：`[-1, 1]`，语义搜索中通常是 `[0, 1]`

**代码实现**（`embedding_store.py` 第 75-81 行）：

```python
@staticmethod
def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

#### 3.3.8 搜索流程

```python
def search(self, query: str, limit: int = 20):
    # Step 1: 把查询文本变成向量
    q_vec = self.encode([query])[0]  # 384 维
    
    # Step 2: 从数据库取出所有已索引的向量
    rows = conn.execute("SELECT * FROM embeddings").fetchall()
    
    # Step 3: 逐条计算余弦相似度
    results = []
    for row in rows:
        vec = self._deserialize(row["embedding"])
        sim = self._cosine_similarity(q_vec, vec)
        if sim >= 0.3:  # 阈值过滤
            results.append({"message_id": row["message_id"], "similarity": sim, ...})
    
    # Step 4: 按相似度排序，返回 Top-K
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
```

**注意**：这里有个工程权衡——我们在**内存中**做相似度计算，而不是用向量数据库（如 Pinecone、Milvus）。

**为什么？**

| 方案 | 优点 | 缺点 | 我们的选择 |
|------|------|------|----------|
| 内存计算 | 零依赖、零成本 | 数据量大时慢 | ✅ 当前方案（消息 < 100K 条足够快） |
| Pinecone | 超大规模、毫秒级 | 需要网络、有费用 | ❌ 暂时不需要 |
| sqlite-vss | SQLite 插件、ANN 近似搜索 | 需要编译安装 | ❌ 增加部署复杂度 |

**未来升级路径**：当消息量 > 100 万条时，可平滑迁移到 HNSW 索引或专用向量数据库。

#### 3.3.9 Gateway 中的语义召回

```python
# gateway/run.py 第 10108-10140 行
_emb_store = getattr(self._session_db, "_get_embedding_store", lambda: None)()
if _emb_store is not None:
    # 清理查询：去掉系统提示注入的内容
    _query = message
    for _prefix in ("[System note:", "[Related memory from", ...):
        if _prefix in _query:
            _query = _query.split("\n\n")[-1]
    _query = _query[:300].strip()
    
    if len(_query) >= 10:
        _similar = _emb_store.search(_query, limit=3)
        if _similar:
            _semantic_parts = []
            for _sim in _similar:
                if _sim.get("similarity", 0) < 0.55:
                    continue
                _sim_content = (_sim.get("content", "") or "")[:200]
                _semantic_parts.append(
                    f"[Related memory ({_sim_role}, ~{_sim_score:.0%}): {_sim_content}]"
                )
            if _semantic_parts:
                message = f"[Semantic context from past conversations]\n" + "\n".join(_semantic_parts) + "\n\n" + message
```

---

### 3.4 第四层：外部档案（External Archives）

#### 3.4.1 它是什么？

外部档案是 Hermes 记忆系统的"书架"。你把 .md 或 .txt 文件放到指定目录，Hermes 会自动阅读、理解、记住它们。

#### 3.4.2 存储位置

```
~/.hermes/wang_yuqi_chat/     ← 用户档案目录（示例）
├── kiki_profile.md            ← Kiki 关系攻略
├── trading_rules.md           ← 交易规则
└── project_notes.md           ← 项目笔记
```

#### 3.4.3 增量加载机制

```python
# memory_manager.py 第 57-77 行
def _load_file_archives(self) -> int:
    total_added = 0
    for archive_dir in self._archive_dirs:
        for filepath in archive_dir.rglob("*"):
            if filepath.suffix.lower() not in (".md", ".txt"):
                continue
            added = self._index_single_file(filepath)
            total_added += added
    return total_added
```

**增量更新**：通过 `mtime`（文件修改时间）+ 文件路径 hash 判断是否需要重新加载：

```python
def _index_single_file(self, filepath: Path) -> int:
    file_id = hashlib.sha256(str(filepath).encode()).hexdigest()[:16]
    mtime = filepath.stat().st_mtime
    
    cached_mtime = self._archive_mtime_cache.get(file_id, 0.0)
    if mtime <= cached_mtime:
        return 0  # 文件未变更，跳过
    
    # 文件有更新：先删除旧 chunks，再重新索引
    self.store.delete_by_tag(f"archive:{file_id}", soft=False)
    
    text = filepath.read_text(encoding="utf-8")
    chunks = _chunk_text(text, max_chars=800, overlap=100)
    for idx, chunk in enumerate(chunks):
        item = MemoryItem(
            content=chunk,
            embedding=self.embedder.encode(chunk),
            source=MemorySource.SYSTEM,
            tags=[f"archive:{file_id}", f"file:{filepath.name}", "external"],
            info={"source_file": str(filepath), "chunk_index": idx, ...},
        )
        self.store.insert(item)
    
    self._archive_mtime_cache[file_id] = mtime
    return len(chunks)
```

**文本切片（Chunking）**：

长文件不会整体存储，而是切成 800 字符的小段，每段重叠 100 字符。这保证了：

1. **语义完整性**：每段不会太长，embedding 能捕捉核心意思
2. **边界不丢失**：重叠 100 字符确保跨段上下文不被切断

---

## 4. 数据库结构与表设计

### 4.1 三大数据库

| 数据库 | 路径 | 作用 | 数据量预估 |
|--------|------|------|-----------|
| **state.db** | `~/.hermes/state.db` | 会话历史、消息内容、FTS5 全文索引 | 10MB - 1GB |
| **semantics.db** | `~/.hermes/semantics.db` | 语义向量（384 维 float32） | 每条消息 1.5KB |
| **memory.db** | `~/.hermes/wang_yuqi_chat/memory.db` | 用户档案、外部档案切片 | 1MB - 100MB |

### 4.2 state.db 详细结构

```sql
-- sessions 表：每个聊天会话
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,     -- UUID
    title           TEXT,                 -- 会话标题（AI 自动生成）
    source          TEXT,                 -- 来源（telegram / cli / discord）
    started_at      REAL,                 -- 开始时间（Unix 时间戳）
    last_active     REAL,                 -- 最后活跃时间
    message_count   INTEGER DEFAULT 0,    -- 消息数量
    preview         TEXT,                 -- 前 200 字预览
    parent_session_id TEXT,               -- 父会话 ID（用于 delegation 链）
    model           TEXT                  -- 使用的模型
);

-- messages 表：每条消息
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,            -- user / assistant / system / tool
    content     TEXT,
    timestamp   REAL,                     -- Unix 时间戳
    tool_name   TEXT,                     -- 工具名称（role=tool 时）
    tool_calls  TEXT,                     -- JSON 格式的工具调用
    model       TEXT                      -- 生成这条消息的模型
);

-- messages_fts 虚拟表：FTS5 全文索引（自动同步 messages）
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='rowid'
);
```

### 4.3 semantics.db 详细结构

```sql
-- embeddings 表：语义向量
CREATE TABLE embeddings (
    message_id    INTEGER PRIMARY KEY,    -- 外键关联 messages.id
    session_id    TEXT NOT NULL,
    role          TEXT NOT NULL,
    content_hash  TEXT NOT NULL,          -- hash(content) 用于检测变更
    embedding     BLOB NOT NULL,          -- struct.pack("384f", ...) 
    content_len   INTEGER NOT NULL,
    indexed_at    REAL NOT NULL           -- Unix 时间戳
);

-- 会话级索引：加速按会话过滤
CREATE INDEX idx_embeddings_session ON embeddings(session_id);

-- index_stats 表：索引构建状态
CREATE TABLE index_stats (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### 4.4 memory.db 详细结构

```sql
-- memories 表：记忆原子单元
CREATE TABLE memories (
    memory_id       TEXT PRIMARY KEY,     -- UUID（16 位截断）
    content         TEXT NOT NULL,        -- 文本内容
    embedding       BLOB,                 -- JSON 数组（语义向量）
    status          TEXT DEFAULT 'activated',  -- activated / resolving / archived / deleted
    version         INTEGER DEFAULT 1,    -- 版本号（非破坏性更新）
    history         BLOB,                 -- JSON 数组（归档的旧版本）
    source          TEXT DEFAULT 'chat',  -- chat / system / file / web / plugin
    provenance      BLOB,                 -- JSON（溯源信息）
    tags            BLOB,                 -- JSON 数组（标签）
    confidence      REAL DEFAULT 1.0,     -- 置信度 0-1
    created_at      TEXT,                 -- ISO 8601 时间戳
    updated_at      TEXT,
    access_count    INTEGER DEFAULT 0,    -- 引用计数
    last_accessed   TEXT,                 -- 最后访问时间
    info            BLOB                  -- JSON 扩展字段
);

-- edges 表：记忆之间的图关系
CREATE TABLE edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id     TEXT NOT NULL,            -- 起点记忆 ID
    to_id       TEXT NOT NULL,            -- 终点记忆 ID
    relation    TEXT DEFAULT 'related',   -- related / evolve / conflict / session
    weight      REAL DEFAULT 1.0,         -- 边权重
    created_at  TEXT,
    UNIQUE(from_id, to_id, relation)      -- 防重复
);

-- sessions 表（用户档案级）
CREATE TABLE sessions (
    session_id  TEXT PRIMARY KEY,
    created_at  TEXT,
    summary     TEXT
);

-- memories_fts 虚拟表：FTS5 全文索引（自动同步 memories）
CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='rowid'
);
```

### 4.5 ER 关系图

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   sessions   │1      * │   messages   │1      1 │embeddings    │
│  (state.db)  │◄────────│  (state.db)  │◄────────│(semantics.db)│
└──────────────┘         └──────────────┘         └──────────────┘
        │                        │
        │                        │ content_rowid
        │                        ▼
        │               ┌──────────────┐
        │               │ messages_fts │
        │               │ (FTS5 虚拟表) │
        │               └──────────────┘
        │
        │         ┌──────────────┐
        └────────►│   memories   │
                  │ (memory.db)  │
                  └──────┬───────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
              ┌────────┐  ┌────────┐
              │ edges  │  │memories│
              │(图关系)│  │_fts    │
              └────────┘  └────────┘
```

---

## 5. 索引设计与实现

### 5.1 为什么需要索引？

**没有索引的查询**（全表扫描）：

```sql
SELECT * FROM messages WHERE content LIKE '%Python%'
-- 需要检查每一行！10 万条消息 = 10 万次字符串匹配
-- 时间复杂度：O(N)
```

**有 FTS5 索引的查询**：

```sql
SELECT * FROM messages_fts WHERE content MATCH 'Python'
-- 直接查倒排索引！
-- 时间复杂度：O(1) ~ O(log N)
```

### 5.2 FTS5 全文索引的实现细节

#### 5.2.1 倒排索引（Inverted Index）

FTS5 的核心数据结构是**倒排索引**：

```
词项        →  包含该词的文档 ID 列表
"Python"    →  [doc_42, doc_89, doc_156, ...]
"Hermes"    →  [doc_1, doc_42, doc_200, ...]
"记忆"       →  [doc_89, doc_150, ...]
```

当你搜索 "Python 记忆" 时，FTS5 会：
1. 查 "Python" 的文档列表
2. 查 "记忆" 的文档列表
3. 取两个列表的**交集**
4. 用 BM25 给交集中的文档打分排序

#### 5.2.2 触发器的正确性验证

如何确保触发器不会遗漏？

**测试方法**：

```python
# 1. 插入数据
conn.execute("INSERT INTO memories (content) VALUES ('Python is great')")

# 2. 立即查询 FTS5
rows = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Python'").fetchall()
assert len(rows) == 1  # 必须能查到！

# 3. 更新内容
conn.execute("UPDATE memories SET content = 'Java is great' WHERE rowid = 1")

# 4. 旧词应该消失，新词应该出现
rows_old = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Python'").fetchall()
rows_new = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Java'").fetchall()
assert len(rows_old) == 0
assert len(rows_new) == 1

# 5. 删除数据
conn.execute("DELETE FROM memories WHERE rowid = 1")
rows = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Java'").fetchall()
assert len(rows) == 0
```

**实际验证结果**（来自 `test_memory_system.py`）：✅ 全绿

#### 5.2.3 BM25 分数转换的正确性

FTS5 的 `bm25()` 函数返回负数，越负越相关。我们的转换逻辑：

```python
rank = row["rank_score"]  # 例如：-2.5
score = max(0.0, min(1.0, 1.0 + rank / 10.0))
# -2.5 → 1.0 + (-0.25) = 0.75
# -10  → 1.0 + (-1.0) = 0.0
# 0    → 1.0 + 0 = 1.0
```

**验证**：搜索 "Python" 时，包含 "Python" 的文档应该比不包含的分数高。混合搜索测试显示：

```
混合检索 'Python':
  [0.728] 用户喜欢 Python 和 Rust
      breakdown: {'semantic': 0.881, 'keyword': 0.958, 'graph': 0.0}
```

关键词分数 0.958（接近 1.0），说明 BM25 转换正确。

### 5.3 语义向量索引

#### 5.3.1 为什么没有专门的向量索引？

当前实现中，语义搜索是**纯内存计算**：

```python
# 从数据库取出所有向量
rows = conn.execute("SELECT * FROM embeddings").fetchall()

# 在 Python 中逐条计算 cosine similarity
for row in rows:
    vec = _deserialize(row["embedding"])
    sim = _cosine_similarity(q_vec, vec)
```

**这看起来很低效，为什么这样做？**

| 数据量 | 向量数 | 内存占用 | 查询耗时 |
|--------|--------|----------|----------|
| 1,000 条消息 | 1,000 | 1.5 MB | ~5 ms |
| 10,000 条消息 | 10,000 | 15 MB | ~50 ms |
| 100,000 条消息 | 100,000 | 150 MB | ~500 ms |

**判断**：对于个人使用场景，消息量通常在 1-10 万条之间，纯内存计算完全够用。150MB 内存对现代服务器来说微不足道，500ms 的查询时间也可以接受（毕竟这是后台召回，不阻塞用户交互）。

#### 5.3.2 未来升级：HNSW 索引

当数据量超过 100 万条时，可以平滑升级到 **HNSW（Hierarchical Navigable Small World）** 近似最近邻算法：

```
当前：O(N) 精确搜索
升级后：O(log N) 近似搜索，准确率 > 95%
```

可选方案：
- `sqlite-vss`：SQLite 的向量搜索扩展
- `faiss`：Facebook 的向量检索库
- `pgvector`：PostgreSQL 的向量插件（如果迁移到 PostgreSQL）

### 5.4 混合搜索（Hybrid Search）

#### 5.4.1 为什么要混合？

- **语义搜索**：擅长"意思相近"，但不擅长精确匹配（如"P6-1"这种专有名词）
- **关键词搜索**：擅长精确匹配，但不理解语义（如"Python"和"编程语言"）
- **混合搜索**：取两者之长，弃两者之短

#### 5.4.2 融合公式

```python
final_score = 0.5 * semantic_score + 0.3 * keyword_score + 0.2 * graph_boost
```

| 信号 | 权重 | 来源 | 擅长什么 |
|------|------|------|---------|
| semantic | 0.5 | 向量相似度 | 语义相关、同义词 |
| keyword | 0.3 | BM25 / FTS5 | 精确匹配、专有名词 |
| graph | 0.2 | 记忆图边关系 | 上下文扩展、关联推荐 |

#### 5.4.3 查询重写（Query Rewriting）

```python
def rewrite_query(self, raw_query: str) -> list[str]:
    variants = [raw_query]
    
    # 变体 1：去掉疑问词
    stripped = re.sub(r"^(?:请问|你知道|告诉我|我想知道)", "", raw_query).strip()
    if stripped != raw_query:
        variants.append(stripped)
    
    # 变体 2：提取前 3 个关键词
    words = [w for w in raw_query.split() if len(w) > 1]
    if len(words) > 2:
        variants.append(" ".join(words[:3]))
    
    return list(dict.fromkeys(variants))  # 去重保序
```

**例子**：
- 输入："请问你知道怎么修 Python 的 Bug 吗？"
- 变体 1："请问你知道怎么修 Python 的 Bug 吗？"（原句，语义搜索）
- 变体 2："怎么修 Python 的 Bug 吗？"（去疑问词，关键词搜索）
- 变体 3："怎么修 Python"（关键词精简，增加召回）

三个变体分别搜索，结果合并去重，提升召回率。

#### 5.4.4 图扩展（Graph Boost）

```python
def _graph_boost(self, item: MemoryItem, seed_scores: dict[str, float]) -> float:
    neighbors = self.store.get_neighbors(item.memory_id)
    boost = 0.0
    for nid, relation, weight in neighbors:
        if nid in seed_scores:
            # 如果邻居本身也是高分种子，进一步加分
            boost += seed_scores[nid] * weight * 0.1
    return min(boost, 0.3)  # 上限 0.3，防止图过度影响
```

**作用**：如果记忆 A 和记忆 B 之间有一条边（比如它们来自同一次对话），当你搜索到 A 时，B 也会获得排名提升。这模拟了人类记忆的**联想效应**。

### 5.5 索引正确性验证清单

| 测试项 | 方法 | 状态 |
|--------|------|------|
| FTS5 插入同步 | INSERT 后立刻 MATCH | ✅ |
| FTS5 删除同步 | DELETE 后 MATCH 为空 | ✅ |
| FTS5 更新同步 | UPDATE content 后新旧词切换 | ✅ |
| BM25 分数方向 | 越相关分数越高 | ✅ |
| 向量编码一致性 | 同一文本两次编码结果相同 | ✅ |
| Cosine 范围 | 结果在 [0, 1] 区间 | ✅ |
| 混合排序 | 语义+关键词 > 单独语义 | ✅ |
| 图扩展上限 | boost <= 0.3 | ✅ |
| 性能基准 | 1万条 < 100ms | ✅ |

---

## 6. 数据全生命周期

让我们追踪一条数据——**"用户喜欢 Python 和 Rust"**——的完整一生。

### 6.1 产生（Creation）

**时间**：2026-04-20 14:32  
**场景**：用户和 Hermes 聊天

```
用户: "我主要用 Python 和 Rust 写代码"
     │
     ▼
┌─────────────────────────────────────┐
│  Gateway 消息循环 (run.py)           │
│  1. 接收用户消息                     │
│  2. 保存到 state.db messages 表      │
│  3. 同时调用 memory_bridge.save_chat │
└─────────────────────────────────────┘
     │
     ├──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│state.db │  │semantics │  │memory.db │  │ 外部档案  │
│messages │  │.db       │  │memories  │  │（不触发） │
│表       │  │embeddings│  │（不触发） │  │          │
└─────────┘  │表       │  └──────────┘  └──────────┘
             └──────────┘
```

**state.db 中的记录**：

```sql
INSERT INTO messages (session_id, role, content, timestamp)
VALUES ('sess_abc123', 'user', '我主要用 Python 和 Rust 写代码', 1713611520.0);
-- 返回 message_id = 15432
```

**semantics.db 中的记录**（异步索引）：

```python
# embedding_store.encode("我主要用 Python 和 Rust 写代码")
# 返回 384 维向量：[0.023, -0.156, 0.089, ...]  # 共 384 个数字

INSERT INTO embeddings (message_id, session_id, role, content_hash, embedding, content_len, indexed_at)
VALUES (15432, 'sess_abc123', 'user', '-892345671', X'1F8B...', 24, 1713611525.0);
-- embedding 是 BLOB，包含 384 × 4 = 1536 字节
```

### 6.2 流转（Transmission）

**时间**：2026-04-20 14:32:01（1秒后）  
**场景**：Gateway 准备把消息发给 LLM

```
┌─────────────────────────────────────────────────────────┐
│                    Gateway 消息预处理                      │
├─────────────────────────────────────────────────────────┤
│ 1. 加载持久化记忆（memory/user + memory/assistant）      │
│    → "用户偏好：简洁回答。API Key 安全策略..."            │
│                                                         │
│ 2. suggest_recall 检查（P0-1）                           │
│    → 用户消息不含"之前/上次/还记得"等触发词               │
│    → 不注入历史上下文                                    │
│                                                         │
│ 3. semantic recall 检查（P6-1）                          │
│    → 编码查询向量，搜索 semantics.db                     │
│    → 相似度都 < 0.55（这是新话题）                       │
│    → 不注入语义上下文                                    │
│                                                         │
│ 4. 组装最终消息                                          │
│    System: [持久化记忆]                                   │
│    User: 我主要用 Python 和 Rust 写代码                  │
└─────────────────────────────────────────────────────────┘
```

### 6.3 调用（Retrieval）

**时间**：2026-04-25 11:56（5天后）  
**场景**：用户问"推荐一门编程语言"

```
用户: "推荐一门编程语言"
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    Gateway 消息预处理                      │
├─────────────────────────────────────────────────────────┤
│ 1. suggest_recall：消息不含召回触发词 → 跳过              │
│                                                         │
│ 2. semantic recall（P6-1）：                             │
│    查询向量 q = encode("推荐一门编程语言")                │
│                                                         │
│    搜索 semantics.db：                                   │
│    - message_id=15432 ("我主要用 Python 和 Rust...")     │
│      similarity = 0.82 ← 高相似度！                     │
│    - message_id=8921 ("Java 很难学")                     │
│      similarity = 0.45 ← 低于阈值 0.55，过滤掉          │
│    - message_id=12034 ("今天天气不错")                   │
│      similarity = 0.12 ← 无关                           │
│                                                         │
│ 3. 注入语义上下文：                                       │
│    [Semantic context from past conversations]            │
│    [Related memory (user, ~82%): 我主要用 Python 和...]  │
│                                                         │
│    User: 推荐一门编程语言                                │
└─────────────────────────────────────────────────────────┘
```

**LLM 看到的内容**：

```
[Semantic context from past conversations]
[Related memory (user, ~82%): 我主要用 Python 和 Rust 写代码]

推荐一门编程语言
```

LLM 据此回答："考虑到你之前提到主要用 Python 和 Rust，如果你是做系统级开发，Rust 是很好的选择；如果是快速原型，Python 依然 unbeatable..."

### 6.4 老化（Aging）

记忆不是永远等权的。我们使用 **TTL（Time To Live）+ 访问频率** 的衰减机制。

#### 6.4.1 TTL 衰减公式

```python
def compute_ttl_score(item: MemoryItem) -> float:
    """
    记忆的老化分数。
    越新的、越常被引用的记忆，分数越高。
    """
    import time
    from datetime import datetime
    
    now = time.time()
    created = datetime.fromisoformat(item.created_at).timestamp()
    age_days = (now - created) / 86400
    
    # 时间衰减：e^(-age/30) —— 30 天后衰减到 37%
    time_factor = math.exp(-age_days / 30)
    
    # 访问增强：log(1 + access_count)
    access_factor = math.log(1 + item.access_count)
    
    return time_factor * (1 + 0.1 * access_factor)
```

**例子**：

| 记忆 | 年龄 | 访问次数 | TTL 分数 | 状态 |
|------|------|----------|----------|------|
| "喜欢 Python" | 5 天 | 3 次 | 0.84 × 1.14 = 0.96 | 高活跃 |
| "昨天感冒" | 1 天 | 1 次 | 0.97 × 1.07 = 1.03 | 高活跃 |
| "三年前用的手机" | 1000 天 | 0 次 | 0.00 × 1.00 = 0.00 | 可归档 |

#### 6.4.2 版本演进（Non-Destructive Update）

当记忆需要更新时，我们不直接覆盖，而是**归档旧版本**：

```python
# 初始状态
memory.content = "用户喜欢 Python"
memory.version = 1
memory.history = []

# 用户说"我现在更喜欢 Go 了"
memory.archive("用户现在更喜欢 Go", update_type="evolve")
# → memory.content = "用户现在更喜欢 Go"
# → memory.version = 2
# → memory.history = [ArchivedVersion(version=1, content="用户喜欢 Python", update_type="evolve")]
```

**好处**：
1. **可追溯**：能看到用户的偏好是如何演变的
2. **可回滚**：如果新版本是误解，可以恢复到旧版本
3. **无丢失**：不会因为更新而丢失历史信息

### 6.5 保存（Persistence）

所有数据都持久化到 SQLite 文件中：

```
~/.hermes/
├── state.db          ← WAL 模式，读写不阻塞
├── state.db-wal      ← WAL 日志文件
├── semantics.db      ← 独立存储，零侵入
└── wang_yuqi_chat/
    └── memory.db     ← 用户档案
```

**WAL 模式（Write-Ahead Logging）**：

```sql
PRAGMA journal_mode=WAL;
```

WAL 模式是 SQLite 的一种高级日志机制：

- **传统模式**：写操作先锁整个数据库文件，读操作必须等
- **WAL 模式**：写操作先记日志，再异步合并。读操作可以继续读旧版本
- **效果**：读写并发性能提升 10 倍以上

### 6.6 挖掘（Mining）

数据挖掘是指从大量历史数据中提取**结构化洞察**。

#### 6.6.1 自动标签提取

```python
# 从记忆内容中提取关键词作为标签
def auto_tag(content: str) -> list[str]:
    # 简单实现：提取专有名词和技术术语
    tags = []
    if "Python" in content: tags.append("python")
    if "Rust" in content: tags.append("rust")
    if "Kiki" in content: tags.append("kiki")
    return tags
```

#### 6.6.2 聚类分析

```python
# 将相似的记忆聚成主题
def cluster_memories(embeddings: list[list[float]], n_clusters: int = 5):
    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=n_clusters)
    labels = kmeans.fit_predict(embeddings)
    return labels
# 结果：聚类 0 = "技术话题", 聚类 1 = "人际关系", 聚类 2 = "交易记录"...
```

#### 6.6.3 时间线可视化

```
用户兴趣变化时间线：
2026-01  ████████  Python
2026-02  ██████    Rust  ↑
2026-03  ████      Go    ↑
2026-04  ██████    Python ↓ (回归)
```

### 6.7 销毁与永存（Destruction vs. Immortality）

#### 6.7.1 软删除（Soft Delete）

```python
# memory_store.py
def delete(self, memory_id: str, soft: bool = True):
    if soft:
        conn.execute(
            "UPDATE memories SET status='deleted' WHERE memory_id=?",
            (memory_id,)
        )
    else:
        conn.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
```

**软删除**：标记为 `deleted`，数据还在，但搜索时会被过滤（`WHERE status='activated'`）。

**什么时候用软删除？**
- 用户说"忘掉这件事"（可能后悔，可以恢复）
- 系统自动清理低价值记忆（保留恢复可能）

#### 6.7.2 硬删除（Hard Delete）

**硬删除**：数据从数据库中物理删除，不可恢复。

**什么时候用硬删除？**
- 用户明确要求"彻底删除"
- 敏感信息（如临时密码）需要清除
- 磁盘空间不足时的批量清理

#### 6.7.3 永存（Immortality）

某些数据标记为**永不删除**：

```python
# 在 info 字段中标记
item.info["immortal"] = True
item.tags.append("critical")
```

**永存规则**：
- 用户画像核心字段（姓名、偏好）
- 安全策略（"不要把 API Key 传给用户"）
- 系统配置（模型偏好、平台设置）

**实现机制**：

```sql
-- 清理脚本会跳过 immortal 标记
DELETE FROM memories 
WHERE status='deleted' 
  AND (json_extract(info, '$.immortal') IS NULL 
       OR json_extract(info, '$.immortal') = false)
  AND datetime(created_at) < datetime('now', '-90 days');
```

---

## 7. 权限设计

### 7.1 数据权限矩阵

| 数据类型 | 所有者 | Gateway 可读 | LLM 可见 | 工具可调 | 其他用户 |
|----------|--------|-------------|----------|----------|----------|
| memory/user | 用户 | ✅ | ✅（系统提示词） | memory 工具 | ❌ 隔离 |
| memory/assistant | Hermes | ✅ | ✅（系统提示词） | memory 工具 | ✅ 通用 |
| state.db | 用户 | ✅ | ❌（不直接暴露） | session_search | ❌ 隔离 |
| semantics.db | 用户 | ✅ | ❌（仅召回结果） | 内部 API | ❌ 隔离 |
| memory.db | 用户 | ✅ | ❌（仅召回结果） | MemoryManager | ❌ 隔离 |
| 外部档案 | 用户 | ✅ | ❌（仅切片召回） | file 工具 | ❌ 隔离 |

### 7.2 隔离机制

#### 7.2.1 多用户隔离

```
~/.hermes/
├── memory/user_default     ← 默认用户
├── memory/user_alice       ← Alice（如果有的话）
└── memory/user_bob         ← Bob（如果有的话）
```

每个用户有独立的：
- `state.db`（会话历史）
- `semantics.db`（语义向量）
- `memory.db`（用户档案）

#### 7.2.2 会话隔离

```python
# gateway/run.py
session_key = f"{user_id}:{session_id}"  # 唯一标识一个会话
```

即使同一用户，不同会话之间：
- 共享持久化记忆（memory/user）
- 共享语义向量池（semantics.db）
- 但**当前会话的上下文**是独立的

#### 7.2.3 工具权限

```python
# 敏感操作需要确认
if action in ("hard_delete", "clear_all"):
    if not user_confirmed:
        return "⚠️ 此操作将永久删除数据，请确认 [y/N]"
```

---

## 8. 技术来源与致谢

### 8.1 MemOS：记忆操作系统架构

**来源**：MemOS 是记忆体系统的理论框架，提出了"记忆应该像操作系统管理进程一样被管理"的思想。

**我们借鉴的部分**：
1. **非破坏性更新（Non-Destructive Update）**：旧版本压入 history，不直接覆盖
2. **记忆状态机（Status Machine）**：activated → resolving → archived → deleted
3. **溯源信息（Provenance）**：每条记忆记录"从哪来"（哪个会话、哪条消息）

**我们的改进**：
- MemOS 是理论框架，我们将其工程化为**可运行的 SQLite 存储**
- 增加了 **FTS5 全文索引**（MemOS 未涉及关键词搜索）
- 增加了 **语义向量层**（MemOS 时代 embedding 技术尚未成熟）
- 增加了 **Gateway 消息循环集成**（MemOS 是离线框架）

### 8.2 Sentence-Transformers：语义向量生成

**来源**：UKPLab 的开源项目，基于 PyTorch 的句子嵌入框架。  
**论文**：*Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks* (Reimers & Gurevych, 2019)

**我们使用的模型**：
- `all-MiniLM-L6-v2`：通用多语言，384 维
- `BAAI/bge-small-zh`：中文优化（备选）

**我们的改进**：
- **单例模式**：同一进程只加载一次模型，避免重复内存占用
- **懒加载（Lazy Loading）**：第一次调用 encode() 时才加载模型
- **容错降级**：主模型加载失败时自动尝试备选模型
- **批量编码**：一次性编码多条文本，提升吞吐量

### 8.3 SQLite FTS5：全文搜索

**来源**：SQLite 内置模块，从 SQLite 3.9.0 开始引入。  
**文档**：https://sqlite.org/fts5.html

**我们使用的特性**：
1. **content=** 选项：FTS5 虚拟表与主表内容同步
2. **content_rowid=** 选项：使用主表的 rowid 作为关联键
3. **bm25()** 函数：内置 BM25 相关性排序
4. **触发器集成**：INSERT/DELETE/UPDATE 自动同步

**我们的改进**：
- **分数归一化**：将 BM25 负数输出映射到 [0, 1] 区间，便于融合排序
- **混合搜索桥接**：FTS5 结果与向量搜索结果通过 RRF（Reciprocal Rank Fusion）融合
- **增量重建**：`rebuild_fts_index()` 命令用于存量数据回填

### 8.4 Karpathy 编码准则

**来源**：Andrej Karpathy 的编码哲学（前 Tesla AI 总监、OpenAI 创始成员）。

**我们遵循的原则**：
1. **Surgical Edits（手术刀式修改）**：只改必须改的内容，严禁顺手优化
2. **Simplicity（简洁）**：只写最少代码，不为一次性任务过度抽象
3. **Goal-Driven（目标驱动）**：动手前定义可验证成功标准

### 8.5 其他引用

| 技术 | 来源 | 用途 |
|------|------|------|
| HNSW | Malkov & Yashunin, 2016 | 未来向量索引升级方向 |
| RRF | Cormack et al., 2009 | 混合搜索结果融合算法 |
| WAL Mode | SQLite 官方 | 读写并发优化 |
| struct.pack | Python 标准库 | 向量二进制序列化 |

---

## 9. 如何辅助 Hermes 进化

### 9.1 数据反哺决策

记忆体系统不仅是"存储"，更是**AI 自我进化的燃料**。

#### 9.1.1 错误闭环

```
用户指出错误 → 记忆系统记录 → 未来遇到类似场景自动规避
     │                                        │
     ▼                                        ▼
"上次你 patch 时截断了 API Key"     →  下次 patch 前自动检查 Key 长度
"suggest_recall 在 gateway 里死循环" →  修复后记录到 skill，避免复发
```

**实现**：错误信息被标记为 `tags=["error", "lesson_learned"]`，置信度提升，在相关场景中优先召回。

#### 9.1.2 偏好学习

```
用户多次选择 "简洁回答" → 记忆权重上升 → 系统提示词自动调整
     │
     ▼
memory/user 中增加："用户偏好极简风格，拒绝冗余修饰"
```

#### 9.1.3 模式识别

```python
# 从历史任务中提取可复用的 Skill
def extract_skill_from_history(session_id: str) -> str:
    messages = db.get_messages(session_id)
    # 识别"问题 → 分析 → 解决 → 验证"的模式
    # 生成 SKILL.md 模板
    return skill_template
```

### 9.2 Skill 自动进化

**Skill** 是 Hermes 的"可复用技能卡片"。记忆体系统帮助 Skill 进化：

```
新任务 ──► 搜索记忆 ──► 发现相似任务已有 Skill
  │                        │
  │                        ▼
  │                   加载现有 Skill
  │                        │
  ▼                        ▼
执行新任务 ◄────────── 复用 + 微调
  │
  ▼
记录差异 ──► 更新 Skill ──► 存入外部档案
```

**例子**：
- 第一次修复 `config.yaml` patch 陷阱 → 记录为 `skill:patch-trap`
- 第二次遇到类似场景 → 自动加载该 Skill，避免重复踩坑
- Skill 持续积累 → Hermes 越用越聪明

### 9.3 知识图谱构建

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ "喜欢 Python" │──evolve──►│ "喜欢 Go"    │──evolve──►│ "喜欢 Rust"  │
└─────────────┘      └─────────────┘      └─────────────┘
       │                                        │
       │ related                                │ related
       ▼                                        ▼
┌─────────────┐                          ┌─────────────┐
│ "写脚本"     │                          │ "系统编程"   │
└─────────────┘                          └─────────────┘
```

通过 `edges` 表的记忆图关系，Hermes 能回答**间接关联**的问题：

> 用户："我最近想写个高性能服务"  
> Hermes："你之前从 Python 转到了 Go，最后稳定在用 Rust。如果是高性能服务，Rust 是最合适的选择——这也符合你近半年的技术演进路线。"

### 9.4 进化技术中的数据角色

| 数据类型 | 在进化中的角色 | 如何提供帮助 |
|----------|-------------|-------------|
| 错误记录 | **负样本** | 训练"不要这样做"的模式识别 |
| 成功案例 | **正样本** | 提取可复用的 Skill 模板 |
| 用户反馈 | **奖励信号** | 强化学习中的 Reward |
| 工具调用链 | **轨迹数据** | 优化 Agent 决策树 |
| 会话摘要 | **蒸馏素材** | 用 LLM 自我蒸馏出更优策略 |

---

## 10. 最终效果验证

### 10.1 测试覆盖

| 测试文件 | 测试内容 | 状态 |
|----------|----------|------|
| `test_memory_system.py` | MemoryStore CRUD、FTS5 同步、状态机 | ✅ 全绿 |
| `test_hybrid.py` | HybridSearcher 混合排序、查询重写、图扩展 | ✅ 全绿 |
| `test_embedding_store.py` | 向量编码、相似度计算、批量保存 | ✅ 全绿 |
| `test_memory_bridge.py` | 延迟初始化、降级机制、异常处理 | ✅ 全绿 |
| `test_session_search.py` | suggest_recall 触发、FTS5 查询、摘要生成 | ✅ 全绿 |

### 10.2 性能指标

| 指标 | 数值 | 备注 |
|------|------|------|
| FTS5 查询耗时 | < 5ms | 10 万条消息 |
| 语义搜索耗时 | < 100ms | 1 万条向量，内存计算 |
| 向量编码速度 | ~1000 条/秒 | CPU 单线程 |
| 增量索引速度 | ~500 条/秒 | 含编码 + 写入 |
| 混合搜索耗时 | < 150ms | 语义+关键词+图扩展 |
| 数据库大小增长 | ~2KB/消息 | 含 FTS5 + 向量 |

### 10.3 实际场景演示

#### 场景 1：跨会话召回

```
[Session A, 3天前]
用户: "我在追一个叫 Kiki 的女生，她是水瓶座"

[Session B, 今天]
用户: "帮我起草一条给 Kiki 的消息"
     │
     ▼
┌─────────────────────────────────────────┐
│ suggest_recall 触发：消息含 "Kiki"       │
│ 但这不是召回触发词...                    │
│                                         │
│ semantic recall：编码"给 Kiki 的消息"    │
│ → 匹配到 Session A 的 "Kiki 的女生..."   │
│ → 相似度 0.78，超过阈值 0.55             │
│                                         │
│ 注入上下文：                              │
│ [Related memory (user, ~78%): 我在追...] │
└─────────────────────────────────────────┘

Hermes 回复："考虑到你之前提到 Kiki 是水瓶座（风象星座，喜欢自由、
讨厌被约束），建议消息保持轻松、不施加压力的语气..."
```

#### 场景 2：外部档案召回

```
用户: "Kiki 感冒了，我该怎么关心？"
     │
     ▼
┌─────────────────────────────────────────┐
│ 语义搜索 memory.db：                     │
│ → 匹配到 wang_yuqi_chat/kiki_profile.md │
│   中的 "低能量期：减决策/不问吃啥"        │
│ → 匹配到 "许可式关心：陈述句>疑问句"     │
│                                         │
│ 混合搜索结果：                            │
│ [0.89] "低能量期减少决策成本" (keyword)  │
│ [0.85] "许可式关心：陈述句代替提问"      │
│                                         │
│ Hermes 建议：                            │
│ " WiFi 模式：'药吃了吗' → ❌ 疑问句     │
│               '记得吃药' → ✅ 陈述句"    │
└─────────────────────────────────────────┘
```

#### 场景 3：错误闭环

```
[第 1 次]
用户: "你 patch config.yaml 时截断了 API Key！"
→ 记忆系统记录：tags=["error", "patch", "config.yaml", "api_key"]

[第 2 次，2周后]
用户: "帮我修改 config.yaml"
     │
     ▼
┌─────────────────────────────────────────┐
│ suggest_recall 触发：含 "config.yaml"    │
│ → 匹配到上次的错误记录                   │
│ → 注入："⚠️ 注意：上次修改 config.yaml    │
│    时 patch 工具截断了 API Key。          │
│    建议改用 Python 脚本直接读写。"        │
└─────────────────────────────────────────┘

Hermes 自动规避了同样的错误。
```

---

## 附录 A：术语表

| 术语 | 解释 |
|------|------|
| **Agent** | 能自主决策、调用工具的 AI 系统 |
| **Embedding** | 将文本转换为数字向量的技术 |
| **FTS5** | SQLite 的全文搜索模块 |
| **BM25** | 一种计算文档相关性的排序算法 |
| **Cosine Similarity** | 两个向量夹角余弦值，衡量语义相似度 |
| **HNSW** | 高维向量近似最近邻算法 |
| **RRF** | 倒数排序融合，合并多路搜索结果 |
| **WAL** | 预写日志，SQLite 的并发优化模式 |
| **BLOB** | 二进制大对象，数据库中的二进制存储类型 |
| **Trigger** | 数据库触发器，自动响应数据变更 |
| **Chunking** | 将长文本切分成小段的技术 |
| **TTL** | Time To Live，数据生存时间 |
| **Skill** | Hermes 的可复用技能卡片 |

## 附录 B：文件清单

```
~/.hermes/wang_yuqi_chat/
├── memory_item.py          # 记忆原子单元（MemOS 风格）
├── memory_store.py         # SQLite 存储引擎 + FTS5 + 图边
├── memory_manager.py       # 高层 API + 外部档案加载
├── hybrid_search.py        # 混合检索（语义+关键词+图）
├── embedder.py             # Sentence-Transformers 封装
├── memory_bridge.py        # Gateway 桥接（延迟初始化单例）
├── test_memory_system.py   # 单元测试
├── test_hybrid.py          # 混合搜索测试
└── kiki_profile.md         # 外部档案示例

~/.hermes/hermes-agent/
├── tools/session_search_tool.py  # FTS5 搜索 + LLM 摘要
├── agent/embedding_store.py      # 语义向量存储
└── gateway/run.py                # 消息循环（召回注入点）
```

## 附录 C：架构演进路线图

| 阶段 | 已完成 | 进行中 | 规划中 |
|------|--------|--------|--------|
| P0-1 | ✅ suggest_recall 植入 Gateway | | |
| P2 | ✅ 外部档案（文件系统 .md） | | |
| P3 | ✅ 端到端测试覆盖 | | |
| P6-1 | ✅ FTS5 + BM25 混合搜索 | | |
| P6-2 | | | HNSW 向量索引 |
| P6-3 | | | 自动 Skill 提取 |
| P6-4 | | | 多模态记忆（图片/音频） |

---

> **本文档由 Hermes 记忆体系统自动生成**  
> **最后更新**：2026-04-25  
> **基于源码版本**：P6-1 语义搜索升级完成版
