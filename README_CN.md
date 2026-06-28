<div align="center">

# Memory Sidecar v3.5.1

**面向 Hermes、Claude Code、Codex、Cursor 等智能体的可发布外挂记忆体。**

[![Version](https://img.shields.io/badge/version-3.5.1-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5.1)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**English**](README.md) | [**架构说明**](ARCHITECTURE_CN.md)

</div>

## 这是什么

Memory Sidecar 是一个运行在智能体旁边的外置记忆系统。它不修改智能体核心代码，而是读取智能体的数据目录，归档会话、沉淀长期知识，并在后续任务中把相关记忆重新注入上下文。

`v3.5.1` 是当前公开版的稳定性和可观测性增强版本，重点解决：

- 多智能体安装路径统一由 `AGENT_HOME` 驱动
- 会话、Hindsight、gbrain、知识笔记的分层召回
- 公开仓库去除服务器路径、密钥和真实业务数据
- 运行健康检查、告警队列、webhook 转发和 dashboard 可视化
- 安装器保留 Embedding 模型选择：默认模型、常用模型、自定义模型

## 开发原因

很多智能体的记忆能力依赖当前会话窗口或单个本地文件，长期使用后会出现三个问题：

- 重要上下文随着会话结束而丢失。
- 项目文档、历史决策、知识库与当前任务召回脱节。
- 记忆管线故障时缺少健康检查、告警和回归验证。

Memory Sidecar 的目标是把记忆能力从智能体主进程中解耦出来，形成一个可以安装、验证、监控、迁移的外置记忆层。

## 设计思路

项目采用 sidecar 架构：智能体继续使用自己的运行目录，Memory Sidecar 只读取必要数据并写入独立索引和上下文产物。

核心设计原则：

- 不侵入智能体核心代码。
- 通过稳定数据边界适配多种智能体。
- 使用热层、温层、冷层、知识层联合召回。
- 把运行健康状态输出为机器可读指标。
- 公开仓库只保留可复用逻辑，不包含任何私有部署数据。

## 实现目标

- 归档会话到可检索的长期存储。
- 从 Hindsight、gbrain、FTS5 和知识笔记中融合召回。
- 自动运行维护、压缩、孤页修复、健康检查和验收检查。
- 对 action-needed 状态生成本地队列并可转发到外部通知系统。
- 通过静态 dashboard 和 token-gated dashboard server 查看运行状态。
- 支持多 profile 隔离测试，降低多智能体共用主机时的串写风险。

## 依赖要求

- Python `3.9+`
- PostgreSQL `16`
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
- 一个包含 `state.db` 和会话文件的智能体数据目录

适配目标包括：

- Hermes Agent
- Claude Code
- Codex / Codex 风格本地智能体
- Cursor 风格共享数据目录

## 快速安装

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

export AGENT_HOME="$HOME/.hermes"
./install.sh
```

非交互安装：

```bash
./install.sh --noninteractive --agent-home "$HOME/.my-agent"
```

安装后建议执行：

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## 安装模式

安装器支持三种依赖辅助模式：

- `--install-mode 3`：默认模式，优先尝试自动依赖引导。
- `--install-mode 2`：半自动模式，输出推荐命令并引导用户逐步完成。
- `--install-mode 1`：仅检测模式，不修改系统。

安装器支持中英文输出：

```bash
./install.sh --lang zh
./install.sh --lang en
```

## Embedding 模型选择

Embedding 用于语义召回：它把文本转换成向量，让“意思相近但文字不同”的内容也能被召回。没有 Embedding 时，系统仍可使用 FTS5、Hindsight、gbrain 关键词和知识笔记索引；启用 Embedding 后，跨语言和语义相似召回质量通常更好。

安装器会记录所选模型，但 Embedding 服务本身需要单独部署。

默认推荐模型：

- `intfloat/multilingual-e5-small`：默认推荐，体积适中，适合中英文混合和多语言项目。

常用内置模型：

- `BAAI/bge-small-zh-v1.5`：中文优先，轻量，适合内存较小环境。
- `paraphrase-multilingual-MiniLM-L12-v2`：成熟 sentence-transformers 生态，多语言覆盖好。
- `Alibaba-NLP/gte-multilingual-base`：质量更高，内存需求也更高。
- `sentence-transformers/LaBSE`：跨语言对齐较强，适合中文查询英文资料。
- `BAAI/bge-m3`：召回能力强，但模型较大，需要更多内存和磁盘。

也可以通过 `--embedding` 直接指定模型，或在交互安装时输入自定义模型 ID。

## 已安装脚本

公开安装器会部署 28 个运行、支持和可观测性脚本到 `$AGENT_HOME/scripts/`。

主要入口：

- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_family_registry.py`
- `tiered_context_injector.py`
- `memory_maintenance_cycle.py`
- `sidecar_acceptance_check.py`
- `archive_sessions.py`
- `auto_session_summary.py`
- `gbrain_deorphan_index.py`
- `memory_observability_report.py`
- `memory_storage_cross_check.py`
- `runtime_drift_check.py`
- `gbrain_stale_maintenance.py`
- `alert_queue.py`
- `alert_webhook_receiver.py`
- `metrics_dashboard.py`
- `metrics_dashboard_server.py`
- `openmetrics_exporter.py`
- `slo_rollup.py`
- `profile_isolation_soak.py`
- `synthetic_recall_benchmark.py`
- `hindsight_security_audit.py`

支持模块：

- `state_db_schema.py`
- `knowledge_notes.py`
- `recall_samples.py`
- `langsmith_monitor.py`
- `langsmith_task_wrapper.py`
- `langsmith_trend_report.py`

## 外部通知

`alert_queue.py` 会把健康检查结果标准化为本地告警队列。`alert_webhook_receiver.py` 提供真实 webhook 入口，并支持通过私有环境变量转发到外部系统。

告警文本支持语言自适应：

- 优先读取 `payload.lang` / `payload.preferred_lang` / `payload.user_lang`
- Telegram 场景下，bot 已学习到的 `chat_id -> lang` 会优先于默认语言
- 如果 payload 没指定，则回退到 `MEMORY_ALERT_LANG`、`MEMORY_UI_LANG` 或系统 locale
- 当前默认支持 `zh` 和 `en`

Telegram 说明：

- 只有在用户至少给 bot 发过一条消息后，Telegram 才会在更新里提供该用户的 `language_code`
- `telegram_language_sync.py` 会读取这些更新，缓存 `chat_id -> lang`，之后告警推送会自动复用这个语言
- 多接收人配置可参考 `config/alert_recipients.example.json`，生产实际文件放在 `$AGENT_HOME/private/alert-recipients.json`

公开仓库不会硬编码任何第三方 webhook 地址或 token。生产环境可在私有文件中配置：

```bash
MEMORY_ALERT_FORWARD_URL="https://example.com/webhook"
MEMORY_ALERT_FORWARD_KIND="telegram"   # generic/slack/feishu/lark/dingtalk/telegram
MEMORY_ALERT_QUEUE_MAX_LINES="5000"
```

Telegram 还需要：

```bash
MEMORY_ALERT_TELEGRAM_CHAT_ID="..."
```

## Dashboard

新增增强能力：

- `alert_webhook_receiver.py` 支持 dead-letter 重放，用于外部通知系统短暂故障后的补发。
- `metrics_dashboard_server.py` 支持 token-gated HTML、`/api/status` JSON 和 `/metrics` OpenMetrics。
- `slo_rollup.py` 汇总接受率、告警队列增长、dead-letter 重放成功率和召回延迟分位数。
- `synthetic_recall_benchmark.py` 提供不含私有数据的召回回归基准，可用于 CI。

`metrics_dashboard.py` 会生成静态 HTML 状态页。`metrics_dashboard_server.py` 可以在本机提供 token-gated 访问，默认绑定 `127.0.0.1`，避免把记忆指标暴露到公网。

常用运维命令：

```bash
hermes-memory status
hermes-memory slo-rollup
hermes-memory openmetrics
```

仓库内置的 Grafana 面板：

- [docs/grafana/hermes-memory-home.json](docs/grafana/hermes-memory-home.json)：运维首页
- [docs/grafana/hermes-memory-openmetrics-dashboard.json](docs/grafana/hermes-memory-openmetrics-dashboard.json)：OpenMetrics 详细指标面板

可直接落地的 Prometheus / Grafana 部署模板位于 [deploy/observability/README.md](deploy/observability/README.md)。

这套部署模板还包含：

- `prometheus-rules.yml`：默认告警规则
- `provision_dashboards.py`：通过 Grafana API 导入面板，并把首页设置为默认主页

反向代理模板见 [docs/dashboard-reverse-proxy.md](docs/dashboard-reverse-proxy.md)。发布前检查清单见 [docs/release-checklist.md](docs/release-checklist.md)。

## Knowledge-and-Memory-Management

如果你希望把“知识采集、知识整理、知识接入记忆体”做成完整工作流，建议配套使用 [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)。

两个项目的边界：

- `hermes-memory-installer`：负责记忆体 sidecar 运行时、安装、召回和健康检查。
- `Knowledge-and-Memory-Management`：负责知识来源、知识整理、笔记同步和上游知识生产。

组合使用时，KMM 产出整理后的知识资产，Memory Sidecar 把这些资产变成智能体可召回的上下文。

## 验证

仓库验证包括：

- 单元测试和回归测试
- 安装器回滚测试
- 多层召回测试
- 多 profile 隔离测试
- 公开仓库卫生检查

部署后的主要验收命令：

```bash
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## 更新记录

### v3.5.1 (2026-06-26)

- 统一安装器、CLI、文档和发布说明版本号。
- 新增本机 action-needed webhook receiver。
- 支持 Telegram、Slack、飞书/Lark、钉钉等外部通知格式。
- 新增 webhook 入站队列轮转。
- 新增 token-gated dashboard server。
- 新增双 profile 隔离长跑测试。
- 保留 Embedding 默认模型、常用模型和自定义模型选择。

### v3.5 (2026-06-19)

- 完成 GitHub 公开发布整理。
- 统一安装器、CLI、架构文档和手册中的版本号。
- 明确通用 sidecar 与宿主专用运维脚本的边界。
- 补充 KMM 的定位和集成说明。
- 清理公开发布面并补齐许可证文件。

### v3.2 (2026-06-08)

- 增加可观测性报告能力。
- 收敛运行时和环境变量配置。
- 优化 sidecar 文档和目录结构。

### v3.1.0 (2026-06-02)

- 简化为三层记忆架构。
- 移除旧 agentmemory bridge。
- 改用 `AGENT_HOME` 驱动多智能体安装。

## 致谢

参考和依赖项目：

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

感谢生产使用者、GitHub 用户、社区交流群和技术讨论中的反馈。当前版本中的安装降级、Embedding 选择、召回质量校验、多智能体隔离和告警可观测性改进，都来自持续使用过程中的问题反馈和优化建议。

## 许可证

MIT。
