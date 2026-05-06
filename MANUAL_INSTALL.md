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

## Optional: gbrain Setup

Memory 2.0 works without gbrain (FTS5 fallback). For full knowledge graph:

```bash
curl -fsSL https://bun.sh/install | bash
git clone https://github.com/garrytan/gbrain ~/gbrain
cd ~/gbrain && bun install && gbrain init
gbrain serve &
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
