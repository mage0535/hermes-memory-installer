# Hermes Memory Installer 2.0 — Manual Installation Guide

For users who want full control.

## Prerequisites

- Hermes Agent installed (v0.11+)
- Python >= 3.9, SQLite with FTS5
- (Optional) [Bun](https://bun.sh) for gbrain

## Quick Steps

### 1. Copy Skills
```bash
cd hermes-memory-installer
cp -r skills/memory-starter-kit ~/.hermes/skills/
cp -r skills/memory-archivist ~/.hermes/skills/
cp -r skills/memory-proactive ~/.hermes/skills/
```

### 2. Init DB
```bash
python3 scripts/init_db.py
```

### 3. Create Archives
```bash
mkdir -p ~/.hermes/archives/{people,projects,knowledge,_index}
```

### 4. Configure
Edit `~/.hermes/config.yaml`:
```yaml
skills:
  - memory-starter-kit
  - memory-archivist
  # - memory-proactive  # Optional
```

### 5. Restart
```bash
systemctl restart hermes-gateway
```


## gbrain + Postgres Setup (Required for Full Memory 2.0)

Memory 2.0 uses gbrain as its Layer 3 knowledge graph engine.
Without gbrain, the system falls back to FTS5-only search.

### Option A: PGLite (Zero-Config)

```bash
curl -fsSL https://bun.sh/install | bash
git clone https://github.com/garrytan/gbrain.git ~/gbrain
cd ~/gbrain && bun install && gbrain init
```

### Option B: PostgreSQL (Production)

```bash
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE USER gbrain WITH PASSWORD 'gbrain_local_only';"
sudo -u postgres psql -c "CREATE DATABASE gbrain OWNER gbrain;"
sudo -u postgres psql -d gbrain -c "CREATE EXTENSION IF NOT EXISTS vector;"
curl -fsSL https://bun.sh/install | bash
git clone https://github.com/garrytan/gbrain.git ~/gbrain
cd ~/gbrain && bun install
DATABASE_URL=postgresql://gbrain:gbrain_local_only@127.0.0.1:5432/gbrain gbrain init
```

### Configure Gateway MCP

In ~/.hermes/config.yaml:

```yaml
mcp_servers:
  gbrain:
    command: /root/.bun/bin/bun
    args:
      - /root/.bun/bin/gbrain
      - serve
    timeout: 120
    connect_timeout: 60
```

Restart Gateway: systemctl restart hermes-gateway

### Verification

```bash
gbrain doctor --fast
gbrain query "test query"
gbrain list -n 5
```

### Automation

```bash
(crontab -l; echo "0 3 * * * cd ~/.hermes/scripts && python3 archive_sessions.py --days 7 --batch 15") | crontab -
(crontab -l; echo "0 4 * * * bash ~/.hermes/scripts/gbrain_maintain.sh") | crontab -
```

### Search

```bash
python3 ~/.hermes/scripts/gbrain_search.py "query"
python3 ~/.hermes/scripts/gbrain_search.py "query" --source telegram
```
## Verification
```bash
python3 tests/test_smoke.py
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| config.yaml error | Check YAML syntax |
| pool.db fails | Check disk/write permissions |
| Skill not loading | Restart gateway |
| FTS5 unavailable | Upgrade SQLite |
| gbrain refused | Ensure port 3000 is running |
