## Memory Sidecar v3.5：当 AI 智能体真的开始「记住」

AI 智能体最尴尬的时刻是什么？你上周跟它聊了三个小时，把项目架构、API 设计、部署坑全交代清楚了，今天打开新会话，它一脸茫然地问你：「你好，有什么我能帮忙的？」

这不是模型能力问题，是记忆断层的结构性问题。每个新会话都是一张白纸，之前的所有上下文灰飞烟灭。

我们在这个问题上折腾了三个月，从 v3.0 到 v3.5，踩过 Docker 桥接层的坑，砍过半成品中间层，最终得出一个结论：**记忆系统不应该嵌入智能体内部，而应该作为一个旁路进程存在。**

这就是 Memory Sidecar 的核心设计思想——sidecar 模式。

### v3.5 真正改了啥

这次的更新没有做大重构，而是补了两块最疼的短板：**知识笔记索引**和**可观测性**。

以前的侧车只能归档会话和回忆事实片段。你说过什么它能记住，但你写好的架构文档、设计决策、方法论笔记，它视而不见。

v3.5 的 `memory_governance_rebuild.py` 学会了读 Markdown 笔记。它扫描 `$AGENT_HOME/knowledge/notes/` 目录下的所有 `.md` 文件，解析 YAML 前置元数据，提取标签和正文摘要，构建 `knowledge_note_index` 表。每条笔记变成一个可检索的知识条目，在前缀元数据完整的前提下，标题来自 frontmatter 或第一个 `#` 标题。

实现并不复杂：

```python
def parse_knowledge_note(path, root_dir):
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _strip_frontmatter(text)
    title = _normalize_note_title(path, body, meta)
    summary = _summarize_note_body(body)
    return {
        "note_id": f"note:{source_path}",
        "title": title[:200],
        "summary": summary[:1200],
        "tags": [str(t).strip() for t in (meta.get("tags") or [])],
        "search_text": f"{title} {summary} {tags} {source_path}"[:4000],
    }
```

真正的复杂度不在解析，而在怎么用这套数据。为此 `tiered_context_injector.py` 新增了一个独立的 **knowledge 检索层**（优先级 35，排在 hub 和 hindsight_cache 之间），专门处理包含 "architecture"、"playbook"、"methodology"、"design" 等标记的查询。RRF 重排序现在会区分知识查询和日常查询——knowledge 层的命中结果获得额外加权，而非知识源的 hub/object 匹配反而降权。

### 看不到的改进：可观测性

`memory_observability_report.py` 是这次新增的运维脚本。它从 governance DB 中抽取召回指标、缓存命中率、知识笔记变更追踪，输出 JSON 或 Markdown 格式的报告。每个意图分类（system、recent、project、knowledge 等）都有独立的样本数、平均延迟、P95 延迟、知识命中率和缓存命中率。

以前遇到召回质量下降，你得猜是哪个环节出了问题。现在一条命令就能看到：是 hindsight 缓存命中率掉了吗？还是 knowledge 索引没更新？还是查询意图分类路由错了？定位时间从小时级降到秒级。

### 另一个隐性改进：所有路径不再硬编码

v3.5 翻了个更大的旧账——7 个核心脚本之前全都硬编码 `~/.hermes` 路径或 `/root/.hermes` 魔数。这意味着侧车只能跟 Hermes Agent 配合使用，换 Claude Code 或 Cursor 就得手动改源码。

现在所有路径通过环境变量暴露：`MEMORY_STATE_DB_PATH`、`MEMORY_GOVERNANCE_DB_PATH`、`MEMORY_OUTPUT_CONTEXT_PATH`、`MEMORY_OBSERVABILITY_DB_PATH`。侧车的最终目标是跟任何写 SQLite 会话文件的智能体配合，不绑定到具体品牌。

### 值不值得升级

如果你已经在跑 v3.2，升级的收益集中在两个场景：一是你有大量 Markdown 笔记/架构文档，想让智能体在对话中主动引用它们；二是你需要量化了解侧车的运行状态，而不是靠感觉判断「好像还行」。

一个数字可以说明当前生产环境的规模：105,601 条索引消息、42,481 个 Hindsight 节点、10,885 个 gbrain 页面、100% 嵌入覆盖率。这套架构每天都在处理这种量级的召回请求，v3.5 在它上面加了一层知识索引，跑下来零故障。

如果你还在用裸智能体没有记忆系统，建议从 v3.5 开始。安装器已经是第三个大版本迭代，交互式引导、环境检查、embedding 模型选择、空跑模式一条龙。跑完 `sidecar_acceptance_check.py` 看到全部绿色通过，就可以放心交给 cron。

记忆系统不值得自己从头造。用现成的，改改参数，把精力花在真正需要推理的事情上。
