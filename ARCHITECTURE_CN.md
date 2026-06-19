# Memory Sidecar 架构说明 v3.5

Memory Sidecar v3.5 是项目的公开可发布版。它部署在智能体旁边，读取智能体的数据目录，在不修改智能体核心代码的前提下增强记忆和召回能力。

发布页： https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5

## 架构目标

v3.5 的架构目标很明确：

1. 保留原始会话数据。sidecar 只做索引和归档，不删除源数据。
2. 多层召回。召回结果要融合会话历史、Hindsight 事实、gbrain 页面和整理后的知识笔记。
3. 保持可移植。只要智能体提供可写的 `AGENT_HOME`，就可以使用同一套运行时。
4. 公开版要稳定。宿主机专用的运维脚本保留在仓库中，但不进入默认安装路径。

## 核心分层

### 1. 热层

热层是智能体本地的短期记忆，保存当前项目上下文、关键偏好和正在纠正的内容。它体积很小，需要时会自动裁剪。

### 2. 温层

温层是 Hindsight。它把会话中的关键事实提取到 PostgreSQL 中，用于持久化召回。

### 3. 冷层

冷层由 gbrain 和 `session_search` 组成：

- gbrain 存储结构化页面、主题中心、时间线和链接关系
- `session_search` 负责对会话归档做全文检索

### 4. 知识层

知识层负责索引整理后的 markdown 知识，包括由 [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management) 产出的知识笔记。这样，整理后的知识可以直接参与召回，而不必先经过原始会话沉淀。

## 召回流程

查询进入后，系统会这样工作：

1. 先判断意图，选择合适的召回家族。
2. 从热层、温层、冷层和知识层取候选结果。
3. 用 Reciprocal Rank Fusion 做融合。
4. 再按意图重排，最后把压缩后的上下文注入给智能体。

这也是它比单一 prompt 内存更强的原因。

## 主要脚本

### `session_to_gbrain.py`

从 `$AGENT_HOME/sessions/` 读取新会话，归档到 gbrain，并记录时间线事件。

### `memory_governance_rebuild.py`

重建召回所需索引：

- 会话索引
- Hindsight 缓存索引
- 知识笔记索引
- 规范化记忆对象
- 冲突分组
- 召回指标

### `memory_guardian.py`

监控健康状态和容量：

- 积压增长
- 重复写入
- 同步延迟
- 卡住的任务
- 热层容量

### `memory_family_registry.py`

负责查询分流，避免项目查询、系统查询和档案查询互相干扰。

### `tiered_context_injector.py`

执行分层召回并注入最终上下文，是实际把记忆送回智能体的运行时入口。

### `memory_maintenance_cycle.py`

按顺序执行完整维护流程：

1. 归档会话
2. 重建治理索引
3. 清理积压
4. 生成分层召回
5. 记录健康状态

### `sidecar_acceptance_check.py`

运行回归检查，确认安装后的运行时仍然符合预期。

## Embedding

Embedding 是可选能力，但建议开启。默认推荐模型是 `intfloat/multilingual-e5-small`。

开启 embedding 后，语义召回能力会更强。不开启时，系统仍可通过以下路径工作：

- FTS5 会话检索
- Hindsight 召回
- gbrain 关键词检索
- 知识笔记索引

## 安装边界

公开安装器关注的是通用运行时，不是宿主机深度耦合：

- 由 `AGENT_HOME` 驱动的安装流程
- 中英文双语输出
- `3 / 2 / 1` 三种安装模式和降级说明
- 保留 embedding 模型选择
- 区分公共运行时脚本和宿主专用辅助脚本

仓库里保留的 `memory_watermark.py` 和 `memory_snapshot_backup.py` 属于可选辅助脚本，默认不进入公开安装路径。

## 兼容性定位

项目追求的是基于稳定数据边界的兼容，而不是深入每个智能体内部做耦合适配。

一个智能体至少需要：

- 可写的 agent home 目录
- `state.db`
- 可读取的会话文件
- 能在智能体进程外运行 Python 辅助脚本

这就是它可以同时服务 Hermes、Claude Code、Codex、Cursor 等多种智能体的原因。

## 运行节奏

典型生产节奏：

- `session_to_gbrain.py`：每 6 小时
- `auto_session_summary.py`：每 6 小时
- `archive_sessions.py`：每天
- `consolidated_system` 健康检查：每小时
- Hindsight reflect：每周

## 与 Knowledge-and-Memory-Management 的关系

`hermes-memory-installer` 是运行时和安装器层。
`Knowledge-and-Memory-Management` 是上游知识整理层。

组合使用时：

- KMM 负责整理知识来源和知识笔记
- Memory Sidecar 负责把这些知识变成智能体可召回的上下文

## 验证

安装后建议执行：

```bash
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

面向用户的概览和安装说明，请查看 [README](README_CN.md)。
