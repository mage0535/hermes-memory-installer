---
name: memory-proactive
description: 专家层 — 分层上下文注入 + 领域路由 + RRF 融合检索
---

# Memory Proactive

专家层。实现跨会话上下文自动注入, 让 AI 在对话开始前就有完整的背景知识。

## 分层上下文注入器 (`tiered_context_injector.py`)

**15.2KB 核心引擎**, 三路并行检索 + Reciprocal Rank Fusion:

```
L1: 最近会话 (state.db, 最近24h)
L2: Hindsight 语义搜索 (PG16, 30天半衰期衰减)
L3: gbrain 知识图谱查询 (pgvector + wikilinks)
↓
RRF fusion (k=60)
↓
注入到当前会话 context
```

### 使用

```bash
python3 scripts/tiered_context_injector.py --query "用户偏好"
```

### 参数
- `--min-score 0.3`: 最低相关度阈值
- `--max-results 10`: 最多返回条数
- `--domains project-alpha,stock`: 限定领域

## 领域内存路由 (`domain_memory.py`)

分配配额, 防止单一领域占用全部内存:

| 领域 | 配额 | 用途 |
|------|------|------|
| project-alpha | 500 | 项目关系分析 |
| stock | 400 | A股策略 |
| system | 300 | 系统配置 |
| promo | 200 | 渠道推广 |
| misc | 200 | 其他 |

## RRF 融合算法

```python
# Reciprocal Rank Fusion
score(doc) = Σ 1/(k + rank_i(doc))
# k=60 经典参数, 多路检索结果融合排序
```

## 升级说明

v2.x 仅支持 SQLite FTS5 单路检索。v3.0 升级为:
- 三路并行 (state → hindsight → gbrain)
- RRF 融合 (vs 简单排序)
- 领域路由 (vs 全局搜索)
- 半衰期衰减 (vs 固定权重)
