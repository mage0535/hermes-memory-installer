# Memory Sidecar 灰度部署运行手册

日期：2026-06-18
目标：在不影响服务器现有业务和记忆内容的前提下，将优化后的 memory sidecar 以双轨方式部署到服务器进行真实场景验证。

## 1. 灰度原则

本次灰度只验证“治理与召回增强”，不直接替换生产主链路，不直接运行会写入 gbrain 的归档流程。

灰度版允许：

- 读取 `$AGENT_HOME/state.db`
- 读取现有 Hindsight 数据
- 读取现有 KMM 知识笔记目录
- 生成独立治理库
- 生成独立 recall 输出

灰度版禁止：

- 覆盖 `$AGENT_HOME/scripts` 生产脚本
- 覆盖生产 `memory_governance.db`
- 覆盖生产 `TIERED_CONTEXT.md` / `PROACTIVE_RECALL.md`
- 运行 `session_to_gbrain.py`
- 运行生产 `memory_maintenance_cycle.py`

## 2. 服务器目标目录

建议灰度目录：

- 代码目录：`$GRAY_CODE_DIR`
- 灰度数据目录：`$GRAY_DATA_DIR`

灰度数据目录内建议包含：

- `memory_governance.gray.db`
- `TIERED_CONTEXT.gray.md`
- `PROACTIVE_RECALL.gray.md`
- `acceptance.gray.json`

## 3. 灰度环境变量

推荐命令前统一导出：

```bash
export AGENT_HOME=/path/to/agent-home
export GRAY_CODE_DIR=/path/to/hermes-memory-installer-gray
export GRAY_DATA_DIR="$AGENT_HOME/gray/memory-sidecar"
export MEMORY_STATE_DB_PATH="$AGENT_HOME/state.db"
export MEMORY_GOVERNANCE_DB_PATH="$GRAY_DATA_DIR/memory_governance.gray.db"
export MEMORY_KNOWLEDGE_NOTES_DIR="$AGENT_HOME/knowledge/notes"
# If your KMM deployment still uses the legacy wiki layout:
# export MEMORY_KNOWLEDGE_NOTES_DIR="$AGENT_HOME/knowledge/wiki/wiki"
export MEMORY_OUTPUT_CONTEXT_PATH="$GRAY_DATA_DIR/TIERED_CONTEXT.gray.md"
export MEMORY_OUTPUT_RECALL_PATH="$GRAY_DATA_DIR/PROACTIVE_RECALL.gray.md"
```

## 4. 灰度验证顺序

### Step 1：重建灰度治理库

```bash
python3 "$GRAY_CODE_DIR/scripts/memory_governance_rebuild.py" --force --quiet
```

验收标准：

- 成功生成 `memory_governance.gray.db`
- 不改动生产 `memory_governance.db`

### Step 2：运行灰度接受性检查

```bash
python3 "$GRAY_CODE_DIR/scripts/sidecar_acceptance_check.py" \
  > "$GRAY_DATA_DIR/acceptance.gray.json"
```

验收标准：

- 接受性检查能正常完成
- 输出包含 guardian 状态与 recall 结果

### Step 3：生成灰度 recall 输出

```bash
python3 "$GRAY_CODE_DIR/scripts/tiered_context_injector.py" \
  --recall "memory" "project retrieval playbook" "知识同步" "用户偏好"
```

验收标准：

- 成功生成 `TIERED_CONTEXT.gray.md`
- 成功生成 `PROACTIVE_RECALL.gray.md`
- 输出写入灰度文件，不覆盖生产文件

## 5. 与 KMM 的联动验收

本次灰度至少要确认以下事项：

1. `MEMORY_KNOWLEDGE_NOTES_DIR` 指向的标准目录或历史 KMM 目录可被索引
2. 灰度治理库中存在 knowledge note 数据
3. 涉及项目方法论、知识沉淀、知识同步的查询，结果中能看到 `knowledge:*` 来源
4. 不影响 KMM 现有知识采集与同步任务

## 6. 回滚说明

本次双轨灰度默认不需要传统回滚，因为不替换生产路径。

如果灰度结果不满意，只需：

- 删除 `$GRAY_CODE_DIR`
- 删除 `$GRAY_DATA_DIR`

生产主链路保持不变。
