<div align="center">

# 🧠 Hermes Memory Installer

**为 Hermes AI Agent 注入持久化长期记忆 — 由 gbrain 知识图谱驱动**

[![Version](https://img.shields.io/badge/version-2.2.0-blue)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v2.2.0)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)]()
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)]()

[English](README.md) | [中文版](README_CN.md)

零依赖记忆体系统，为 Hermes Agent 增加持久化、可检索、生命周期管理的长期记忆能力。60 秒内完成安装。

</div>

---

## 目录

- [为什么需要这个项目](#为什么需要这个项目)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [架构详解](#架构详解)
  - [数据写入流程](#数据写入流程)
  - [数据读取流程](#数据读取流程)
  - [维护管道（Cron）](#维护管道cron)
  - [组件全景图](#组件全景图)
- [脚本参考手册](#脚本参考手册)
  - [核心管道脚本](#核心管道脚本)
  - [守卫与验证脚本](#守卫与验证脚本)
  - [工具脚本](#工具脚本)
- [配置指南](#配置指南)
  - [记忆体生命周期保护配置](#记忆体生命周期保护配置)
  - [领域配额配置](#领域配额配置)
  - [Tiered Context 参数调优](#tiered-context-参数调优)
- [Cron 任务策略](#cron-任务策略)
- [增量同步架构详解](#增量同步架构详解)
- [数据安全与隐私](#数据安全与隐私)
- [版本历史](#版本历史)
- [致谢](#致谢)
- [License](#license)

---

## 为什么需要这个项目

Hermes Agent 内置的 `memory()` 工具适合短期记忆，但在长期使用中暴露出几个根本性短板：

### 1. 无生命周期管理
```
记忆体   [今天刚存的]     [90天前的]     [150天前的]
槽位     ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░
         ↑ 新条目和旧条目              ↑ 永远占着位置
           平等竞争有限槽位            不会自动释放
```
每条记忆一旦写入就永久占据槽位。旧知识不会自动降级，新知识没有优先权。结果是：Agent 的上下文里同时塞着"今天股票分析结论"和"三个月前的过期规则"，而且无法区分优先级。

### 2. 无分层检索
每次新会话从零开始 —— 没有之前对话的上下文累积。即使是最相关的历史信息，也需要 Agent 从当前 `memory()` 的快照中碰运气式地找到。没有"最近优先"、"相关度排序"或"多数据源融合"机制。

### 3. 无领域隔离
```
当前 flat memory:
  "Kiki 今天心情不好"      ← 关系记录
  "沪深300推荐用5因子模型"  ← 股票配置
  "抖音矩阵已注册24个渠道"  ← 推广运营
  "auxiliary必须跟随主模型"  ← 系统配置
  → 全部混在一起，没有分类，没有配额
```
股票分析配置和关系状态混在同一个扁平命名空间里。一个领域可以撑爆所有槽位，另一个领域则完全没空间。

### 4. 无反馈循环
Agent 无法标记"这条信息有用"或"这条已经过时"。每次调用 `memory()` 返回的内容都是一视同仁的——没有学习，没有进化。

### 本项目解决的问题

这个安装包在 Hermes Agent 原生 `memory()` 工具之上构建了一套完整的记忆管道：

- **分层上下文注入**：从三个独立数据源构建会话上下文（最近会话 + FTS5 全文检索 + 知识图谱），用 RRF 融合排序
- **生命周期状态机**：跟踪知识新鲜度，自动归档过时内容，保护关键页面
- **领域隔离**：5 个独立领域配额，防止单一话题挤占所有槽位
- **写入前守卫**：写入前检测矛盾、检查容量，避免静默失败
- **会话→知识图谱管道**：将一次性对话转化为持久的知识图谱节点

全部 ~1,400 行 Python，零第三方依赖。

---

## 功能特性

### 🧠 三层上下文注入 v3（RRF 融合）

当 Agent 启动新会话时，注入器从三个层构建复合上下文：

| 层级 | 数据源 | 衰减策略 | 权重策略 |
|------|--------|---------|---------|
| **L1** | 最近 N 个会话摘要（SQLite `messages_fts`） | 无衰减 | 始终包含 |
| **L2** | FTS5 全文搜索（60K+ 历史消息） | **30 天半衰期** `0.5^(days/30)` | RRF 与 L3 融合 |
| **L3** | gbrain 知识图谱 MCP 查询 | 自然衰减取决于图谱更新 | RRF 与 L2 融合 |

**关键设计决策：L2 和 L3 并行运行，不是兜底关系。**

```
传统的 cascade 方式:
  先查 FTS5 → 结果不足时再查 gbrain
  → gbrain 永远是第二选择，即使它有更相关的信息

RRF 融合方式 (本项目):
  FTS5 和 gbrain 同时查询
  → Reciprocal Rank Fusion (k=60) 合并两个结果集
  → 同时出现在两个源中的条目获得显著排名提升
  → 信息量最大的内容排在最前面 ✅
```

**RRF 公式说明：**

对于每个条目 e，其融合分数为：
```
score(e) = Σ [ 1 / (k + rank_i(e)) ]
  其中 i = 每个数据源的排名
  k = 融合常数（默认 60）
```

- k 值越小，排名越靠前的条目权重越大
- k 值越大，排名分布越均匀
- 默认 k=60 在实践测试中取得了最好的平衡

### 🔄 记忆体生命周期状态机

每个 gbrain page 遵循四态生命周期，由 `memory_lifecycle.py` 管理：

```
                    ┌─────────────────┐
                    │   state:active   │
                    │   (正常状态)     │
                    └────────┬─────────┘
                             │
               90 天未更新 ──┤
                             ▼
                    ┌─────────────────┐
                    │   state:stale    │
                    │   (90天未更新)   │
                    └────────┬─────────┘
                    ┌────────┴────────┐
                    │                 │
         手动更新 ──┤   180天未更新 ──┤
                    │                 │
                    ▼                 ▼
          ┌──────────────┐  ┌──────────────┐
          │  state:active │  │ state:       │
          │  (恢复正常)   │  │  archived    │
          └──────────────┘  │  (从搜索隐藏) │
                            └──────────────┘

  可选: 显式标记为 superseded → 跳过时间检查直接进入归档候选
```

**保护机制**：通过在 YAML 配置文件中定义白名单来保护关键页面：
- 匹配 `protected_slugs` 的页面不会进入 stale/archived 状态
- 匹配 `protected_tags` 标签的页面也受保护
- 配置文件不存在时默认**关闭**保护（不保护任何页面）
- 仓库代码中**不包含任何**内部页面名

### 🚧 写入前守卫

在写入新的 memory 条目之前，两道守卫逐一检查：

#### 第一道：容量守卫 (`memory_guard.py`)

| 剩余容量 | 行为 |
|----------|------|
| > 20% | 正常写入 |
| 15% ~ 20% | 写入并触发 compaction 预警 |
| < 15% | 阻止写入，返回明确错误 |

#### 第二道：矛盾检测 (`memory_prewrite_guard.py`)

基于正则匹配（零 token 消耗）扫描已有条目，检测：

```python
# 检测到的矛盾类型
"not working" ↔ "works great"           # 状态冲突
"I handle it" ↔ "someone else handles"   # 归属冲突
"tomorrow" ↔ "already done"             # 时间冲突
```

返回结构化 JSON 供 Agent 自主决策：

```json
{
  "allow_write": true,
  "contradictions": [],
  "suggestion": "add",
  "capacity_check": {"ok": true, "remaining_pct": 68}
}
```

### 🏷️ 反馈标签系统

Agent 在使用上下文完成响应后，可以为页面打标签：

| 标签 | 效果 | 应用场景 |
|------|------|---------|
| `fb:helpful` | RRF 分数 +0.1 | Agent 发现该信息对本次推理有效 |
| `fb:misleading` | RRF 分数 -0.5 | Agent 发现该信息导致错误结论 |
| `fb:outdated` | 标记为待审查 | Agent 发现信息与当前状态不符 |

标签存储在 gbrain page 上，跨会话持久。后续任何 Agent 会话都能查询到反馈历史。

### 🔌 五领域隔离

记忆体按领域分割，每个领域有独立的配额上限：

| 领域 | 配额 | 用途 | @domain 前缀 |
|------|------|------|-------------|
| 💬 Kiki | 300 | 关系状态、性格画像、沟通策略 | `@domain:kiki` |
| 📈 A股 | 400 | 选股配置、因子权重、模型参数 | `@domain:astock` |
| 📢 推广 | 300 | 渠道运营、注册进度、数据统计 | `@domain:promo` |
| ⚙️ 系统 | 300 | 配置规则、架构决策、工程哲学 | `@domain:system` |
| 📦 通用 | 300 | 其他未分类内容 | `@domain:misc` |

路由规则：
```
记忆条目内容 → 解析 @domain: 前缀 → 路由到对应领域 → 检查配额 → 写入

没有 @domain 前缀的条目 → 自动路由到 misc
配额用尽的领域 → 阻止新写入，提示 compaction
```

### ✅ 零依赖验证

所有 7 个新脚本仅使用 Python 标准库：

```
memory_lifecycle.py        → json, sqlite3, sys, os, time, re, argparse, datetime, pathlib
tiered_context_injector.py → json, math, sqlite3, os, sys, time, re, datetime, pathlib
memory_guard.py            → os, json, re, sys, pathlib
memory_prewrite_guard.py   → sys, json, re, pathlib
domain_memory.py           → sys, json, re, pathlib
compact_memory.py          → sys, json, re, pathlib
session_to_gbrain.py       → os, json, time, hashlib, sqlite3, subprocess, sys, pathlib,
                              datetime, timezone, timedelta, collections, re
```

无需 pip install，无需虚拟环境，复制即用。

---

## 快速开始

### 前置条件

- Hermes Agent 已安装（v0.11+）
- Python ≥ 3.9，SQLite 需支持 FTS5（通常默认支持）
- 可选：安装 [gbrain](https://github.com/garrytan/gbrain) 以获得知识图谱功能

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

# 方式 A：一键安装脚本（推荐）
bash install.sh

# 方式 B：Python 安装器
python3 installer/install.py

# 重启 Hermes Gateway 使配置生效
systemctl restart hermes-gateway
```

### 安装验证

```bash
# 检查核心组件
echo "=== 核心脚本 ==="
ls -la ~/.hermes/scripts/tiered_context_injector.py
ls -la ~/.hermes/scripts/memory_lifecycle.py
ls -la ~/.hermes/scripts/session_to_gbrain.py

echo "=== 数据库 ==="
ls -la ~/.hermes/pool.db

echo "=== 归档目录 ==="
ls -d ~/.hermes/archives/*/

echo "=== Skills ==="
ls -d ~/.hermes/skills/memory-*/
```

### 首次运行测试

```bash
# 测试上下文注入
python3 ~/.hermes/scripts/tiered_context_injector.py --recall test

# 测试生命周期检查（干跑）
python3 ~/.hermes/scripts/memory_lifecycle.py --dry-run

# 测试会话同步（干跑）
python3 ~/.hermes/scripts/session_to_gbrain.py --dry-run --batch 3
```

---

## 架构详解

```
┌──────────────────────────────────────────────────────────┐
│                     Hermes Agent                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ memory()     │  │ session      │  │ tiered_context │ │
│  │ 写入         │  │ 上下文       │  │ injector(读取) │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘ │
└─────────┼─────────────────┼──────────────────┼───────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                     记忆体管道层                            │
│                                                            │
│  ┌──────────────┐    ┌────────────────┐  ┌──────────────┐ │
│  │ 写入前守卫    │    │ 会话→gbrain    │  │ 生命周期管理  │ │
│  │ - 容量检查    │    │ (增量同步)     │  │ - stale检测  │ │
│  │ - 矛盾检测    │    │                │  │ - 归档处理   │ │
│  └──────┬───────┘    └───────┬────────┘  └──────┬───────┘ │
│         │                   │                   │         │
│         ▼                   ▼                   ▼         │
│  ┌──────────────┐    ┌────────────────┐  ┌──────────────┐ │
│  │ 领域隔离      │    │ gbrain MCP     │  │ 领域隔离      │ │
│  │ 5大领域配额   │    │ (知识图谱)     │  │ 5大领域配额   │ │
│  └──────┬───────┘    └───────┬────────┘  └──────┬───────┘ │
└─────────┼───────────────────┼──────────────────┼──────────┘
          │                   │                  │
          ▼                   ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                     存储层                                  │
│                                                            │
│  ┌────────────────────┐  ┌───────────────────────────┐    │
│  │ Hermes state.db    │  │ gbrain brain.db            │    │
│  │ messages_fts       │  │ (知识图谱 + 嵌入 + 向量)   │    │
│  │ (60K 条消息)        │  │                           │    │
│  └────────────────────┘  └───────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### 数据写入流程

```
Agent 调用 memory() 写入新内容
    │
    ▼
┌──────────────────────────────────────┐
│ 步骤 1: 容量守卫 (memory_guard.py)    │
│                                      │
│ 检查剩余容量:                         │
│   > 20%  → 允许写入                  │
│   15-20% → 允许写入 + 发出compaction │
│            预警                       │
│   < 15%  → 阻止写入，返回错误        │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ 步骤 2: 矛盾检测                      │
│ (memory_prewrite_guard.py)           │
│                                      │
│ 扫描已有条目:                         │
│   - 状态冲突检测（正则匹配）           │
│   - 归属冲突检测                      │
│   - 时间冲突检测                      │
│                                      │
│ 输出结构化 JSON:                      │
│   {allow_write, contradictions,      │
│    suggestion, capacity_check}       │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ 步骤 3: 领域路由 (domain_memory.py)   │
│                                      │
│ 解析 @domain: 前缀:                   │
│   @domain:kiki    → 路由到 Kiki 领域  │
│   @domain:astock  → 路由到 A股 领域   │
│   @domain:promo   → 路由到 推广 领域  │
│   @domain:system  → 路由到 系统 领域  │
│   无前缀          → 路由到 misc      │
│                                      │
│ 检查领域配额:                         │
│   配额未用完 → 允许写入               │
│   配额用尽   → 阻止写入（提示compaction│
└──────────────┬───────────────────────┘
               ▼
    memory 写入 Hermes state.db
               │
               ▼ (异步，由 cron 调度)
    session_to_gbrain.py
    → 创建/更新 gbrain page
    → 添加 tags + timeline
```

### 数据读取流程

```
Agent 会话启动
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ tiered_context_injector.py                                │
│                                                          │
│  ┌────────────────────────┐  ┌────────────────────────┐  │
│  │ L1: 最近 N 个会话       │  │ L3: gbrain MCP 查询    │  │
│  │ 从 state.db sessions    │  │ 从 gbrain brain.db     │  │
│  │ 表读取                   │  │ （知识图谱搜索）        │  │
│  │ 返回: 摘要文本列表       │  │ 返回: 匹配的页面+片段   │  │
│  └──────────┬─────────────┘  └───────────┬────────────┘  │
│             │                            │               │
│  ┌──────────▼─────────────┐              │               │
│  │ L2: FTS5 全文搜索       │              │               │
│  │ 在 messages_fts 中搜索  │              │               │
│  │ 搜索词: recall 参数      │              │               │
│  │ 衰减: 30天半衰期         │              │               │
│  │ score *= 0.5^(days/30) │              │               │
│  └──────────┬─────────────┘              │               │
│             │                            │               │
│             └──────────┬─────────────────┘               │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐    │
│  │ RRF Fusion (k=60)                                 │    │
│  │                                                     │    │
│  │ 对 L2 和 L3 的每个结果计算 RRF 分数:                │    │
│  │   score(e) = 1/(k + rank_L2(e)) + 1/(k + rank_L3(e))│   │
│  │                                                     │    │
│  │ 应用反馈调整:                                       │    │
│  │   fb:helpful    → score += 0.1                      │    │
│  │   fb:misleading → score -= 0.5                      │    │
│  │                                                     │    │
│  │ 按分数降序排列                                       │    │
│  └──────────────────┬───────────────────────────────┘    │
└─────────────────────┼────────────────────────────────────┘
                      ▼
    输出文件:
    TIERED_CONTEXT.md     — 注入 Agent 系统提示词
    PROACTIVE_RECALL.md   — 预热召回线索
```

### 维护管道（Cron）

```
每日 02:00（合并记忆体综合维护）:
    │
    ├── session_to_gbrain.py      → 增量同步会话到 gbrain
    ├── tiered_context_injector   → 刷新 TIERED_CONTEXT.md
    ├── memory_lifecycle          → stale/archive 状态检查
    └── 归档完整性核查             → memory ↔ gbrain 对比

每周一（附加）:
    └── 四源一致性校验             → memory vs skill vs gbrain vs file

每月 15 日（附加）:
    └── TTL 降级                  → 标记 90 天未更新的条目
```

### 组件全景图

| 组件 | 类型 | 语言 | 依赖 | 行数 |
|------|------|------|------|------|
| `tiered_context_injector.py` | 读取管道 | Python | stdlib | 384 |
| `session_to_gbrain.py` | 写入管道 | Python | stdlib | 476 |
| `memory_lifecycle.py` | 维护 | Python | stdlib | 118 |
| `domain_memory.py` | 路由 | Python | stdlib | 144 |
| `memory_guard.py` | 守卫 | Python | stdlib | 76 |
| `memory_prewrite_guard.py` | 守卫 | Python | stdlib | 58 |
| `compact_memory.py` | 清理 | Python | stdlib | 128 |
| `install.sh` | 安装器 | Bash | — | ~100 |
| `installer/install.py` | 安装器 | Python | stdlib + yaml | 127 |

---

## 脚本参考手册

### 核心管道脚本

#### `tiered_context_injector.py`（384 行）

三层上下文构建器。是记忆体管道的核心读端。

**关键参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `HALF_LIFE_DAYS` | 30 | FTS5 分数衰减半衰期（天） |
| `TOP_K_L1` | 5 | 包含的最近会话数 |
| `TOP_K_L2` | 5 | FTS5 结果数 |
| `TOP_K_L3` | 3 | gbrain 结果数 |
| `RRF_K` | 60 | RRF 融合常数（越小排名优势越大） |
| `FEEDBACK_BOOST` | 0.1 | helpful 标签加分 |
| `FEEDBACK_PENALTY` | -0.5 | misleading 标签减分 |
| `OUTPUT_CONTEXT` | `TIERED_CONTEXT.md` | 输出文件路径 |
| `OUTPUT_RECALL` | `PROACTIVE_RECALL.md` | 预热召回输出文件 |

**L3 数据源：**
- `semantics.db` → `content_chunks` 表（7,600+ 条目）
- `archives_fts` → FTS5 归档索引（3,000+ 条目）

**用法：**
```bash
# 用指定主题构建上下文
python3 tiered_context_injector.py --recall kiki memory stock

# Cron 模式（静默）
python3 tiered_context_injector.py --cron
```

#### `session_to_gbrain.py`（476 行）

将短期会话摘要转化为持久的知识图谱节点。

**增量同步机制：**

```
首次运行:
  扫描全部会话 → 创建 gbrain pages → 
  写入 checkpoint(gbrain_session_cursor) → 完成

后续运行:
  读取 checkpoint → 只处理更新的会话 → 
  更新 checkpoint → 完成

崩溃恢复:
  运行中断 → 最后已知 checkpoint → 
  从中断处继续 → 幂等（内容哈希去重）
```

**用法：**
```bash
# 预览模式
python3 session_to_gbrain.py --dry-run

# 批处理（每次最多 10 条）
python3 session_to_gbrain.py --batch 10

# 完整回填
python3 session_to_gbrain.py
```

**输出 gbrain page 结构：**
```yaml
slug: session/2026-05-13-analysis
type: session
tags: [stock-analysis, a-share, 2026-05]
timeline:
  - date: 2026-05-13
    summary: "Daily stock analysis run"
    detail: "Agent scanned HS300+ZZ500, scored 100 stocks, recommended top 5"
content: |
  ## Session Summary
  - Date: 2026-05-13 09:00 CST
  - Topic: A-share daily analysis
  - Key outcome: 5 stocks recommended with entry/stop-loss targets
```

### 守卫与验证脚本

#### `memory_guard.py`（76 行）

写入前容量扫描，防止容量满时静默失败。

**使用示例：**
```python
# 在 agent workflow 中调用
from memory_guard import check_capacity

result = check_capacity()
# 返回:
# {
#   "remaining": 420,
#   "total": 2200,
#   "needs_compaction": True,
#   "action": "warn"
# }

if result["needs_compaction"]:
    print("[MEMORY GUARD] 容量不足，建议先 compaction")
```

**CLI 用法：**
```bash
# 只检查，不操作
python3 memory_guard.py --check-only

# 检查并自动触发 compaction
python3 memory_guard.py --auto-compact
```

#### `memory_prewrite_guard.py`（58 行）

矛盾检测器。在写入前扫描已有条目，检测与待写入内容的冲突。

**检测模式：**
```python
# 状态反转模式
"还没搞定"  ↔ "已经完成了"    # 状态反转
"不工作"    ↔ "运行正常"     # 状态反转

# 归属变更
"我来负责"  ↔ "转交给别人了"  # 归属变更
"这是最高优先级" ↔ "暂缓处理" # 优先级变更

# 时间矛盾
"明天截止"  ↔ "已经过期"     # 时间矛盾
"下周开始"  ↔ "做了两周了"   # 时间矛盾
```

**返回格式：**
```json
{
  "allow_write": true,
  "contradictions": [],
  "suggestion": "add",
  "capacity_check": {"ok": true, "remaining_pct": 68}
}
```

当检测到矛盾时，`suggestion` 变为 `"replace_old_with_new"` 并给出匹配的旧条目 ID。

#### `domain_memory.py`（144 行）

领域隔离与配额管理器。

**支持的子命令：**
```bash
# 列出某领域的所有条目
python3 domain_memory.py --domain kiki --list

# 查看全部领域使用统计
python3 domain_memory.py --stats
# 输出示例:
# Domain      Used    Quota   Usage%
# kiki        87/300  300     29%
# astock     312/400  400     78%
# promo      201/300  300     67%
# system     154/300  300     51%
# misc        42/300  300     14%

# 检查某领域是否还有空间
python3 domain_memory.py --domain astock --check-capacity
```

#### `compact_memory.py`（128 行）

记忆体压缩工具。分析现有条目并识别可清理项。

**过期模式匹配（基于正则，非 AI）：**
```
模式                 示例匹配
──────────────────────────────────────
已完成|已修复|已部署  "已修复网络问题"
done|fixed|resolved  "fixed the bug in v2"
60+ 天无更新          "last updated March 3"
被新信息替代          "see new entry: @domain:astock #42"
```

**用法：**
```bash
# 生成压缩报告
python3 compact_memory.py --analyze

# 应用清理（调用 memory(action='remove')）
python3 compact_memory.py --apply
```

**输出报告示例：**
```
=== Memory Compaction Report ===
Total entries: 47 (2200 chars, 48% used)
Stale entries found: 3
  1. "已修复：API超时问题" (120d old)
  2. "临时方案：手动重启" (85d old)
  3. "旧版因子配置" (已被新条目替代)

Recommendation: remove 3 entries → free ~280 chars (12%)
```

### 工具脚本

v2.1.1 遗留脚本，保持向后兼容：

| 脚本 | 行数 | 用途 |
|------|------|------|
| `archive_sessions.py` | 231 | 批量会话归档 |
| `auto_session_summary.py` | 72 | 自动生成会话摘要 |
| `gbrain_search.py` | 99 | gbrain 知识图谱搜索 CLI |
| `sync_embeddings.py` | 109 | 嵌入向量同步 |
| `init_db.py` | 61 | 归档数据库初始化 |
| `daily_archive.py` | 105 | 每日归档轮转 |
| `weekly_cleanup.py` | 66 | 周度维护任务 |
| `test_router.py` | 60 | 测试用路由 |
| `backup.py` | 95 | 配置备份 |
| `archive_daily.sh` | 18 | shell 归档脚本 |
| `gbrain_init.sh` | 247 | gbrain 初始化脚本 |
| `gbrain_maintain.sh` | 46 | gbrain 维护脚本 |
| `embedding_server.py` | 175 | 嵌入引擎服务 |

---

## 配置指南

### 记忆体生命周期保护配置

创建 `~/.hermes/memory_lifecycle.yaml` 文件（参考 `config/memory_lifecycle.example.yaml`）：

```yaml
# 受保护页面 slug 列表
protected_slugs:
  - my-project-config      # 项目配置文件页面
  - my-hub-operations       # 运营中心页面

# 受保护标签列表（所有带此标签的页面）
protected_tags:
  - archive                 # 所有归档类页面也受保护
  - hub                     # 所有 hub 页面受保护
  - protected               # 手动标记为受保护的
```

**规则引擎逻辑：**
```
is_protected(slug, tags):
  if slug in protected_slugs → YES ✅
  if any tag in protected_tags → YES ✅
  otherwise → NO ❌
```

- 配置文件**不存在**时，默认不保护任何页面
- 保护页面不会进入 stale/archived 状态
- 保护页面的 RRF 分数不受 feedback 标签影响

### 领域配额配置

在 `domain_memory.py` 中调整 `DOMAIN_QUOTAS` 字典：

```python
DOMAIN_QUOTAS = {
    "kiki": 300,     # Kiki 关系管理
    "astock": 400,   # A 股分析（需要更多空间）
    "promo": 300,    # 推广运营
    "system": 300,   # 系统配置
    "misc": 300,     # 通用
}

# 总量: 1,600 字符（比 flat memory 的 2,200 少 27%）
# 但通过分层检索，有效信息密度更高
```

### Tiered Context 参数调优

```python
# 在 tiered_context_injector.py 中调整

# 半衰期：值越小，旧信息衰减越快
HALF_LIFE_DAYS = 30
#   = 7:  一周后分数减半（适合高频使用场景）
#   = 30: 一月后分数减半（平衡推荐）
#   = 90: 一季后分数减半（适合低频场景）

# RRF 融合常数：值越小，排名优势越大
RRF_K = 60
#   = 30: 前 3 名获得显著优势
#   = 60: 分布均匀（推荐，默认）
#   = 100: 轻微排名优势

# 反馈调分力度
FEEDBACK_BOOST    = 0.1   # 加分（保守）
FEEDBACK_PENALTY  = -0.5  # 减分（激进）
# 设计理念：错误信息的代价远高于漏掉一条有用信息
```

---

## Cron 任务策略

### 推荐设置（安装时自动配置）

| 时间 (CST) | 任务 | 频率 | 说明 |
|-----------|------|------|------|
| 02:00 每日 | 合并记忆体维护 | 每日 | gbrain 同步 + 生命周期检查 + 上下文刷新 |
| 02:00 周一 | + 四源一致性校验 | 每周 | memory ↔ skill ↔ gbrain ↔ file |
| 02:00 每月15日 | + TTL 降级 | 每月 | 标记 90 天未更新条目 |

### 查看当前 Cron 任务

```bash
hermes cron list
```

### 手动触发测试

```bash
# 测试 gbrain 同步
python3 ~/.hermes/scripts/session_to_gbrain.py --dry-run

# 测试上下文注入
python3 ~/.hermes/scripts/tiered_context_injector.py --recall test

# 测试生命周期
python3 ~/.hermes/scripts/memory_lifecycle.py --dry-run

# 一致性校验
python3 ~/.hermes/scripts/memory_lifecycle.py --consistency
```

---

## 增量同步架构详解

`session_to_gbrain.py` 使用 checkpoint 文件实现高效增量操作：

### 同步流程

```
第一轮运行:
  1. 扫描 state.db 中所有会话
  2. 对每个会话，计算内容哈希作为 key
  3. 查询 gbrain 是否已存在相同 key 的页面
  4. 不存在的 → 创建 gbrain page（tag + timeline + content）
  5. 写入 .gbrain_session_cursor（最后处理的时间戳）

后续运行:
  1. 读取 .gbrain_session_cursor
  2. 只查询该时间戳之后的会话
  3. 对每个新会话，重复步骤 2-5

幂等性保证:
  如果某条会话已同步过（内容哈希匹配），跳过
  如果管道中断，下次运行从中断的 checkpoint 继续
```

### 文件位置

```
~/.hermes/scripts/
├── session_to_gbrain.py        # 主同步脚本
├── .gbrain_session_cursor      # Checkpoint 文件（自动创建）
└── ...
```

### 性能数据

| 场景 | 处理量 | 耗时 |
|------|--------|------|
| 日常增量（0-5 条新会话） | 5 | < 3 秒 |
| 小批回填（10 条） | 10 | < 10 秒 |
| 全部回填（100+ 条） | 100 | ~ 60 秒 |

---

## 数据安全与隐私

### 防止内部数据泄漏

v2.2.0 的一项重要重构：将所有可能包含内部数据的配置从代码中剥离。

```
v2.1.1（有风险）:
  memory_lifecycle.py 中硬编码:
    PROTECTED_SLUGS = ["kiki-chat-archive-...", "hub-system-...", ...]
    PROTECTED_TAGS = ["archive", "hub", "protected", "kiki", ...]
  → 推送到 GitHub 后，所有人可见！

v2.2.0（安全）： ✅
  memory_lifecycle.py 运行时从 YAML 加载:
    _load_config() → ~/.hermes/memory_lifecycle.yaml
  → GitHub 仓库中零内部数据
  → config/memory_lifecycle.example.yaml 是通用占位数据
```

### 零第三方依赖

所有脚本仅使用 Python 标准库，没有 pip 包引入风险。代码审查范围可控。

---

## 版本历史

### v2.2.0（2026-05-13）

#### 🚀 新增 7 个 Runtime 脚本

| 脚本 | 行数 | 核心功能 |
|------|------|---------|
| `tiered_context_injector.py` | 384 | 三层上下文注入 v3，RRF 融合排序，反馈调分 |
| `session_to_gbrain.py` | 476 | 会话→gbrain 知识图谱管道，增量 checkpoint |
| `memory_lifecycle.py` | 118 | 页面生命周期状态机，YAML 配置保护 |
| `domain_memory.py` | 144 | 5 领域隔离，独立配额管理 |
| `memory_guard.py` | 76 | 写入前容量守卫，<15% 阻止写入 |
| `memory_prewrite_guard.py` | 58 | 矛盾检测 + 结构化 JSON 输出 |
| `compact_memory.py` | 128 | 记忆体压缩 v2，过期模式识别 |

#### 🔧 修改 4 个文件

| 文件 | 改动 |
|------|------|
| `install.sh` | 版本 2.1.1→2.2.0；修复 `/tmp/memory-repo` 硬编码路径为相对路径 |
| `installer/install.py` | 版本标注 2.0→2.2 |
| `README.md` / `README_CN.md` | 完整文档更新（本文） |
| `tests/test_smoke.py` | 修复硬编码路径，新增脚本测试覆盖 |

#### 🔒 数据安全重构

- `memory_lifecycle.py`：`PROTECTED_SLUGS/TAGS` 硬编码 → 外部 YAML 配置
- 新增 `config/memory_lifecycle.example.yaml`（通用占位数据）

#### 📊 规模对比

| 指标 | v2.1.1 | v2.2.0 | 变化 |
|------|--------|--------|------|
| 脚本总数 | 13 | 20 | **+54%** |
| 代码行数 | ~4,200 | ~5,600 | **+33%** |
| 新功能脚本 | 0 | 7 | **新增** |
| 硬编码内部数据 | 1处 | 0 | ✅ 修复 |
| 硬编码绝对路径 | 3处 | 0 | ✅ 修复 |
| 第三方依赖 | 0 | 0 | ✅ 不变 |

### v2.1.1（2026-05-09）

- 默认嵌入模型切换为 `intfloat/multilingual-e5-small`
- 模型选择器增加 AI 助手自动安装支持
- 跨平台路径支持（Windows/macOS/Linux）

### v2.1.0（2026-05-08）

- 多语言语义搜索
- 新增脚本：嵌入引擎、自动摘要、gbrain 维护
- 跨平台路径处理

### v2.0.0（2026-05-06）

- gbrain 知识图谱集成（Memory 2.0）
- 双路径搜索（gbrain + 本地 FTS5）
- 自动摘要与 curator 自我进化

---

## 致谢

- **[@mattamundson](https://github.com/mattamundson)** — [ralph-orchestrator](https://github.com/mattamundson/ralph-orchestrator) 项目和 ai-agent-memory-patterns 中的配置外部化与内存隔离模式，启发了 `memory_lifecycle.py` 的保护数据外移方案（硬编码 slug/tag → YAML 配置加载）。
- **RRF 融合算法** — `tiered_context_injector.py` 中使用的 Reciprocal Rank Fusion 算法基于信息检索标准公式 `score = Σ 1/(k + rank)`，k=60。
- **[gbrain](https://github.com/garrytan/gbrain)** — garrytan 开发的知识图谱引擎，提供了 `put_page` / `add_timeline_entry` / `query` MCP 接口，支撑了 `session_to_gbrain.py` 和 `tiered_context_injector.py` 的核心功能。
- **@domain 前缀协议** — v1 开发阶段由用户确定的领域隔离命名约定。
- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — 上游 `memory()` 工具提供了所有管道脚本依赖的底层写入/读取原语。

其余所有代码（7 个 runtime 脚本、配置模板、安装器修复、文档）均为全自主开发。零第三方 Python 包依赖。

---

## License

MIT - 详见 [LICENSE](LICENSE) 文件。
