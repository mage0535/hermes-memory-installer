# 高级配置

## 目录结构定制

编辑 `installer/install.py` 中的 `ARCHIVE_DIRS`：

```python
ARCHIVE_DIRS = [
    "archives/people",      # 人物
    "archives/projects",    # 项目
    "archives/knowledge",   # 知识
    "archives/ideas",       # 灵感（新增）
    "archives/_index",
]
```

## 数据库扩展

### 添加自定义字段

编辑 `scripts/init_db.py` 中的 SCHEMA_SQL：

```sql
ALTER TABLE archives ADD COLUMN importance INTEGER DEFAULT 0;
```

### 创建自定义索引

```sql
CREATE INDEX idx_archives_importance ON archives(importance DESC);
```

## 上下文路由器调优

编辑 `scripts/context_router.py`：

```python
# 提取更长的关键词
self.max_keywords = 15

# 加载更多档案
self.max_results = 5

# 使用 LLM 做 NER（需要配置 API）
```

## 备份策略

### 本地备份

```bash
python3 ~/.hermes/skills/memory-archivist/scripts/backup.py \
    --dest /mnt/backup/hermes-memory
```

### 云备份（示例：rclone + 阿里云盘）

```bash
# 配置 rclone
rclone config

# 添加 cronjob
0 5 * * * rclone sync ~/.hermes/archives aliyun:hermes-backup
```

## 多设备同步

### 方案 A: Git 仓库

```bash
cd ~/.hermes/archives
git init
git remote add origin git@github.com:yourname/hermes-memory.git
```

### 方案 B: Syncthing

安装 Syncthing，将 `~/.hermes/archives` 设为同步文件夹。

## 故障排查

### pool.db 损坏

```bash
# 使用备份恢复
cp ~/.hermes/backups/pool.db.$(date +%Y%m%d) ~/.hermes/pool.db

# 或使用 SQLite 修复
sqlite3 ~/.hermes/pool.db ".recover" > recovered.sql
sqlite3 ~/.hermes/pool.db.new < recovered.sql
```

### 索引失效

```bash
# 重建 FTS5 索引
sqlite3 ~/.hermes/pool.db "INSERT INTO archives_fts(archives_fts) VALUES('rebuild');"
```

### Skill 冲突

```bash
# 查看已安装的 Skill
ls ~/.hermes/skills/

# 手动移除冲突
rm -rf ~/.hermes/skills/memory-starter-kit

# 重新安装
python3 installer/install.py
```
