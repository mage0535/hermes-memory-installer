# AGENTS.md — Hermes Tool Stack 智能体接入指南

> Hermes-specific: this document describes a Hermes deployment and its surrounding tool stack. It is not the generic multi-agent sidecar install guide.

本文档面向将要接入 Hermes Tool Stack 环境的新智能体。请先完整阅读本文档，识别可用工具集和后端服务，再执行具体任务。

---

## 一、快速安装（给新智能体宿主）

### 安装 Hermes Agent（基础框架）

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
hermes setup        # 交互式配置向导
hermes model        # 选择模型/提供商
hermes gateway start  # 启动网关（如需消息平台）
```

### 安装记忆体（Memory Sidecar v3.5）

```bash
# 方式一：一键安装（推荐）
curl -fsSL https://raw.githubusercontent.com/mage0535/hermes-memory-installer/main/install.sh | bash

# 方式二：手动安装
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
bash install.sh

# 安装后重启
hermes gateway restart
```

### 安装知识管理插件（KMM）

```bash
git clone https://github.com/mage0535/Knowledge-and-Memory-Management.git
cd Knowledge-and-Memory-Management
bash install.sh
```

### 安装第三方 MCP 服务器

参见 `~/.hermes/config.yaml` 中 `mcp_servers` 配置节。常用 MCP：

| MCP 服务器 | 后端服务 | 配置方式 | 端口 |
|---|---|---|---|
| gbrain | gbrain 知识图谱 | `mcp_servers.hermes-gbrain-mcp` | 8787 |
| Chrome DevTools | 无（内置） | `mcp_servers.chrome-devtools` | 9222 |
| AnySearch | 无（远端 API） | `mcp_servers.anysearch` | — |
| headroom | headroom-proxy | `mcp_servers.headroom` | 8787(proxy) |
| scrapling | 无（浏览器池） | `mcp_servers.scrapling` | — |
| tushare | 无（远端 API） | `mcp_servers.tushare-pro` | — |
| codegraph | 无（本地索引） | `mcp_servers.codegraph` | — |
| Horizon | 无（本地服务） | `mcp_servers.horizon` | — |

---

## 二、工具清单（Tool Manifest）

**重要**：开始任何任务前，请先扫描这份清单识别可用工具。工具按功能域分组。

### 2.1 核心域（Core Domains）

| 域 | 工具/能力 | 说明 |
|---|---|---|
| **terminal** | 任意 Shell 命令 | 执行 Python/bash/git/系统命令 |
| **file** | `read_file` / `write_file` / `patch` / `search_files` | 文件读写搜索编辑 |
| **web** | `web_search` / `web_extract` | 网络搜索和内容提取 |
| **browser** | Chrome DevTools MCP / GStack Browser / Scrapling | 浏览器自动化、反爬采集 |
| **vision** | `vision_analyze` | 图像分析（OCR、截图理解） |
| **delegation** | `delegate_task` | 多 Agent 并行子任务 |
| **cron** | `cronjob` | 定时任务编排 |

### 2.2 记忆域（Memory Domain）

| 层 | 工具/后端 | 技术栈 | 速度 | 容量 |
|---|---|---|---|---|
| **Hot** | `memory` 工具 | 系统注入 | 0ms | ~20K chars |
| **Warm** | `hindsight_recall` / `hindsight_retain` / `hindsight_reflect` | PostgreSQL 16 | ~50ms | 5,420+ 节点 |
| **Cold** | `session_search` / gbrain MCP API | SQLite FTS5 / gbrain 知识图谱 | ~500ms | 105K+ 消息 |

### 2.3 知识域（Knowledge Domain）

| 工具 | 来源 | 用途 |
|---|---|---|
| `mcp_anysearch_search` | AnySearch MCP | 垂直领域搜索（20+ 域） |
| `mcp_anysearch_batch_search` | AnySearch MCP | 批量多域搜索 |
| `mcp_anysearch_extract` | AnySearch MCP | 提取页面全文 |
| `mcp_gbrain_*` | gbrain MCP | 知识图谱读写（put_page / query / traverse_graph） |
| `web_search` / `web_extract` | 内置 | 通用网络搜索 |
| `mcp_horizon_*` | Horizon MCP | AI 科技资讯采集分析 |

### 2.4 分析域（Analysis Domain）

| 工具 | 来源 | 用途 |
|---|---|---|
| `mcp_tushare_*` | Tushare MCP | A 股/港股/美股行情、财务数据、宏观数据 |
| `mcp_codegraph_*` | CodeGraph MCP | 代码库分析：符号搜索、调用链、影响分析 |
| `mcp_sequentialthinking` | 内置 | 复杂问题分步推理 |
| `mcp_headroom_*` | headroom MCP | 内容压缩/恢复（节省 token） |
| `graphify` CLI | 本地 | 代码知识图谱构建 |

### 2.5 脚本域（Standalone Scripts）

托管在 `~/.hermes/scripts/` 中，可按需调用：`python3 <script>.py`。

| 脚本 | 用途 |
|---|---|
| `book_cache_manager.py` | 书籍缓存管理与知识精炼触发 |
| `book_to_skill.py` | PDF→Skill 格式知识提取管线 |
| `codegraph_diff_impact.py` | git diff + 知识图谱 = 影响分析报告 |
| `codegraph_onboard.py` | 代码库上手指南生成 |
| `skill_forge.py` | 网站结构探测 + 提取配置生成 |
| `memory_watermark.py` | 记忆体水位检测与归档 |
| `memory_snapshot_backup.py` | 周期快照备份 |
| `session_to_gbrain.py` | 会话归档到 gbrain 知识图谱 |
| `tiered_context_injector.py` | 分层上下文注入（RRF 融合） |

---

## 三、工作流：智能体如何选择工具

**标准流程**：接收任务 → 识别域 → 选择工具 → 执行 → 验证

```
用户请求
   │
   ▼
域名识别 ──────────────────┐
   │        │        │     │
   ▼        ▼        ▼     ▼
  文件     网络     分析   记忆
   │        │        │     │
   ▼        ▼        ▼     ▼
 read_file  web_search  MCP  memory
 write_file web_extract tushare hindsight
 patch      browser     codegraph session_search
 search_files scrapling sequential
             anysearch
```

### 3.1 代码/文件类任务

```
问题: "帮我看看这个bug"
路径: 代码理解
   ├─ codegraph_context("bug描述") → 入口点
   ├─ codegraph_node("symbol") → 符号详情
   ├─ read_file(path) → 查看源码
   └─ patch(path, old, new) → 修复
```

### 3.2 金融分析类任务

```
问题: "分析比亚迪行情"
路径: 金融数据采集
   ├─ mcp_tushare_daily(ts_code="002594.SZ") → K线数据
   ├─ web_search("比亚迪 最新消息") → 新闻
   └─ terminal("python3 script.py") → 计算指标
```

### 3.3 知识记忆类任务

```
问题: "我之前关于 X 的笔记在哪"
路径: 记忆检索
   ├─ hindsight_recall("X") → 长期事实
   ├─ session_search("X") → 历史会话
   └─ mcp_gbrain_query("X") → 知识图谱
```

### 3.4 网页自动化类任务

```
问题: "帮我注册这个平台"
路径: 渠道注册
   ├─ mcp_scrapling_stealthy_fetch → 绕过反爬
   ├─ mcp_scrapling_fetch → 低防护页面
   └─ mcp_scrapling_screenshot → 截图验证
```

---

## 四、工具预检规则（Mandatory Pre-Checks）

每次开始工作前，必须执行以下预检：

### 4.1 MCP 服务器状态

以下 MCP 服务器需要后端服务才能工作。使用前先确认：

| MCP | 后端检查命令 | 健康信号 |
|---|---|---|
| gbrain | `curl -s http://localhost:8787/health` | `200 OK` |
| headroom | `curl -s http://localhost:8787/health` | `200 OK` |
| chrome-devtools | `curl -s http://localhost:9222/json/version` | JSON 返回 |

### 4.2 环境变量

| 工具 | 必需环境变量 | 可选 |
|---|---|---|
| Tushare | `TUSHARE_TOKEN` | — |
| AnySearch | `ANYSEARCH_API_KEY` | — |
| gbrain | `GBRAIN_MCP_TOKEN` | `GBRAIN_MCP_URL` |
| web_search | — | `SERPER_API_KEY` (更佳) |
| text_to_speech | — | 见 provider 配置 |

---

## 五、记忆体安装后的验证清单

安装后执行以下验证确认环境就绪：

```bash
# 1. 验证记忆体目录
ls ~/.hermes/scripts/memory_*.py  # 应有 9+ 个脚本

# 2. 验证 gbrain 可访问
curl -s http://localhost:8787/health | head -c 100

# 3. 验证技能已安装
hermes skills list | grep memory

# 4. 验证知识库
ls ~/.hermes/archives/  # 应有 people/projects/knowledge/_index

# 5. 验证 MCP 连接
hermes mcp list
```

---

## 六、跨会话记忆系统详解

这是 Hermes 区别于普通 AI 的核心能力。

### 6.1 三层访问入口

```python
# Hot — 当前会话的持久事实（memory 工具）
memory(action="add", target="memory", content="用户偏好X")

# Warm — 长期事实图谱（Hindsight API）
hindsight_recall(query="用户的项目偏好")
hindsight_retain(content="用户选择了方案A", tags=["决策"])

# Cold — 完整检索（会话搜索 + 知识图谱）
session_search(query="关于X的讨论")
mcp_gbrain_query(query="概念A")
```

### 6.2 知识沉淀流程

```
会话对话
   │
   ▼
memory + hindsight_retain  ← 即时存储关键偏好
   │
   ▼
session_search  ← FTS5 全文索引（105K+ 消息）
   │
   ▼
gbrain 知识图谱 ← 结构化知识（10,885 页面）
   │
   ▼
下次会话 ← 自动注入相关上下文
```

---

## 七、Skill 系统（经验复用）

Skill 是 Hermes 的可复用程序化记忆。每个 Skill 是一个 `SKILL.md` 文件，包含触发条件、步骤、坑点和验证方法。

```yaml
# SKILL.md 示例
name: my-skill
description: 当执行 X 类任务时自动加载
steps:
  1. 检查 A 条件
  2. 执行 B 操作
  3. 验证 C 结果
pitfalls:
  - 注意 D 情况会导致失败
```

**对智能体的指导**：
- 每次完成复杂任务（5+ 工具调用）、修复棘手错误、或发现非平凡工作流时，保存为 Skill
- 新智能体在 `~/.hermes/skills/` 目录下创建 `SKILL.md` 即可自动被加载
- 使用 `skill_manage(action='create', name='...', content='...')` 注册

---

## 八、常见坑点（Pitfalls）

### 8.1 配置文件

- `~/.hermes/config.yaml` — 设置（可编辑）
- `~/.hermes/.env` — API 密钥（`.env` 优先级高于 `config.yaml`）
- `ROOT` 级 `model.base_url` 会覆盖 `custom_providers` 中的 `base_url`
- `model.api_key` 可能不适用于 delegation 子任务 — 需要单独设置 `delegation.api_key`

### 8.2 工具调用

- 工具变更需要 `hermes tools` 启用 + `/reset`（新会话）才能生效
- 不要在同一回合中连续调用 `read_file` — 先 `search_files` 定位再精准读取
- `execute_code` 不能在 cron 环境中使用（无用户审核）

### 8.3 记忆体

- `memory` 工具有容量上限（~20K chars）— 超 80% 时 `memory_watermark.py` 自动归档
- `hindsight_retain` 写入异步后可用 `hindsight_recall` 检索
- gbrain 需要 worker 进程处理 embedding — `gbrain jobs work` 独立启动

### 8.4 部署

- cron 任务不继承会话上下文 — prompt 必须自包含
- cron 间隔 > 重启总耗时（systemctl 铁律）
- gateway 重启后模型选择可能丢失 — 用 `hermes config set` 持久化

---

## 九、代理子任务规则

使用 `delegate_task` 创建子 Agent 时的约束：

| 属性 | 规则 |
|---|---|
| 并发数 | 最多 3 个并行子 Agent |
| 嵌套深度 | max_spawn_depth=1（子 Agent 不能再次 delegation） |
| 工具集 | 子 Agent 可指定独立 toolsets |
| 子节点限制 | 叶子子 Agent 不能调用：delegate_task, clarify, memory, send_message, execute_code |
| 验证 | 子 Agent 的完成报告是自述声明 — 必须二次验证（读回文件/检查 HTTP 状态） |

---

## 十、快速排障

| 问题 | 检查 |
|---|---|
| 工具不可用 | `hermes tools list` → 检查该工具集是否启用 |
| Agent 看不到技能 | `hermes skills config` → 检查平台启用 |
| 模型无法调用 | `hermes doctor` → `hermes model` |
| Gateway 崩溃 | `grep -i error ~/.hermes/logs/gateway.log \| tail -20` |
| MCP 无响应 | `hermes mcp status` → 检查后端服务是否运行 |
| 记不住东西 | `hindsight_recall("关键词")` → `session_search("关键词")` |

---

*本文档版本：1.0 — 基于 Hermes Agent 生产环境生成*
*参考项目：*
- https://github.com/NousResearch/hermes-agent
- https://github.com/mage0535/hermes-memory-installer
- https://github.com/mage0535/Knowledge-and-Memory-Management
