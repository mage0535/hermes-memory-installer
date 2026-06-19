# Hermes Memory Installer v3.5 手动安装说明

本指南面向希望手动安装公开版 sidecar 的用户，不使用 `./install.sh` 也能完成部署。

## 适用范围

手动安装路径部署的是公开的 `v3.5` sidecar 运行时，包括：

- 会话归档到 gbrain
- 治理索引重建
- 分层召回
- 健康检查
- 验收检查
- 整理后的知识笔记索引

它不会修改智能体源码。

它不会默认安装 `memory_watermark.py` 或 `memory_snapshot_backup.py`，这两个脚本属于宿主机专用辅助操作，不在默认公开安装集内。

## 安装模式

包装安装器在 sidecar 部署前支持 3 种依赖协助模式：

- `--install-mode 3`
  默认自动优先模式，适合新手。
- `--install-mode 2`
  指导式协助模式，会输出推荐命令并允许你逐步继续。
- `--install-mode 1`
  仅检测模式，只告诉你缺少什么，不修改系统。

降级顺序：

1. 先尝试 `3`
2. `3` 失败后切换到 `2`
3. `2` 仍失败后切换到 `1`

安装器同时支持：

- `--lang en`
- `--lang zh`

## Embedding 模型选择

安装器保留交互式 embedding 模型选择流程。

- 安装过程中可以从内置模型中选择
- 也可以通过 `--embedding` 直接传入模型 ID
- 交互模式下仍可手动输入自定义模型

## 前置条件

- Python `3.9+`
- `pip`
- PostgreSQL `16`
- 可访问的 Hindsight 服务
- 可访问的 gbrain 服务
- 一个包含 `state.db` 和会话文件的 agent home 目录

安装器辅助依赖：

```bash
python3 -m pip install "PyYAML>=6.0"
```

## 默认安装的脚本集

创建目标脚本目录：

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.hermes}"
mkdir -p "$AGENT_HOME/scripts"
```

复制运行时入口脚本：

```bash
cp scripts/session_to_gbrain.py "$AGENT_HOME/scripts/"
cp scripts/memory_governance_rebuild.py "$AGENT_HOME/scripts/"
cp scripts/memory_guardian.py "$AGENT_HOME/scripts/"
cp scripts/memory_family_registry.py "$AGENT_HOME/scripts/"
cp scripts/tiered_context_injector.py "$AGENT_HOME/scripts/"
cp scripts/memory_maintenance_cycle.py "$AGENT_HOME/scripts/"
cp scripts/sidecar_acceptance_check.py "$AGENT_HOME/scripts/"
cp scripts/archive_sessions.py "$AGENT_HOME/scripts/"
cp scripts/auto_session_summary.py "$AGENT_HOME/scripts/"
cp scripts/memory_observability_report.py "$AGENT_HOME/scripts/"
```

复制支持模块：

```bash
cp scripts/state_db_schema.py "$AGENT_HOME/scripts/"
cp scripts/knowledge_notes.py "$AGENT_HOME/scripts/"
cp scripts/recall_samples.py "$AGENT_HOME/scripts/"
chmod +x "$AGENT_HOME/scripts/"*.py
```

## Skills

```bash
mkdir -p "$AGENT_HOME/skills"
cp -r skills/memory-starter-kit "$AGENT_HOME/skills/"
cp -r skills/memory-archivist "$AGENT_HOME/skills/"
cp -r skills/memory-proactive "$AGENT_HOME/skills/"
```

## Agent 配置

如果你的智能体使用 `config.yaml`，最小应包含以下内容：

```yaml
memory:
  provider: hindsight

skills:
  - memory-starter-kit
  - memory-archivist
  - memory-proactive

memory_sidecar:
  version: "3.5"
  profile: hybrid
  scripts_dir: /path/to/agent-home/scripts
```

请合并到现有配置中，不要整份覆盖。

## Embedding 配置记录

建议记录实际选用的 embedding 模型，便于复现：

```bash
mkdir -p "$AGENT_HOME/memory-sidecar"
cat > "$AGENT_HOME/memory-sidecar/install-profile.json" <<'EOF'
{
  "version": "3.5",
  "profile": "hybrid",
  "embedding_model": {
    "model_id": "intfloat/multilingual-e5-small"
  }
}
EOF
```

## 首次运行

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

期望结果：

- maintenance 返回 `ok: true`
- 归档、治理重建、召回生成和健康检查都成功
- 验收检查返回通过结果

## Knowledge-and-Memory-Management

如果要把“知识采集、知识整理、知识接入记忆体”做完整，建议配套使用 [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)。

两者的职责边界：

- KMM 负责知识来源、整理与供给
- Memory Sidecar 负责把整理后的知识变成智能体可召回上下文

sidecar 默认索引：

- `$AGENT_HOME/knowledge/notes`
- 历史知识路径，如 `$AGENT_HOME/knowledge/wiki/wiki`

## 灰度 / 隔离环境变量

灰度测试或隔离部署时，这些环境变量可覆盖默认路径：

- `MEMORY_STATE_DB_PATH`
- `MEMORY_GOVERNANCE_DB_PATH`
- `MEMORY_KNOWLEDGE_NOTES_DIR`
- `MEMORY_OUTPUT_CONTEXT_PATH`
- `MEMORY_OUTPUT_RECALL_PATH`

## 可选仓库辅助脚本

仓库中保留但不属于公开默认安装集的脚本：

- `memory_watermark.py`
- `memory_snapshot_backup.py`

只有在宿主环境与它们的运行假设匹配时，才建议手动加入。

## 故障排查

| 问题 | 含义 | 首先检查 |
|---------|---------|-------------|
| `ok=false` in maintenance | 某个 sidecar 阶段失败 | 直接重跑失败步骤并查看 stderr |
| 单条查询验收失败 | 召回策略回退或缺少依赖 | 直接运行 `tiered_context_injector.py` 查看结果 |
| gbrain 读取失败 | 冷层不可用 | 检查 gbrain 健康状态与凭据 |
| Hindsight 读取失败 | 温层不可用 | 检查 Hindsight 和 PostgreSQL 连通性 |
| 知识笔记缺失 | KMM / knowledge 路径未被索引 | 检查 `MEMORY_KNOWLEDGE_NOTES_DIR` 和治理重建输出 |
