#!/usr/bin/env python3
"""Learn Telegram chat language preferences from bot updates."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_MAP = AGENT_HOME / "private" / "telegram-chat-languages.json"
DEFAULT_OFFSET = AGENT_HOME / "private" / "telegram-updates-offset"
DEFAULT_ENV_FILE = AGENT_HOME / "private" / "alert-webhook.env"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_lang(value: str | None) -> str:
    lowered = str(value or "").strip().lower()
    if lowered.startswith("zh"):
        return "zh"
    if lowered.startswith("en"):
        return "en"
    return ""


def extract_bot_token() -> str:
    direct = str(os.environ.get("MEMORY_ALERT_TELEGRAM_BOT_TOKEN", "")).strip()
    if direct:
        return direct
    forward_url = str(os.environ.get("MEMORY_ALERT_FORWARD_URL", "")).strip()
    if not forward_url and DEFAULT_ENV_FILE.exists():
        for line in DEFAULT_ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("MEMORY_ALERT_FORWARD_URL="):
                forward_url = line.split("=", 1)[1].strip()
                break
    marker = "/bot"
    if "api.telegram.org" in forward_url and marker in forward_url:
        tail = forward_url.split(marker, 1)[1]
        return tail.split("/", 1)[0].strip()
    return ""


def read_offset(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def write_offset(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value), encoding="utf-8")


def load_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_map(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def telegram_api(method: str, params: dict[str, Any], token: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"https://api.telegram.org/bot{token}/{method}?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {"ok": False, "result": []}


def update_from_message(message: dict[str, Any], mapping: dict[str, Any]) -> int:
    user = message.get("from") if isinstance(message.get("from"), dict) else {}
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    language = normalize_lang(user.get("language_code"))
    chat_id = chat.get("id")
    if not language or chat_id in (None, ""):
        return 0
    mapping[str(chat_id)] = {
        "lang": language,
        "source": "telegram_update",
        "user_id": user.get("id"),
        "username": user.get("username"),
        "updated_at": utc_now(),
    }
    return 1


def sync_telegram_languages(map_path: Path, offset_path: Path, token: str, limit: int = 100) -> dict[str, Any]:
    offset = read_offset(offset_path)
    response = telegram_api("getUpdates", {"offset": offset, "limit": limit}, token)
    results = response.get("result") if isinstance(response.get("result"), list) else []
    mapping = load_map(map_path)
    updated = 0
    next_offset = offset

    for row in results:
        if not isinstance(row, dict):
            continue
        update_id = row.get("update_id")
        if isinstance(update_id, int):
            next_offset = max(next_offset, update_id + 1)
        for key in ("message", "edited_message"):
            message = row.get(key)
            if isinstance(message, dict):
                updated += update_from_message(message, mapping)
        callback_query = row.get("callback_query")
        if isinstance(callback_query, dict):
            message = callback_query.get("message")
            user = callback_query.get("from") if isinstance(callback_query.get("from"), dict) else {}
            if isinstance(message, dict) and isinstance(message.get("chat"), dict):
                chat_id = message["chat"].get("id")
                language = normalize_lang(user.get("language_code"))
                if language and chat_id not in (None, ""):
                    mapping[str(chat_id)] = {
                        "lang": language,
                        "source": "telegram_callback",
                        "user_id": user.get("id"),
                        "username": user.get("username"),
                        "updated_at": utc_now(),
                    }
                    updated += 1

    save_map(map_path, mapping)
    if next_offset != offset:
        write_offset(offset_path, next_offset)
    return {
        "ok": True,
        "updates_seen": len(results),
        "entries": len(mapping),
        "updated": updated,
        "next_offset": next_offset,
        "map_path": str(map_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-path", default=str(DEFAULT_MAP))
    parser.add_argument("--offset-path", default=str(DEFAULT_OFFSET))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    token = extract_bot_token()
    if not token:
        print(json.dumps({"ok": False, "error": "missing_telegram_bot_token"}, ensure_ascii=False, indent=2))
        return 1

    payload = sync_telegram_languages(
        Path(args.map_path).expanduser(),
        Path(args.offset_path).expanduser(),
        token,
        limit=args.limit,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
