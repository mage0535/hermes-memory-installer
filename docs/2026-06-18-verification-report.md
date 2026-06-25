# Hermes Memory Sidecar 验证记录

日期：2026-06-18
负责人：Codex
范围：本地代码验证 + 服务器双轨灰度验证 + KMM 兼容性验证

## 1. 本地验证

执行结果：

- `python -m pytest.__main__ -q`
  - 结果：`29 passed`
- Python 编译检查
  - 结果：`scripts/*.py` 全部通过

本地新增验证覆盖：

- 公开仓库去个人化检查
- 去服务器绝对路径检查
- KMM 知识笔记解析
- KMM 知识笔记索引
- KMM 知识查询层
- 灰度运行环境变量重定向

## 2. 本轮核心增强

### 2.1 KMM 知识接入

新增能力：

- 将 `$AGENT_HOME/knowledge/notes` 纳入治理索引
- 自动兼容历史 KMM 路径：
  - `$AGENT_HOME/knowledge/wiki/wiki`
  - `$AGENT_HOME/knowledge/wiki`
- 在 L3 召回中增加 `knowledge` 层

实际效果：

- sidecar 不再只依赖 session / Hindsight / hub / object
- 现在能直接利用 KMM 沉淀的知识笔记增强召回

### 2.2 灰度安全能力

新增环境变量：

- `MEMORY_STATE_DB_PATH`
- `MEMORY_GOVERNANCE_DB_PATH`
- `MEMORY_KNOWLEDGE_NOTES_DIR`
- `MEMORY_OUTPUT_CONTEXT_PATH`
- `MEMORY_OUTPUT_RECALL_PATH`

用途：

- 让灰度版共享生产输入数据
- 同时把治理库和输出文件写到独立路径
- 避免覆盖生产 sidecar 文件

## 3. 服务器灰度验证

### 3.1 灰度目录

- 代码：`$GRAY_CODE_DIR`
- 数据：`$GRAY_DATA_DIR`

### 3.2 灰度模式

本次灰度只执行：

- `memory_governance_rebuild.py`
- `sidecar_acceptance_check.py`
- `tiered_context_injector.py`

本次灰度不执行：

- `session_to_gbrain.py`
- 生产 `memory_maintenance_cycle.py`
- 任何覆盖 `~/.hermes/scripts` 的操作

### 3.3 灰度结果

治理重建结果：

- `sessions_indexed = 7166`
- `recovered_sessions = 81`
- `hindsight_items_total = 11010`
- `hindsight_duplicate_count = 10`
- `memory_hubs = 4`
- `memory_objects = 11083`
- `knowledge_notes = 11`

KMM 兼容结果：

- KMM 历史知识目录成功自动发现
- `knowledge_note_index` 成功写入灰度治理库
- 定向查询 `agent memory architecture` 命中知识笔记：
  - `knowledge:concepts/agent_memory.md`

召回结果：

- `tiered_context_injector.py --test "agent memory architecture"` 已返回 `knowledge` 层结果
- `TIERED_CONTEXT.gray.md` 中已出现 `Agent Memory Architecture`

## 4. 生产安全结论

本次灰度验证未做以下操作：

- 未替换生产脚本
- 未覆盖生产治理库
- 未修改生产输出文件
- 未写入新的 gbrain 归档
- 未更改生产 cron / systemd

因此当前结论是：

- 灰度验证已完成
- 生产主链路保持原状
- 当前服务器可继续使用灰度目录做真实场景观察

## 5. 当前遗留事项

### 高优先级

- 继续观察灰度版在真实场景中的召回质量
- 判断是否需要把 `knowledge` 层在 project/general 查询中进一步前置
- 评估是否将知识层接入接受性检查的固定查询集

### 中优先级

- 针对 Hindsight backlog / sticky 状态做单独治理，不与本次灰度发布耦合
- 增加更系统的记忆质量回归样本库

### 低优先级

- 进一步清理部分历史文档乱码
- 将 README / ARCHITECTURE 同步更新为“支持 KMM 知识层接入”的最新描述
