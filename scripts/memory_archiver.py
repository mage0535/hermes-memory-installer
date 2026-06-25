#!/usr/bin/env python3
"""
Memory 容量监控 + 自动归档脚本 (no_agent)
由系统管家 (consolidated_system.py) 每日 02:30 调用。

职责:
1. 读取 MEMORY.md/USER.md 容量
2. 如果容量 >85%，识别可归档的低价值条目
3. 用 gbrain CLI 归档到对应 hub 页面
4. 从 memory 文件中移除已归档条目
5. 经验类条目同时推送到 Hindsight
6. 输出归档报告 (stdout → Telegram 推送)
"""
import re, os, sys, subprocess, json, urllib.request, shutil
from datetime import datetime
import os
from pathlib import Path

AGENT_HOME = Path(os.environ.get("HERMES_HOME", os.environ.get("AGENT_HOME", str(Path.home() / ".hermes"))))
MEMORY_DIR = AGENT_HOME / "memories"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"
USER_FILE = MEMORY_DIR / "USER.md"
GBRAIN = shutil.which("gbrain") or os.environ.get("GBRAIN_BIN", "gbrain")
HINDSIGHT_URL = "http://127.0.0.1:8890/v1/default/banks/hermes/memories"

CAPACITY_WARN_PCT = 85


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M')}] {msg}", file=sys.stderr, flush=True)


def read_entries(path: Path):
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    entries = [e.strip() for e in content.split("§") if e.strip()]
    seen = set()
    unique = []
    for e in entries:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def write_entries(path: Path, entries: list):
    path.write_text("\n§\n".join(entries) + "\n", encoding="utf-8")
    log(f"已写入 {len(entries)} 条到 {path.name}")


def gbrain_put(slug: str, content: str) -> bool:
    p = subprocess.run(
        [GBRAIN, "put", slug],
        input=content,
        capture_output=True, text=True, timeout=30,
    )
    if p.returncode != 0:
        log(f"gbrain put {slug} 失败: {p.stderr[:200]}")
        return False
    return True


def hindsight_retain(content: str, context: str = "") -> bool:
    """Push experience-type entry to Hindsight Retain API. Silent if Hindsight is down."""
    try:
        payload = json.dumps({
            "items": [{
                "content": content,
                "context": context,
                "document_id": f"memory_archive_{datetime.now().strftime('%Y%m%d')}"
            }]
        }).encode()
        req = urllib.request.Request(
            HINDSIGHT_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        # 3s timeout — don't block archiving if Hindsight is temporarily down
        resp = urllib.request.urlopen(req, timeout=3)
        if resp.getcode() == 200:
            return True
    except Exception as e:
        log(f"Hindsight retain 失败 (非致命): {e}")
    return False


def classify_entry(entry: str):
    """返回 (gbrain_slug, archive_summary, is_experience) 或 (None, None, False)"""
    # 核心行为规则 - 始终保留
    KEEP = ["Never send empty responses", "humanizer skill", "Changelog 格式偏好",
            "配置哲学", "Gmail IMAP passwords"]
    for k in KEEP:
        if k in entry:
            return None, None, False

    e = entry.lower()

    # 本次会话新增 - 保留
    if "warp-svc 内存泄漏" in entry: return None, None, False
    if "系统管家 cron" in entry and "0,30" in entry: return None, None, False
    if "systemd-journald 限额" in entry: return None, None, False
    # 最新 session - 保留
    if "check_memory" in entry: return None, None, False

    # 重要陷阱 - 保留
    if "OpenCode credential pool" in entry: return None, None, False
    if "自审规则" in entry: return None, None, False

    # 可归档的老条目

    if "Mastodon" in entry: return ("hub-system-operations", entry[:150], False)
    if "项目+工具路径" in entry: return ("hub-system-operations", entry[:150], False)
    if "推广:" in entry and "tool_manifest" in entry: return ("hub-social-media", entry[:150], False)
    if "v2raya 路由规则" in entry: return ("hub-system-operations", entry[:150], False)
    if "Yfinance + 27" in entry: return ("hub-system-operations", entry[:150], False)
    if "Tushare Pro integrated" in entry: return ("hub-system-operations", entry[:150], False)
    if "Free signal sources" in entry: return ("hub-a-stock-trading", entry[:150], False)
    if "stock-strategies skill" in entry: return ("hub-a-stock-trading", entry[:150], False)
    if "rclone OAuth" in entry: return ("hub-system-operations", entry[:150], False)
    if "金融综合 cron" in entry: return ("hub-a-stock-trading", entry[:150], False)
    if "gbrain minion worker" in entry: return ("hub-system-operations", entry[:150], False)
    if "curator_runner.py 修复" in entry: return ("hub-system-operations", entry[:150], False)

    return None, None, False


def check_capacity(entries: list, limit: int) -> dict:
    total = sum(len(e) for e in entries)
    return {"total_chars": total, "limit": limit, "pct": round(total / limit * 100, 1), "count": len(entries)}


def main():
    mem_entries = read_entries(MEMORY_FILE)
    if not mem_entries:
        return

    cap = check_capacity(mem_entries, 5000)
    log(f"Memory: {cap['pct']}% ({cap['count']}条, {cap['total_chars']}/5000)")

    if cap["pct"] < CAPACITY_WARN_PCT:
        return

    log(f"容量 {cap['pct']}% > {CAPACITY_WARN_PCT}%，归档中...")
    kept, archived_list, hindsight_pushed = [], [], []

    for entry in mem_entries:
        slug, summary, is_experience = classify_entry(entry)
        if slug and summary:
            content = f"---\ntitle: Memory自动归档 {datetime.now().strftime('%Y-%m-%d')}\n---\n\n{entry}\n\n_自动归档于 {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"
            # Always archive to gbrain
            if gbrain_put(slug, content):
                archived_list.append(summary)
                log(f"归档→gbrain: {summary[:60]}")
                # Experience-type entries also push to Hindsight
                if is_experience:
                    if hindsight_retain(entry, context=f"auto-archive from memory tool"):
                        hindsight_pushed.append(summary)
                        log(f"归档→Hindsight: {summary[:60]}")
            else:
                kept.append(entry)
        else:
            kept.append(entry)

    if archived_list:
        write_entries(MEMORY_FILE, kept)
        new_cap = check_capacity(kept, 5000)
        report = "## 🧠 Memory 容量维护\n\n"
        report += f"- **归档前**: {cap['pct']}% ({cap['count']}条)\n"
        report += f"- **归档后**: {new_cap['pct']}% ({new_cap['count']}条)\n"
        report += f"- **→ gbrain**: {len(archived_list)} 条\n"
        for a in archived_list:
            report += f"  - {a[:70]}…\n"
        if hindsight_pushed:
            report += f"- **→ Hindsight**: {len(hindsight_pushed)} 条\n"
        print(report)

    # User 文件检查
    user_entries = read_entries(USER_FILE)
    if user_entries:
        ucap = check_capacity(user_entries, 3000)
        if ucap["pct"] > CAPACITY_WARN_PCT:
            print(f"## 👤 User Profile\n- 使用率 {ucap['pct']}% ({ucap['count']}条, {ucap['total_chars']}/3000)\n")


if __name__ == "__main__":
    main()
