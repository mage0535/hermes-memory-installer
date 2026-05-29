# Hermes Memory Installer v3.0 架构说明

本文描述的是最终的 **v3.0 sidecar 外挂记忆体架构**。

Hermes 仍然是对话运行时；本项目提供的是一个部署在 Hermes 旁边的外挂记忆系统，用来：

- 读取 Hermes 会话结果，
- 把重要记忆整理成长期结构，
- 重建治理索引，
- 生成分层召回上下文，
- 暴露健康与运维信号。

它**不会修改 Hermes 核心代码**。

## 架构目标

最终 v3.0 主要围绕五个生产目标设计：

1. **无损保留**
   Hermes 会话始终是源事实层，sidecar 可以摘要、索引、归档，但不依赖删记忆来运行。
2. **分层召回**
   检索不是“换一个数据库”，而是热层、温层、冷层联动。
3. **重点主题管理**
   重要人物、项目、事件、主题可以演变成独立 dossier，而不是永远埋在 session 碎片里。
4. **可观测性**
   backlog、同步滞后、重复数据、重建状态都能看见。
5. **低耦合**
   Hermes 升级不应该要求 sidecar 重写，集成边界应稳定。

## 运行时分层

### 1. 源事实层

这层由 Hermes 自身负责：

- `state.db`
- `~/.hermes/sessions/` 下的 session 文件

作用：

- 保存原始对话，
- 保存时间线，
- 支持回放、审计、恢复。

这层永远不被当成可随便丢弃的缓存。

### 2. 事实提取层

这层从原始会话中提炼更高价值的记忆。

- Hindsight
- sidecar 归档 intake
- session 摘要

作用：

- 抽取可复用事实，
- 识别重复实体和主题，
- 为活跃召回提供更短路径的记忆底层。

### 3. 治理层

这是 sidecar 的控制中枢：

- `memory_governance.db`
- `memory_governance_rebuild.py`
- `memory_family_registry.py`

作用：

- 规范化多源记忆，
- 构建 hub 与 canonical object，
- 统一 family 与 mode 策略，
- 记录 recall 和 maintenance 指标。

### 4. 召回层

这里负责 query 时的分层融合：

- `tiered_context_injector.py`

作用：

- 分类 query 的 family 与 mode，
- 融合 hub / object / hindsight / fallback，
- 当强证据存在时压制弱回退，
- 输出给 Hermes 使用的结构化 recall。

### 5. 运维层

- `memory_maintenance_cycle.py`
- `memory_guardian.py`
- `sidecar_acceptance_check.py`

作用：

- 串行调度维护任务，
- 监控 backlog 与健康状态，
- 暴露同步与队列趋势，
- 跑固定验收集。

## 核心脚本集合

v3.0 支持的生产脚本集合为：

- `memory_family_registry.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_maintenance_cycle.py`
- `session_to_gbrain.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

`installer/install.py` 安装的就是这一组脚本。

## 主要数据层

### Hermes `state.db`

角色：

- 原始会话库，
- 搜索兜底层，
- 审计与回放来源。

### Hindsight

角色：

- 短中期事实层，
- 关系类、上下文类 query 的 live recall 来源，
- consolidation 的记忆汇聚层。

### `memory_governance.db`

角色：

- sidecar 的治理索引与召回控制层。

当前重要逻辑结构：

- session index
- hindsight index
- memory hubs
- memory objects
- recall metrics
- governance meta

### gbrain

角色：

- 长期 archive page，
- hub、tag、link、timeline 边，
- sidecar 的持久归档目标。

## Query Family 与 Mode

v3.0 会对不同 query 采用不同流程。

### Provider / System

Mode：

- `config`
- `runtime`
- `tooling`

例子：

- `hermes gateway provider` -> config-first
- `gateway restart error switching model` -> runtime / incident

### Project

Mode：

- `delivery`
- `exploration`
- `project`

例子：

- `github script deploy` -> delivery-first
- `search open source automation tools` -> exploration-first

### Relationship / Dossier

这一类用于重点档案，例如 `kiki`。

行为特点：

- dossier-first
- 强优先使用 live Hindsight
- 带时间线偏好

## Focused Dossier 模型

v3.0 把“重要内容的单独管理”抽象成 **Focused Dossier**。

一个 dossier 包含：

- aliases
- topic markers
- retention priority
- timeline preference
- recall preference

`kiki` 是第一个生产实例，但架构目标是支持更多 dossier，例如：

- 重要人物，
- 关键项目，
- 长期故障，
- 策略主题，
- 运维专题。

## 维护流程

标准 v3.0 maintenance 流程是：

1. session 归档 intake，
2. governance rebuild，
3. tiered recall generation，
4. guardian 健康快照。

实际对应：

- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `tiered_context_injector.py`
- `memory_guardian.py --status`

维护链还会把 guardian 快照写入历史文件，用来判断 backlog 趋势。

## Backlog 与恢复机制

v3.0 显式处理 sticky Hindsight consolidation backlog。

实际遇到的生产问题：

- backlog 可能粘住但失败数仍然是 0，
- 重复 consolidate 请求可能落到同一个 in-flight operation，
- 队列压力会卡住而不是继续下降。

v3.0 对应缓解：

- 趋势与粘滞性检测，
- stuck operation 检测，
- 受控 drain，
- 带冷却的服务重启保护，
- maintenance 后健康与验收复核。

也就是说，这套系统更强调“显式看见真实状态并可控恢复”，而不是假装永远不会积压。

## 安装器边界

安装器负责：

- 部署支持的 sidecar 脚本，
- 安全 patch Hermes 配置，
- 记录 sidecar 安装元数据，
- 允许用户选择 Embedding Model，
- 保持项目版本为 `3.0`。

安装器不负责：

- 修改 Hermes 核心，
- 做一个任意引擎自由切换矩阵，
- 替代 Hindsight 或 gbrain。

## Embedding Model 的角色

在 v3.0 里，Embedding Model 是部署元数据与召回质量配置，不是“主引擎切换器”。

它影响：

- 语义相似度质量，
- 中英文混合召回质量，
- 资源占用，
- 长期归档的语义搜索效果。

安装器会把用户选定的模型写入安装 profile，便于后续复现和审计。

## 验收基线

开发阶段长期使用的生产回归集是：

- `hermes gateway provider`
- `gateway restart error switching model`
- `github script deploy`
- `search open source automation tools`
- `模型用量`
- `kiki`

只有在以下条件都满足时，项目才应被视为可部署：

- maintenance 为 `ok`
- acceptance 通过
- 核心服务 active
- 没有引入新的 sidecar 回归

## 架构边界

最终 v3.0 的边界很清楚：

- **Hermes 内部**：会话生成、Hermes memory tool、Hermes runtime
- **sidecar 内部**：归档、治理、dossier、召回、健康监控

正因为这个边界稳定，这套设计才更容易跟随 Hermes 升级长期维护。
