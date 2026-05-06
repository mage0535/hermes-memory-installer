#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 archive_sessions.py --days 7 --batch 15
