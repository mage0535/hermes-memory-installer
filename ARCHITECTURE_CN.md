# Memory Sidecar 架构文档 v3.1.1

AI 智能体的生产级记忆栈。三层架构，无 Docker 依赖，与智能体无关。

## 设计原则

1. **无损持久化。** 智能体会话是唯一真理源。Sidecar 索引和归档它们，但从不删除原始数据。
2. **分层召回。** 检索不是一次数据库查询。热层、温层、冷层通过 Reciprocal Rank Fusion（RRF）融合排序。
3. **重点记忆。** 重要的人、项目和事件获得专属档案，而不是埋在会话碎片中。
4. **运维可见性。** 积压大小、同步延迟、重复摄入和重建健康状态都可见，而非隐藏。
5. **智能体无关。** 兼容 Hermes、Claude Code、Cursor、Codex —— 任何将会话写入数据目录的智能体。

## v3.1.0 变更内容

v3.0 有 4 层架构，包含一个 `agentmemory` Docker 桥接层位于 Hindsight 和 gbrain 之间。实际上那层桥接只存了 13 条过期数据，平白增加了 Docker 依赖。v3.1.0 将其完全移除，并新增 session_search FTS5 作为并行冷路径。

**已移除：**
- agentmemory MCP（Docker 容器，51 个工具，13 条记录）
- memory_index.db（半成品治理层，100 条 misc 条目）
- Docker 作为 sidecar 运行时依赖

**已新增：**
- session_search FTS5 —— PostgreSQL 全文搜索，覆盖 105K 条消息
- gbrain MCP 桥接 —— session_to_gbrain.py 改用 HTTP API 直接调用 gbrain，替代脆弱的 CLI
- consolidated_system.py auto_repair —— 所有记忆服务的健康检查
- OneDrive 知识库同步管道
- book_cache 系统 —— 大型参考书库管理

## 三层架构

```
┌──────────────────────────────────────────────────┐
│                    智能体                          │
│  写入会话 → state.db + 会话文件                    │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│              SIDECAR（本项目）                     │
│                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  热层     │  │    温层      │  │    冷层     │ │
│  │ memory   │  │  Hindsight   │  │  gbrain     │ │
│  │ tool     │──│  PostgreSQL  │──│  + FTS5     │ │
│  │ 5KB 限制 │  │  ~50ms       │  │  ~500ms     │ │
│  └──────────┘  └──────────────┘  └─────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │        tiered_context_injector.py            │ │
│  │   RRF 融合 → 意图路由 → 上下文注入          │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 热层 —— memory tool

位于智能体的系统提示词中。保存用户身份、关键偏好和活跃上下文。默认上限 5KB。`compact_memory.py` 脚本在容量将满时处理裁剪和去重。

**存放内容：**
- 用户身份
- 当前项目状态
- 反复出现的纠正（防止智能体重复犯错）
- 关键配置（提供商链路、认证偏好）

### 温层 —— Hindsight

基于 PostgreSQL 的事实图谱。Hindsight 自动从每个会话中保留关键事实，在查询时自动召回相关上下文，并每周运行反思周期来综合模式。

**生产数据（来自线上 Hermes 实例）：**
- 21,629 条提取的记忆
- 20,543 条观察
- 309 条语义缓存条目
- 42,481 个总节点

健康检查 API 端点：
- `GET /health` → `{"status":"healthy","database":"connected"}`
- `GET /v1/default/banks/hermes/stats` → 库统计信息（库名因部署而异，`hermes` 是默认值）
- `GET /metrics` → Prometheus 格式指标

### 冷层 —— gbrain + session_search

两条并行的长期检索路径：

**gbrain 知识图谱**（10,885 页面，脑分 73）：
- 通过 pgvector 进行向量搜索（384 维，来自 multilingual-e5-small）
- 通过 FTS 进行关键词搜索
- 通过 wikilinks 和类型边进行图谱遍历
- 时间线条目用于时序查询
- 基于标签的过滤

**session_search FTS5**（105,601 条消息，6,374 个会话）：
- 所有历史消息的全文搜索
- 会话级范围限定和谱系追踪
- 支持中文搜索（三元组索引）

## 核心脚本

### session_to_gbrain.py

归档主力。从 `$AGENT_HOME/sessions/` 读取智能体会话，处理未归档的，并将结构化页面写入 gbrain。

v3.1.0 升级：改用 **MCP API 直连桥接** 替代 gbrain CLI。原 CLI 脆弱——路径依赖、偶发崩溃、难调试。MCP 桥接通过 Bearer 认证调用 gbrain 的 HTTP 端点 `localhost:8787`，不依赖 CLI 状态。

会话处理流程：
1. 加载检查点（已处理哪些会话）
2. 扫描新的会话文件
3. 对每个未处理会话：
   - 提取关键决策、学习和上下文
   - 创建带 frontmatter 的 gbrain 页面（标签、日期、摘要）
   - 链接到相关主题中枢
   - 为重要事件添加时间线条目
4. 保存更新后的检查点

生产环境每 6 小时运行一次：`*/30 */6 * * *`

### memory_governance_rebuild.py

索引器。重建以下内容：
- 会话索引（state.db 上的 FTS5）
- Hindsight 索引（预缓存的召回结果）
- 记忆中枢（主题聚合器）
- 规范记忆对象，含多版本状态（active/superseded）和时间有效性（valid_from/valid_to）
- 冲突组（去重集群）
- 档案元数据
- 召回指标
- 向量嵌入（配置 EMBEDDING_API_URL 时启用）

维护的基础设施表：
- `orphan_messages` —— 未归属消息审计表
- `session_repair_map` —— 消息→会话修复映射
- `session_lineage_repair` —— 会话父链修复
- `recovered_fragments` —— 无法归类的记忆碎片
- `memory_aliases` / `memory_relations` —— 别名和关系图
- `sessions_effective` —— 修复后的会话视图

### memory_guardian.py

容量和健康看门狗。追踪：
- 热层内存填充率（5KB 上限仪表盘）
- 重复检测（同一事实以多种方式存储）
- 积压趋势（处理是否滞后）
- 卡住操作（未进展的任务）
- 同步延迟（Hindsight 合并队列深度）

提供积压和卡住操作的安全排空路径。

### memory_family_registry.py

意图分类器 + 档案路由器。将查询文本映射到检索族：

- **提供商/系统** → 配置优先，治理对象
- **项目** → 交付优先，规范项目对象
- **关系/档案** → 档案优先，实时 Hindsight + 时间线感知
- **探索型** → 更宽的治理证据，有限的回退

包含活跃的 Focused Dossier 注册表。通过编辑 `active_focus_profiles()` 字典添加新档案。

### tiered_context_injector.py

召回引擎。三路并行检索 + RRF 融合：

```
查询到达
    ↓
┌───┼───────────────────────────────┐
│   │                               │
▼   ▼                               ▼
L1  L2                              L3
热  温                               冷
    (Hindsight)                     (gbrain + FTS5)
    │                               │
    └───────────────┬───────────────┘
                    ↓
            RRF 融合 (k=60)
                    ↓
            意图重排序
                    ↓
            注入智能体上下文
```

支持领域路由，防止某个主题占据全部记忆：

| 领域 | 配额 | 用途 |
|--------|-------|---------|
| user-profile | 500 | 用户画像分析 |
| stock | 400 | A股策略 |
| system | 300 | 系统配置 |
| promo | 200 | 渠道推广 |
| misc | 200 | 其他 |

### memory_maintenance_cycle.py

编排器，串联完整的维护管道：
1. 会话归档摄入（session_to_gbrain.py）
2. 治理重建（memory_governance_rebuild.py）
3. 积压排空（memory_guardian.py）
4. 分层召回生成（tiered_context_injector.py）
5. 健康快照（memory_guardian.py --status）

### sidecar_acceptance_check.py

生产验证套件。运行关键回归查询并检查所有层返回预期结果。

## Focused Dossier（重点档案）模型

当一个人、项目或主题重要到需要系统跟踪时，它就成为一个 Focused Dossier。

`memory_family_registry.py` 中的档案条目示例：

```python
"user-profile": {
    "slug": "hub-user-profile",
    "title": "用户画像档案",
    "tags": ["user-profile", "profile"],
    "keywords": ["user", "profile", "preferences"],
    "aliases": ["用户"],
    "retention_priority": "high",
    "enable_timeline": True,
}
```

当查询匹配档案关键词时，召回引擎：
1. 首先从 gbrain 拉取档案中枢页面
2. 加载最近的时间线条目
3. 使用档案范围过滤器搜索 Hindsight
4. 将档案证据排在一般治理结果之上

## Embedding 基础设施

语义搜索是可选的，但强烈推荐。Sidecar 使用 sentence-transformers 模型作为本地 HTTP API 服务。

**生产部署（线上 Hermes 实例）：**
- 模型：`intfloat/multilingual-e5-small`（384 维）
- 服务：systemd 管理，端口 8766
- 健康检查：`GET /health` → `{"ok": true, "service": "gbrain-embed"}`
- 消费方：gbrain 分块嵌入 + governance rebuild 向量索引

不部署 embedding 服务也能正常使用——所有基于文本的检索路径（FTS5、LIKE、Hindsight、gbrain 关键词）继续工作。

## 维护调度（生产）

来自一个自 2026 年 4 月起运行的线上 Hermes 实例：

| 任务 | 调度 | 用途 |
|-----|----------|---------|
| session_to_gbrain | 每 6 小时 | 增量会话归档 |
| auto_session_summary | 每 6 小时 | 会话摘要生成 |
| archive_sessions | 每日 02:00 | 批量会话归档 |
| consolidated_system | 每小时 :00/:30 | 服务健康 + 自动修复 |
| Hindsight reflect | 每周日 05:30 | 从累积事实中综合模式 |
| memory maintenance cycle | 手动 / 按需 | 需要时完全重建 |

## 数据流（端到端）

```
1. 智能体对话发生
   └→ state.db 更新 + 会话 JSON 写入

2. session_to_gbrain.py 获取新会话
   └→ 创建带标签、时间线、中枢链接的 gbrain 页面

3. memory_governance_rebuild.py 索引所有内容
   └→ 会话索引、hindsight 索引、中枢、规范对象

4. memory_guardian.py 检查健康
   └→ 积压趋势、容量、卡住操作

5. 下次智能体对话开始
   └→ tiered_context_injector.py 组装上下文
      热（memory tool）→ 温（Hindsight）→ 冷（gbrain + FTS5）
      RRF 融合 → 注入智能体提示词
```

## 运维健康信号

当 sidecar 健康时：
- gbrain 页面创建及时（无可处理的会话积压）
- Hindsight 合并队列稳定排空
- memory tool 保持在 80% 容量以下
- 嵌入覆盖率接近 100%
- session_search FTS5 索引最新

当出现问题时：
- `memory_guardian.py --status` 显示积压增长
- gbrain 健康端点显示缺失嵌入
- tiered_context_injector.py 返回结果少于预期
- sidecar_acceptance_check.py 回归查询失败

## 架构边界

Sidecar 的职责止于智能体的数据目录。它从 `$AGENT_HOME/state.db` 和 `$AGENT_HOME/sessions/` 读取，将索引/归档写入自己的存储（gbrain、Hindsight）。从不修改智能体源代码。

这个边界是 sidecar 能跨智能体版本升级存活的原因。当 Hermes 或 Claude Code 发布新版本时，sidecar 继续工作——它只依赖稳定的数据格式（SQLite + JSON 文件），而非智能体内核。

---

要查看概览和安装说明，请参阅 [README](README_CN.md)。英文架构文档见 [ARCHITECTURE.md](ARCHITECTURE.md)。
