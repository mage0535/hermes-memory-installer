# Hermes Memory Installer — 架构设计文档

*版本：v0.1形态定稿 | 目标读者：开发者 / 产品决策者*

---

## 1. 产品定位

让任何 Hermes 用户（包括完全的新手）在 5 分钟内搭建与我们迭代优化后同等级的综合记忆管理体系。

**不是**：
- 一个替换 Hermes 原生记忆机制的系统
- 一个需要改变 Hermes 核心代码的方案
- 一个需要外部服务器或 API Key 的云服务

**是**：
- 一套利用 Hermes 已有能力的使用范式
- 一个一键化的环境搭建工具
- 一组自动化维护工具

---

## 2. 三层 Skill 架构

```
┌────────────────────────────────────────────────────────┐
│  Skill 1: memory-starter-kit【必装】                       │
│  作用：初始化环境 + 提供模板 + 使用指南            │
│  启动时间：仅安装时执行一次                         │
├────────────────────────────────────────────────────────┤
│  Skill 2: memory-archivist【推荐安装】                       │
│  作用：自动归档旧会话 + 定期清理 + 备份              │
│  启动时间：每日/每周 cron 自动运行                    │
├────────────────────────────────────────────────────────┤
│  Skill 3: memory-proactive【选装】                           │
│  作用：对话中主动识别主题 → 预加载档案                  │
│  启动时间：每 5 分钟 cron + 对话触发副本              │
└────────────────────────────────────────────────────────┘
```

---

## 3. 数据流动全图

```
┌────────────────────────────────────────────────────────┐
│  对话发生时                                    │
│  用户说: "Alice 最近怎么样"                    │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐ │
│  │  Step 1: 原生层自动操作（Hermes 内置）      │ │
│  │  • session_search 提取对话上下文          │ │
│  │  • memory 注入已有持久化记忆           │ │
│  │  • Skill 被命中时自动加载 Skill 内容    │ │
│  └──────────────────────────────────────┘ │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐ │
│  │  Step 2: memory-proactive 层（我们实现）   │ │
│  │  • 分析当前对话主题【"Alice"】           │ │
│  │  • 在档案库 FTS5 检索相关档案        │ │
│  │  • 将档案摘要写入 memory（临时注入）   │ │
│  └──────────────────────────────────────┘ │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐ │
│  │  Step 3: 数据持久化（archivist 层）     │ │
│  │  • 对话结束后自动归档到 pool.db        │ │
│  │  • 每周扫描目录更新索引              │ │
│  │  • 清理过期会话释放空间                │ │
│  └──────────────────────────────────────┘ │
├────────────────────────────────────────────────────────┤
│  输出：Hermes 回复带着档案中的背景信息        │
└────────────────────────────────────────────────────────┘
```

---

## 4. 与 Hermes 原生能力的界限

```
┌────────────────────────────────────────────────────────┐
│  我们能做的（Skill 层）                           │
│  ✅ 创建目录结构                                   │
│  ✅ 初始化数据库                                   │
│  ✅ 提供档案模板                                   │
│  ✅ 自动归档会话                                   │
│  ✅ 定期更新索引                                   │
│  ✅ 对话后事分析 + memory 注入（延迟 1 轮）    │
├────────────────────────────────────────────────────────┤
│  我们做不了的（需要改核心）                       │
│  ❌ 实时意图识别（对话中立即解析用户输入）           │
│  ❌ 修改系统 Prompt 组装逻辑                      │
│  ❌ 新增原生 @tool 减少对话开销                  │
└────────────────────────────────────────────────────────┘
```

---

## 5. 安装器算法

```python
# 简化伪代码

def install():
    # 1. 检测
    assert_hermes_installed()
    assert_python_version(">=3.9")
    
    # 2. 备份
    backup_config_yaml()
    
    # 3. 创建目录
    create_directories(ARCHIVE_DIRS)
    
    # 4. 初始化数据库
    init_sqlite_db("pool.db", SCHEMA_SQL)
    
    # 5. 安装 Skills
    install_skills(["memory-starter-kit", "memory-archivist"])
    
    # 6. 修改配置（安全）
    safe_patch_config(add_skill_entries, add_cron_entries)
    
    # 7. 验证
    run_smoke_tests()
    
    # 8. 报告
    print_install_report()
```

**config.yaml 修改原则**
- 使用 YAML 解析器读写，不做文本替换
- 保留现有配置，只追加
- 先写临时文件，验证通过后原子替换

---

## 6. 目录结构规范

```
~/.hermes/
├── config.yaml                    # 原有
├── hermes.db                      # 原有（会话记录）
├── archives/                      # 【新建】主档案目录
│   ├── people/                    # 人物档案
│   │   └── alice/
│   │       ├── profile.md         # 基础信息
│   │       ├── chronology.md      # 时间线
│   │       ├── analysis.md        # 分析结论
│   │       └── raw_logs/          # 原始记录
│   ├── projects/                  # 项目档案
│   │   └── project-a/
│   │       ├── overview.md
│   │       └── specs/
│   ├── knowledge/                 # 知识档案
│   │   └── topic-x.md
│   └── _index/                    # 索引元数据
│       ├── manifest.json          # 档案清单
│       └── tags.yaml              # 标签体系
├── pool.db                        # 【新建】归档数据库
└── skills/                        # 原有
    └── memory-starter-kit/        # 【新安装】
    └── memory-archivist/          # 【新安装】
```

---

## 7. 文件总览（本项目内）

```
hermes-memory-installer/
├── installer/
│   ├── install.py              # 主安装器
│   ├── check_env.py            # 环境检测
│   └── config_patch.py         # config.yaml 安全修改器
├── skills/
│   ├── memory-starter-kit/
│   │   ├── SKILL.md            # 使用指南
│   │   ├── references/
│   │   │   ├── writing-guide.md
│   │   │   └── archive-patterns.md
│   │   └── templates/
│   │       ├── person.md.j2
│   │       ├── project.md.j2
│   │       └── knowledge.md.j2
│   ├── memory-archivist/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/
│   │       ├── daily_archive.py
│   │       ├── weekly_cleanup.py
│   │       └── backup.py
│   └── memory-proactive/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
│           ├── context_router.py   # 上下文路由器主脚本
│           └── topic_extractor.py  # 主题提取模块
├── templates/                  # 原始模板
│   ├── person.md.j2
│   ├── project.md.j2
│   └── knowledge.md.j2
├── scripts/                    # 独立运行脚本
│   ├── init_db.py
│   ├── daily_archive.py
│   └── context_router.py
├── tests/
│   ├── test_install.py
│   ├── test_router.py
│   └── test_smoke.py
├── docs/
│   ├── quickstart.md           # 10 分钟上手
│   └── advanced.md             # 高级配置
├── ARCHITECTURE.md             # 本文件
├── DESIGN.md                   # 设计决策记录
└── README.md
```

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解方案 |
|------|------|----------|
| config.yaml 被修坏 | Hermes 无法启动 | 安装前自动备份，验证后原子替换 |
| 已有 Skill 冲突 | 命名空间冲突 | 使用 `memory-kit-` 前缀，检测并询问 |
| cronjob 与现有任务冲突 | 资源竞争 | 时间窗口可配置，默认随机分布 |
| 用户不会写档案 | 系统流空 | Skill 模板强制填空，增加模板引导 |
| Hermes 版本不兼容 | 安装失败 | 版本检测，最低版本门槛 |

---

## 9. 里程碑

| 阶段 | 交付物 | 时间估算 |
|------|--------|----------|
| M1: 设计确认 | 本文件 + 接口定义 | 1 天 |
| M2: installer 主体 | install.py + 测试 | 2 天 |
| M3: Skill 套件 | 3 个 Skill + 模板 | 3 天 |
| M4: 文档与 QA | quickstart + 高级文档 | 2 天 |
| M5: 集成测试 | 清环测试 | 2 天 |
| **合计** | | **~10 天** |

---

*最后更新：2026-04-25*
