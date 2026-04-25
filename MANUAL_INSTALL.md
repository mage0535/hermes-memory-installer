# Hermes Memory Installer - 手动安装指南（方式 B）

适合已有 Hermes 经验的用户，想要完全控制安装流程。

---

## 快速步骤

### 1. 复制 Skill 套件

```bash
# 进入项目目录
cd hermes-memory-installer

# 复制基础和进阶 Skill
cp -r skills/memory-starter-kit ~/.hermes/skills/
cp -r skills/memory-archivist ~/.hermes/skills/

# 可选：复制专家层 Skill
cp -r skills/memory-proactive ~/.hermes/skills/
```

### 2. 初始化数据库

```bash
python3 scripts/init_db.py
```

这会在 `~/.hermes/pool.db` 创建带有 FTS5 全文检索的数据库。

### 3. 创建档案目录

```bash
mkdir -p ~/.hermes/archives/{people,projects,knowledge,_index}
```

### 4. 添加 Skill 到配置

编辑 `~/.hermes/config.yaml`，在 `skills:` 列表中添加：

```yaml
skills:
  - ...  # 你现有的 skills
  - memory-starter-kit
  - memory-archivist
  # - memory-proactive  # 可选
```

### 5. 重启 Gateway

```bash
# 根据你的实际情况选择一种方式
# 方式一：如果使用 systemd
systemctl restart hermes-gateway

# 方式二：如果使用 Docker
docker restart hermes-gateway

# 方式三：如果手动运行
# 先关闭当前进程，然后重新启动
```

---

## 验证安装

```bash
python3 tests/test_smoke.py
```

预期输出：
```
✅ config.yaml
✅ archives dir
✅ pool.db
✅ memory-starter-kit
✅ memory-archivist
```

---

## 创建第一个档案

```bash
# 使用模板创建人物档案
cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \
   ~/.hermes/archives/people/alice/profile.md

# 用编辑器打开填写
nano ~/.hermes/archives/people/alice/profile.md
```

---

## 可选：配置自动化

### 方式一：cronjob

```bash
# 每日对话归档
(crontab -l 2>/dev/null; echo "0 4 * * * python3 ~/.hermes/skills/memory-archivist/scripts/daily_archive.py") | crontab -

# 每周清理
(crontab -l 2>/dev/null; echo "0 3 * * 0 python3 ~/.hermes/skills/memory-archivist/scripts/weekly_cleanup.py") | crontab -
```

### 方式二：Hermes 内部 cron

使用 Hermes 的 `cronjob` 工具创建自动化任务（如果支持）。

---

## 升级

更新 Skill 时，直接覆盖即可：

```bash
cp -r skills/memory-starter-kit ~/.hermes/skills/
# 重启 Gateway
```

数据库结构更新时，运行：

```bash
python3 scripts/init_db.py
# 该脚本使用 IF NOT EXISTS，不会破坏现有数据
```

---

## 卸载

```bash
# 1. 移除 Skills
rm -rf ~/.hermes/skills/memory-starter-kit
rm -rf ~/.hermes/skills/memory-archivist
rm -rf ~/.hermes/skills/memory-proactive

# 2. 移除 config.yaml 中的引用
# 手动编辑删除 memory-* 行

# 3. 可选：移除数据（注意备份）
# rm -rf ~/.hermes/archives
# rm ~/.hermes/pool.db

# 4. 重启 Gateway
```

---

## 故障排查

| 问题 | 解决方案 |
|------|---------|
| `config.yaml` 格式错误 | 检查 YAML 语法，确保 skills 是列表 |
| pool.db 创建失败 | 检查磁盘空间，确保写入权限 |
| Skill 加载失败 | 确认 Gateway 已重启，检查日志 |
| FTS5 检索无结果 | 确认 SQLite 编译时启用了 FTS5 扩展 |
