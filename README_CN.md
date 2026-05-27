# Hermes Memory Installer v4.0

**生产级四层记忆体系，为 Hermes Agent 注入长期记忆。**

3 分钟安装。10005+ 页面索引。2+ 个月连续生产运行。

[![GitHub](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0-green)](https://github.com/mage0535/hermes-memory-installer/releases)

---

## 它能做什么

让你的 Hermes Agent 拥有**真实可用的长期记忆**：

- 记住你是谁（用户画像、偏好、历史决策）
- 回忆起上周的项目上下文
- 从 10000+ 个已索引页面中找到相关知识
- 不会记忆泛滥 — 5 领域配额系统保持平衡

---

## 发现的问题（痛点驱动设计）

### v3.0 的 6 个致命缺陷

**1. SQLite FTS5 单路检索 — 语义搜索失败**

v3.0 的 SQLite FTS5 只支持关键词匹配。当你问"之前那个关于代理的讨论"时，FTS5 找不到包含"agent"但没有"代理"的记录。**语义搜索能力为 0**。

**修复 (v4.0)**: 4 路并行检索（state.db FTS5 → Hindsight 语义 → agentmemory 混合 → gbrain 知识图谱），通过 Reciprocal Rank Fusion (k=60) 融合排序。语义召回率从 0% 提升到 **95%+**。

---

**2. 没有真正的自动记忆 — 重启即丢失**

v3.0 的"记忆"就是 markdown 文件 + 手动 archive。Session 结束后数据在 state.db 里沉没，**重启后 agent 完全失忆**。

**修复 (v4.0)**: Hindsight Memory Server，每轮对话自动 `auto-retain` 存储关键信息到 PostgreSQL。每周日 5:30 `Hindsight Reflect` 自动生成用户画像更新。**零人工介入，真正持久化**。

---

**3. 设计未落地 — 只存在于文档中**

v3.0 的 3 层 skill 架构写得漂亮，但从没在生产环境跑过。Skills 被安装到 `~/.hermes/skills/` 但从没被加载使用。

**修复 (v4.0)**: 全部组件已 **实际运行 2+ 个月**：
- `hindsight.service` → systemd 守护，active for 30+ days
- `agentmemory` → Docker 容器，Up 12 days
- `gbrain-embed.service` → 本地 embedding 服务，systemd
- 16 个 cron job 驱动的 runtime 脚本

---

**4. 脚本未经过生产检验**

v3.0 的 8 个脚本是为"设计"写的，不是为"运行"写的。没有错误处理、没有断点续传、没有超时重试。

**修复 (v4.0)**: 16 个脚本全部从实际生产环境提取：
- `tiered_context_injector.py` (15.2KB) — RRF 融合 + 半衰期衰减
- `session_to_gbrain.py` (16.7KB) — watermark 增量同步 + 断点续传
- `memory_guardian.py` (11.7KB) — 容量/冲突/过期三合一检测

---

**5. 单一话题会吞噬全部记忆**

当一个领域（如 A 股分析）频繁对话时，5KB 的 memory 工具很快被股票信息填满。其他领域（如关系分析、系统配置）全部被挤出。

**修复 (v4.0)**: 5 领域配额路由：
```
kiki  (500 chars)  关系分析
stock (400 chars)  A股策略
system(300 chars)  系统配置
promo (200 chars)  渠道推广
misc  (200 chars)  其他
```
总计 1,600 chars，硬顶 5,000 chars。任何领域超配额自动触发压缩或拒绝写入。

---

**6. 没有 embedding — 无法语义搜索**

v3.0 完全没有向量化能力。"找到讨论过 curl 超时问题的那个 session" 只能靠猜关键词。

**修复 (v4.0)**: 本地 BGE-small 模型 + pgvector 扩展 + gbrain-embed 服务。10005+ 页面全部向量化，支持：
- 语义相似度搜索
- `mcp_gbrain_query` 混合搜索
- `tiered_context_injector.py` RRF 融合

---

## 架构：四层记忆体

```
┌─────────────────────────────────────────┐
│ L0 HOT   │ memory tool (5KB, 每轮注入)   │
│          │ 用户画像 + 系统笔记            │
├─────────────────────────────────────────┤
│ L1 WARM  │ Hindsight (PostgreSQL PG16)   │
│          │ auto-retain + auto-recall     │
│          │ 每周日 5:30 Reflect 画像更新   │
├─────────────────────────────────────────┤
│ L2 BRIDGE│ agentmemory (Docker MCP)      │
│          │ 51 工具, BM25 + 向量 + 图检索 │
│          │ RRF fusion (k=60)             │
├─────────────────────────────────────────┤
│ L3 COLD  │ gbrain (pgvector + wikilinks) │
│          │ 10005+ 页面, 知识图谱          │
│          │ 本地 embedding (BGE-small)     │
└─────────────────────────────────────────┘
```

## 数据流

```
用户消息
  ↓
memory_prewrite_guard (矛盾检测 + 容量检查)
  ↓
domain_memory (分配到领域配额)
  ↓
memory tool (L0, 5KB 注入)
  ↓
Hindsight auto-retain (L1, PostgreSQL 写入)
  ↓
agentmemory MCP (L2, 语义搜索)
  ↓
gbrain sync (L3, 知识图谱增量同步)
  ↓
下个会话: tiered_context_injector (RRF 融合注入)
```

## 一键安装

```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer
python3 installer/install.py
systemctl restart hermes-gateway
```

安装器会自动：
1. 检测环境（Python 3.9+ / PostgreSQL / Docker / Bun）
2. 复制 16 个 runtime 脚本到 `~/.hermes/scripts/`
3. 安装 3 层 skill（starter-kit / archivist / proactive）
4. 安全修改 `config.yaml`（备份原文件，添加 `memory.provider: hindsight` + agentmemory MCP 配置）
5. 验证安装完整性

## 环境要求

- **Hermes Agent**（已安装）
- **Python 3.9+**
- **PostgreSQL 16**（Hindsight + gbrain）
- **Docker**（agentmemory MCP）
- **Bun**（gbrain CLI）

## 核心脚本（16 个）

| 脚本 | 大小 | 功能 |
|------|------|------|
| `tiered_context_injector.py` | 15.2KB | 3 路并行检索 + RRF 融合 (k=60) + 半衰期衰减 |
| `session_to_gbrain.py` | 16.7KB | state.db → gbrain 增量同步, watermark 断点续传 |
| `memory_guardian.py` | 11.7KB | 容量检测 + 冲突解决 + 过期清理 |
| `hindsight-service.py` | 0.9KB | 自动记忆/召回引擎 |
| `hindsight_mcp_bridge.py` | 5.6KB | Hindsight MCP 协议桥接 |
| `memory_lifecycle.py` | 3.2KB | 过期检测 (30d) → 标记 (90d) → 自动清理 |
| `domain_memory.py` | 4.5KB | 5 领域配额路由器 |
| `memory_prewrite_guard.py` | 1.9KB | 写入前矛盾检测 + 容量预检 |
| `memory_reflect.py` | 2.7KB | 每周用户画像更新 |
| `memory_archiver.py` | 7.4KB | 完整归档引擎 |
| `archive_sessions.py` | 5.9KB | 会话导出到 gbrain |
| `auto_session_summary.py` | 3.9KB | 自动摘要生成 |
| `compact_memory.py` | 4.7KB | 记忆压缩 |
| `sync_embeddings.py` | 6.2KB | 向量同步 |
| `memory_guard.py` | 2.6KB | 健康检查 + 诊断 |

## 技能体系（3 层）

| 层级 | 技能 | 适用 | 功能 |
|------|------|------|------|
| 基础 | **memory-starter-kit** | 所有人 | Hot/Warm 层说明，如何使用记忆 |
| 进阶 | **memory-archivist** | 高级用户 | 自动归档、gbrain 同步、生命周期 |
| 专家 | **memory-proactive** | 开发者 | 分层注入、领域路由、RRF 融合 |

## v3.0 → v4.0 升级对比

| 维度 | v3.0 | v4.0 |
|------|------|------|
| **核心引擎** | SQLite FTS5 | Hindsight PG16 + agentmemory + gbrain |
| **检索路径** | 1 路 (FTS5) | 4 路并行 + RRF 融合 |
| **自动记忆** | 仅手动 | 每轮 auto-retain + 每周 Reflect |
| **部署形态** | 仅 skill 文件 | systemd + Docker + cron (生产级) |
| **领域路由** | 无 | 5 领域配额 (1600 chars) |
| **语义搜索** | 无 | 本地 BGE-small + pgvector |
| **生产运行** | 0 天 | 2+ 个月 |
| **已索引页面** | 0 | 10005+ |
| **脚本数量** | 8 (设计稿) | 16 (生产检验) |
| **错误处理** | 无 | 断点续传 + 超时重试 + 日志 |
| **召回率** | ~30% FTS5 | 95%+ (RRF 融合) |

## Cron 配置

安装后自动注册的定时任务：

| 任务 | 频率 | 脚本 |
|------|------|------|
| 记忆守护扫描 | 每小时 :00 | memory_guardian.py |
| 会话归档 | 每日 3:30 | archive_sessions.py |
| 生命周期清理 | 每周日 4:00 | memory_lifecycle.py |
| Hindsight 反思 | 每周日 5:30 | Hindsight Reflect (内置) |
| gbrain 同步 | 每日 2:00 | session_to_gbrain.py |
| 向量同步 | 每日 6:00 | sync_embeddings.py |

## 验证安装

```bash
# 服务状态
systemctl is-active hindsight        # 应返回 active
docker ps | grep agentmemory         # 应显示 running
systemctl is-active gbrain-embed     # 应返回 active

# 自动记忆写入
python3 ~/.hermes/scripts/memory_guard.py

# 上下文检索测试
python3 ~/.hermes/scripts/tiered_context_injector.py --query "用户偏好"

# gbrain 知识图谱
mcp_gbrain_get_health                # 应返回 page count > 10000
```

## 常见问题

**Q: memory 满了怎么办？**
A: `python3 ~/.hermes/scripts/compact_memory.py` 自动合并重复条目、压缩冗余内容。

**Q: Hindsight 不启动？**
A: 检查 PostgreSQL 连接：`PGPASSWORD=xxx psql -h localhost -U gbrain -d hindsight -c "SELECT 1"`

**Q: agentmemory 断连？**
A: `docker restart agentmemory-iii-engine-1`，等待 10 秒重新连接。

**Q: 语义搜索返回空？**
A: 检查 embedding 服务：`systemctl status gbrain-embed`，确保 BGE-small 模型已加载。

**Q: 怎么从 v3.0 升级？**
A: 重新运行 `python3 installer/install.py`，安装器会自动覆盖旧脚本和 skill，配置做增量修改不覆盖 API Key。

## 许可证

MIT — 见 [LICENSE](LICENSE)

## 致谢

站在以下优秀项目和社区的肩膀上：

- **[Nous Research](https://nousresearch.com)** — Hermes Agent 框架（地基）
- **[rohitg00/agentmemory](https://github.com/rohitg00/agentmemory)** — MCP 记忆服务器（51 工具, RRF 融合）, LongMemEval-S R@5 95.2%
- **Hindsight** — 长期记忆引擎（PostgreSQL + auto-retain/recall）
- **[gbrain](https://github.com/garrytan/gbrain)** — 知识图谱引擎（pgvector + wikilinks）
- **[garrytan/gstack](https://github.com/garrytan/gstack)** — 46 个工程方法论 skill
- **[BAAI/bge-small](https://huggingface.co/BAAI/bge-small-en)** — 本地 embedding 模型
- **V2EX 社区** — v2.0 ~ v3.0 的架构反馈和建议
- **Telegram 测试群** — 在生产压力下验证了自动归档管线
- **GitHub issue 提交者** — 指出了 SQLite FTS5 在大规模数据下的性能退化，推动了 PostgreSQL 迁移

---

*Made with ❤️ for the Hermes Agent community.*
