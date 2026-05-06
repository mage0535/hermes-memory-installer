# Archiving Policy

## Default Settings
- Archive sessions older than 7 days
- Process 15 sessions per batch
- Run daily at 3AM

## Retention
- state.db: auto-prune sessions older than 30 days (Hermes native)
- gbrain: permanent storage (archived pages never deleted)
- pool.db: permanent index (syncs with gbrain)

## Backup Strategy
- config.yaml: auto-backed before installation
- pool.db: re-creatable from archives
- gbrain: versioned pages (no data loss on update)
