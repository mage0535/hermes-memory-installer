#!/usr/bin/env python3
"""Full backup & restore for Memory 2.0."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

HOME = Path.home()
HERMES = HOME / '.hermes'
BACKUP_DIR = HERMES / 'backups' / 'full'
DBS = ['state.db', 'pool.db', 'semantics.db']

def backup_fn(name=None, dry_run=False):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = name or f"memory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    archive = BACKUP_DIR / f"{name}.tar.gz"
    
    if dry_run:
        print(f"[dry-run] Would create {archive}")
        return
    
    with tarfile.open(archive, 'w:gz') as tar:
        for db in DBS:
            src = HERMES / db
            if src.exists():
                tar.add(src, arcname=db)
        cfg = HERMES / 'config.yaml'
        if cfg.exists():
            tar.add(cfg, arcname='config.yaml')
    
    # Try gbrain export
    try:
        r = subprocess.run('gbrain export --format json 2>/dev/null',
            shell=True, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            export_path = BACKUP_DIR / f"{name}_gbrain.json"
            with open(export_path, 'w') as f:
                f.write(r.stdout)
    except:
        pass
    
    size_kb = os.path.getsize(archive) // 1024
    print(f"Backup OK: {archive} ({size_kb} KB)")

def restore_fn(name, dry_run=False):
    archive = BACKUP_DIR / f"{name}.tar.gz"
    if not archive.exists():
        print(f"Not found: {name}")
        return
    
    if dry_run:
        with tarfile.open(archive) as tar:
            for m in tar.getmembers():
                print(f"  -> {m.name}")
        return
    
    tag = datetime.now().strftime('%Y%m%d%H%M%S')
    extract = BACKUP_DIR / f"_restore_{tag}"
    extract.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(extract)
    
    for db in DBS:
        src = extract / db
        if src.exists():
            dst = HERMES / db
            if dst.exists():
                shutil.copy2(dst, BACKUP_DIR / f"{db}.pre_restore_{tag}")
            shutil.copy2(src, dst)
            print(f"Restored: {db}")

def list_fn():
    if not BACKUP_DIR.exists():
        print("No backups found")
        return
    backups = sorted(BACKUP_DIR.glob('memory_backup_*.tar.gz'), reverse=True)
    if not backups:
        print("No full backups")
        return
    for b in backups:
        print(f"  {b.stem:<30} {os.path.getsize(b)//1024:>6} KB")

def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest='cmd')
    bp = sp.add_parser('backup')
    bp.add_argument('--name')
    bp.add_argument('--dry-run', action='store_true')
    rp = sp.add_parser('restore')
    rp.add_argument('name')
    rp.add_argument('--dry-run', action='store_true')
    sp.add_parser('list')
    args = p.parse_args()
    if args.cmd == 'backup':
        backup_fn(args.name, args.dry_run)
    elif args.cmd == 'restore':
        restore_fn(args.name, args.dry_run)
    elif args.cmd == 'list':
        list_fn()
    else:
        p.print_help()

if __name__ == '__main__':
    main()
