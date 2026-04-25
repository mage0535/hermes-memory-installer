---
name: memory-starter-kit
description: Hermes 记忆体系入门套件。初始化环境、提供档案模板、使用指南。必装。
---

# Memory Starter Kit

你的第一个 Hermes 记忆管理体系。

---

## 它是什么

Hermes 已经内置了强大的记忆能力：
- **session_search**: 跨会话搜索
- **memory 注入**: 每轮对话自动加载
- **Skill 自动挂载**: 命中时自动加载

但仅仅这些不够。你需要：
1. 结构化的档案存储
2. 模板化的记录方式
3. 自动化的归档和维护

这个 Skill 帮你做好上述一切。

---

## 安装后的目录

```
~/.hermes/
├── archives/              # 你的专属档案库
│   ├── people/            # 人物档案
│   ├── projects/          # 项目档案
│   ├── knowledge/         # 知识档案
│   └── _index/            # 索引和元数据
└── pool.db                # 对话归档数据库
```

---

## 创建第一个档案

### 人物档案

```bash
# 自动创建
hermes-memory new person --name "Alice"

# 或手动创建
cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \
   ~/.hermes/archives/people/alice/profile.md
```

然后填写模板：

```markdown
# 人物档案: Alice

## 基本信息
- 职业: 产品经理
- 认识方式: 2024年活动

## 关键记忆
- 喜欢咖啡，不喝奶茶
- 上次聊天提到在做 AI 项目

## 注意事项
- 避免讨论前公司
```

### 项目档案

```bash
hermes-memory new project --name "MyApp"
```

### 知识档案

```bash
hermes-memory new knowledge --name "Python-Tips"
```

---

## 档案写作规范

### ✅ 应该怎么写

- 用**声明式事实**代替操作指令
- 每条信息是独立的，可以被单独提取
- 保持简洁，单个档案不超100行

```markdown
✅ 好: "Alice 喜欢喝手冲咖啡，不喝奶茶。"
❌ 差: "记住下次给 Alice 带咖啡。"  ← 这是指令，不是事实
```

### ❌ 不应该怎么写

- 不要写任务进度或临时状态
- 不要写对 Hermes 的指令
- 不要写会过期的信息

---

## 与 Hermes 对话时怎么用

### 方式一：直接查询

```
用户：调取 Alice 的档案
Hermes：（通过 session_search 检索档案）
      "Alice 是产品经理，喜欢咖啡..."
```

### 方式二：被动加载

安装 `memory-proactive` 后，你说"Alice 怎么样了"，Hermes 会自动加载 Alice 的档案。

### 方式三：Skill 绑定

创建一个专门的 Skill，内容里引用档案路径。当 Skill 被命中时，档案内容自动注入对话。

---

## 常见问题

**Q: 档案和 memory 工具的区别？**
A: memory 是快照，会话结束后不保存细节。档案是长文档，持久化存储，可以随时查询和更新。

**Q: 多久更新一次档案？**
A: 每次重要对话后随手更新，或者安装 `memory-archivist` 定期归档。

**Q: 可以存储多少档案？**
A: 无限制。但建议保持索引更新，FTS5 索引过大会影响检索速度。

---

*版本：0.1.0 | 依赖：memory-archivist（推荐）*
