<div align="center">

# Memory Sidecar v3.5

**面向 Hermes、Claude Code、Codex、Cursor 等智能体的可发布外挂记忆体。**

[![Version](https://img.shields.io/badge/version-3.5-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5)
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

## 公开发布边界

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
  半自动协助模式。输出推荐命令，并支持用户按步骤继续安装。
- `--install-mode 1`
  仅检测模式。不改系统，只告诉你缺了什么。

如果模式 `3` 失败，请切换到：

```bash
./install.sh --install-mode 2
```

如果模式 `2` 仍然失败，再切换到：

```bash
./install.sh --install-mode 1
```

安装器同时支持中英文输出：

```bash
./install.sh --lang zh
./install.sh --lang en
```

如果不传 `--lang`，安装器会根据本地环境自动判断。

安装后执行：

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## 默认安装的脚本集

公开安装器会把 10 个运行入口脚本和 3 个支持模块部署到 `$AGENT_HOME/scripts/`。

运行入口脚本：

- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_family_registry.py`
- `tiered_context_injector.py`
- `memory_maintenance_cycle.py`
- `sidecar_acceptance_check.py`
- `archive_sessions.py`
- `auto_session_summary.py`
- `memory_observability_report.py`

支持模块：

- `state_db_schema.py`
- `knowledge_notes.py`
- `recall_samples.py`

仓库内可选辅助脚本：

- `memory_watermark.py`
- `memory_snapshot_backup.py`

## 知识笔记集成

除了会话记忆之外，Memory Sidecar 还能接入整理后的 markdown 知识。

默认会检查：

- `$AGENT_HOME/knowledge/notes`
- 历史知识目录，如 `$AGENT_HOME/knowledge/wiki/wiki`

这些内容会进入独立的 `knowledge` 召回层，并与会话检索、Hindsight 事实、gbrain 结果一起参与融合召回。

## Knowledge-and-Memory-Management

如果你希望把“知识采集、知识整理、知识接入记忆体”做完整，建议配套使用 [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)。

它扩展的是上游知识能力，包括：

- 结构化知识采集流程
- wiki / 笔记管理
- 更多同步和接入工具
- 更完整的“知识从哪里来、如何维护、如何被记忆体使用”的工作流

两者的职责边界：

- `hermes-memory-installer`：负责记忆体 sidecar 运行时和安装部署
- `Knowledge-and-Memory-Management`：负责知识来源、知识整理、知识供给

组合使用时，KMM 负责产出整理后的知识资产，Memory Sidecar 负责把这些资产变成智能体可召回的上下文。

## 向量召回

语义召回不是强制依赖，但强烈建议开启。安装器只记录你选择的 embedding 模型，embedding 服务本身需要你单独部署。

默认推荐：

- `intfloat/multilingual-e5-small`

即使不启用 embeddings，以下能力仍然可用：

- FTS5 会话检索
- Hindsight 事实召回
- gbrain 关键词检索
- 知识笔记索引召回

## Embedding 模型选择

安装器会继续保留交互式 Embedding 模型选择功能。

- 安装过程中可以从内置的多个模型中选择。
- 也可以通过 `--embedding` 直接传入模型 ID。
- 交互模式下仍然支持填写自定义模型。

## 兼容性定位

这个项目追求的是“基于稳定数据边界的兼容”，而不是“深入每一种智能体内部做耦合适配”。

对接一个智能体至少需要：

- 一个可写的 agent home 目录
- `state.db`
- 可读取的会话文件
- 能在智能体进程之外运行 Python 辅助脚本

这也是它能服务多种智能体的原因。

## 验证方式

仓库当前通过以下本地验证：

- 单元测试与回归测试
- 安装器回滚测试
- 多层召回测试
- 公开仓库卫生检查

部署后主要验收命令：

```bash
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## 更新记录

### v3.5 (2026-06-19)

- 完成 GitHub 公开发布整理
- 统一安装器、CLI、架构文档、手册中的版本号
- 明确“通用已安装运行时”和“可选 Hermes 运维脚本”的边界
- 补充 KMM 的正式介绍、作用定位与链接
- 清理发布面并补齐许可证文件

### v3.5.1 (2026-06-20)

- 安装器新增中英文双语输出
- 增加 `1 / 2 / 3` 三种安装模式与失败降级说明
- 保留 embedding 模型选择与自定义模型输入
- 补充依赖安装协助的预先说明

### v3.2 (2026-06-08)

- 增加可观测性报告能力
- 进一步收敛运行时和环境变量配置
- 优化 sidecar 文档和目录结构

### v3.1.0 (2026-06-02)

- 简化为三层记忆架构
- 移除旧的 agentmemory 桥接层
- 改用 `AGENT_HOME` 驱动多智能体安装

## 相关链接

- [ARCHITECTURE_CN.md](ARCHITECTURE_CN.md)
- [MANUAL_INSTALL_CN.md](MANUAL_INSTALL_CN.md)
- [MANUAL_INSTALL.md](MANUAL_INSTALL.md)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

## 致谢

参考项目：

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

推动当前公开发布形态的社区和用户反馈主要来自：

- GitHub issues 和 discussions
- 一线生产环境使用者的直接反馈
- 围绕召回质量、安装门槛、多智能体兼容性的持续反馈

## 许可证

MIT。
