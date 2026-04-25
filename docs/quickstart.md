# Quick Start - 10 分钟上手

## 1. 安装

```bash
curl -fsSL https://install.hermes-memory.dev | bash
```

或者本地执行：
```bash
cd hermes-memory-installer
python3 installer/install.py
```

## 2. 验证安装

```bash
python3 tests/test_smoke.py
```

应该看到：
```
✅ config.yaml
✅ archives dir
✅ pool.db
✅ memory-starter-kit
✅ memory-archivist
```

## 3. 创建第一个档案

```bash
# 复制模板
cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \
   ~/.hermes/archives/people/alice/profile.md

# 用编辑器打开，填写内容
```

## 4. 让 Hermes 记住

在对话中说：
```
"帮我记录：Alice 喜欢手冲咖啡，不喝奶茶"
```

Hermes 会自动更新 Alice 的档案。

## 5. 体验自动加载

安装 memory-proactive 后：
```
用户: "Alice 最近怎么样了？"
Hermes: （自动加载 Alice 档案）
      "看档案里记录她上次报备了感冒，低能量期..."
```

---

## 下一步

- 阅读完整指南：`docs/advanced.md`
- 查看 Skill 文档：`~/.hermes/skills/memory-starter-kit/SKILL.md`
- 配置自动化：`~/.hermes/skills/memory-archivist/SKILL.md`
