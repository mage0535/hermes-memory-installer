<div align="center">

# Memory Sidecar v3.5

**面向 Hermes、Claude Code、Codex、Cursor 等智能体的可发布外挂记忆体。**

[![Version](https://img.shields.io/badge/version-3.5-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**English**](README.md) | [**架构说明**](ARCHITECTURE_CN.md)

</div>

## 这是什么

Memory Sidecar 是一个跑在智能体旁边的外挂记忆体系统，不修改智能体核心代码，只围绕智能体的数据目录工作。它会读取会话、沉淀长期知识，并在后续任务中把相关记忆重新注入上下文。

`v3.5` 是当前架构的对外发布整理版本，目标很明确：

- 用 `AGENT_HOME` 驱动多智能体安装
- 让分层召回、知识笔记召回、安装器、CLI、文档口径完全一致
- 清理公开仓库中的私有路径和部署残留
- 让项目可以真正放到 GitHub 上供用户安装体验和反馈

## 它真正增强了什么

这个外挂记忆体主要从 3 个方面增强智能体：

1. 把会话沉淀到持久层，而不是只停留在当前对话窗口。
2. 通过热层、温层、冷层、知识层联合召回，而不是只依赖单一 prompt 内存。
3. 让整理过的知识笔记也能参与召回，避免项目文档和知识库与会话记忆脱节。

###公开发布边界

`v3.5` 明确区分“通用 sidecar”和“宿主专用运维脚本”：

- 默认安装：通用多智能体 sidecar 运行时、安装器、CLI、记忆技能。
- 仓库内保留但默认不安装：`memory_watermark.py`、`memory_snapshot_backup.py`。

这两个脚本带有更强的 Hermes 和宿主环境假设，所以在公开多智能体安装路径中 **默认不会被安装**，避免降低外部用户的安装成功率。

## 依赖要求

- Python `3.9+`
- PostgreSQL `16`
- 可用的 [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- 可用的 [gbrain](https://github.com/hi-ogawa/gbrain)
- 一个包含 `state.db` 和会话文件的智能体数据目录

当前适配定位：

- Hermes Agent
- Claude Code
- Codex / 类 Codex 本地智能体
- Cursor 类共享数据目录场景

## 快速开始

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

export AGENT_HOME="$HOME/.hermes"   # 也可以是 ~/.claude、~/.cursor、~/.agent 等
./install.sh
```

非交互安装：

```bash
./install.sh --noninteractive --agent-home "$HOME/.my-agent"
```

## 安装模式

安装器支持 3 种依赖安装协助模式：

- `--install-mode 3`
  默认模式。优先尝试最自动化的依赖引导安装路径。

- `--install-mode 2`
  安装器会根超壨方的后续一迋的新同使地店。如果模式的分胫下绤中文。
- `--install-mode 1`
  回中怅一测不怎失败，中文仵一进程失所.

/Fallback order:

1. Try mode `3`
2. If mode `3` fails, switch to mode `2`
3. If mode `2` still fails, switch to mode `1`

The wrapper installer also supports:

- `--lang en`
- `--lang zh`

## Embedding Model Selection

The wrapper installer keeps the embedding model selection flow.

- interactive selection from built-in models
- direct model override with `--embedding`
- custom model id entry in interactive mode

## Prerequisites

- Python `3.9+`
- `pip`
- PostgreSQL `16`
- reachable Hindsight service
- reachable gbrain service
- an agent home directory with `state.db` and session files

Installer helper dependency:

```bash
python3 -m pip install "PyYAML>=6.0"
```

## Core Installed Script Set

Create the target scripts directory:

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.hermes}"
mkdir -p "$AGENT_HOME/scripts"
```

Copy the installed runtime entry scripts:

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

Copy the support modules:

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

## Agent Config

If your agent uses `config.yaml`, the minimum expected entries are:

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

Merge into existing config instead of replacing it wholesale.

## Embedding Profile Metadata

Record the selected embedding model so the deployment is reproducible:

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

## First Run

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

Expected result:

- maintenance returns `ok: true`
- archive, governance rebuild, recall generation, and guardian checks succeed
- acceptance checks return pass output

## Knowledge-and-Memory-Management

For upstream knowledge collection and curation, pair this sidecar with [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management).

Operational relationship:

- KMM manages source knowledge, curated notes, ingestion flows, and broader knowledge operations
- Memory Sidecar indexes curated notes and turns them into recallable context for agents

The sidecar will index:

- `$AGENT_HOME/knowledge/notes`
- legacy paths such as `$AGENT_HOME/knowledge/wiki/wiki`

## Gray / Isolated Runtime Variables

For gray testing or isolated deployments, these optional environment variables can override default paths:

- `MEMORY_STATE_DB_PATH`
- `MEMORY_GOVERNANCE_DB_PATH`
- `MEMORY_KNOWLEDGE_NOTES_DIR`
- `MEMORY_OUTPUT_CONTEXT_PATH`
- `MEMORY_OUTPUT_RECALL_PATH`

## Optional Repository Helpers

These scripts exist in the repository but are not part of the generic public install set:

- `memory_watermark.py`
- `memory_snapshot_backup.py`

Only add them deliberately if your host environment matches their operational assumptions.

## Troubleshooting

| Problem | Meaning | First check |
|---------|---------|-------------|
| `ok=false` in maintenance | One of the sidecar stages failed | Re-run the failed stage directly and inspect stderr |
| Acceptance fails on one query | Retrieval policy regressed or a dependency is missing | Run `tiered_context_injector.py` directly and inspect results |
| gbrain lookup fails | Cold layer unavailable | Check gbrain health and credentials |
| Hindsight lookup fails | Warm layer unavailable | Check Hindsight health and PostgreSQL reachability |
| Knowledge notes missing | KMM/knowledge path not indexed | Check `MEMORY_KNOWLEDGE_NOTES_DIR` and governance rebuild output |
