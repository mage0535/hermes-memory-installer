---
name: memory-archivist
description: "自动归档会话、FTS5 索引维护、保留策略管理"
tags: [memory, archive, cron, fts5, automation]
---

# Memory Archivist

## Overview

The **memory-archivist** automates session archiving for Memory 2.0:

1. Reads finished sessions from Hermes state.db
2. Creates structured gbrain pages with timeline entries
3. Maintains FTS5 indexes for fast retrieval
4. Enforces retention policies

## Automation

### Option A: Hermes Cron
Use the cronjob tool to schedule the archivist:

```bash
# Daily session archive (3AM)
hermes cron create "0 3 * * *" --prompt "Run archive_sessions.py" --script scripts/archive_sessions.py
```

### Option B: System Cron
```bash
# Daily session archive
(crontab -l 2>/dev/null; echo "0 3 * * * cd ~/.hermes/scripts && python3 archive_sessions.py --days 7 --batch 15") | crontab -
```

## Key Scripts

- `scripts/archive_sessions.py` — Main archiver (watermark-based incremental)
- `scripts/archive_daily.sh` — Daily wrapper (7 days, 15 batch)

## Pitfalls

- **Watermark gap**: If watermark advances before gbrain ingestion completes, sessions may be skipped. Reset with: `sqlite3 ~/.hermes/state.db "INSERT OR REPLACE INTO state_meta (key,value) VALUES ('gbrain_archive_watermark','0')"`
- **Cron session collision**: cron wrapper sessions (cron_*) are auto-excluded from archiving
