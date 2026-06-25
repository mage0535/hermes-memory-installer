#!/usr/bin/env python3
"""
Hot Memory 水位探测器 — 读取 MEMORY.md/USER.md
输出: JSON 水位 + 可归档条目列表（no_agent 模式，空输出=健康）
"""
import os, re, json, math
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.environ.get("AGENT_HOME", str(Path.home() / ".agent"))))
MEMORY_DIR = HERMES_HOME / "memories"

MEMORY_LIMIT = 20000
USER_LIMIT = 12000

def read_entries(filepath):
    """读取用 § 分隔的条目列表"""
    if not filepath.exists():
        return []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    # 条目间用 § 分隔
    raw = [e.strip() for e in text.split("§") if e.strip()]
    return raw

def classify_entry(text, index, total):
    """
    判断条目是否可归档。
    可归档条件：纯历史记录（非活跃规则/配置）
    """
    text_lower = text.lower()
    
    # 永远保留的标签
    keep_keywords = [
        "🔴 铁律", "铁律:", "必须", "禁止",
        "配置哲学", "iron law", "铁则",
        "humanizer skill", "关系建议第一手",
        "vent", "终点线", "笔记保存目录",
        "onedrive files read", "gbrain", "hindsight",
        "memory分层", "cron prompt",
        "fallback链", "cron+systemd", "cron体系",
        "收盘价管线", "用户盲区", "用户分析原则",
        "用户 [强]", "用户 投资",
        "6层信号", "iron rule",
        "全自动运营", "指令模式",
        "多agent违规", "多Agent", "skill更新",
        "草稿/闲聊", "模型提供商与",
        "chat text intake",
        "记忆体系修复",
        "auto_repair",
        "中文输出",
    ]
    
    for kw in keep_keywords:
        if kw in text:
            return False, "活跃规则/配置"
    
    # 可归档条件：历史事件记录
    archive_keywords = [
        "2026-05-3", "2026-06-0", "2026-06-0",
        "session:", "大规模维护",
        "已创建", "已移除", "已部署",
        "集成:", "已集成", "集成确认",
        "清理", "磁盘清理",
        "归档:", "修复:",
        "通过审核", "v3.1.1", "release",
        "gbrain修复", "gbrain stale",
        "gbrain supervisor",
        "xmemory 三项",
        "book-knowledge",
        "smzdm.com",
        "抖音批量",
        "2026-06-06 5工具",
        "2026-06-06 外部",
        "2026-06-06 出院",
        "2026-06-04 session",
        "2026-06-04 术后",
        "2026-06-04 企业级",
        "2026-06-02 session",
        "2026-06-02 市场",
        "2026-06-02 医院",
        "2026-06-02 对话",
        "2026-06-02 毛笔",
        "2026-06-02 晨报",
        "2026-06-01 三日",
        "2026-06-05 术后",
        "2026-06-05 回复",
    ]
    
    for kw in archive_keywords:
        if kw in text:
            return True, "历史事件"
    
    # 旧的历史记录自动归档
    if len(text) > 300 and re.search(r"20\d{2}-\d{2}-\d{2}", text):
        return True, "旧历史事件"
    
    return False, "保留（未知）"

def main():
    mem_file = MEMORY_DIR / "MEMORY.md"
    user_file = MEMORY_DIR / "USER.md"
    
    mem_entries = read_entries(mem_file)
    user_entries = read_entries(user_file)
    
    mem_total = sum(len(e) for e in mem_entries)
    user_total = sum(len(e) for e in user_entries)
    mem_pct = round((mem_total / MEMORY_LIMIT) * 100, 1)
    
    # 只在超阈值时输出
    if mem_pct < 80:
        return  # 静默
    
    # 找出可归档条目（靠前的 = 最老的）
    archivable = []
    for i, entry in enumerate(mem_entries):
        can_archive, reason = classify_entry(entry, i, len(mem_entries))
        if can_archive:
            # 用前 80 个字符作 old_text（足够 memory remove 匹配）
            old_text = entry[:80].strip()
            archivable.append({
                "index": i,
                "old_text": old_text,
                "chars": len(entry),
                "reason": reason,
            })
    
    result = {
        "mem_count": len(mem_entries),
        "mem_chars": mem_total,
        "mem_pct": mem_pct,
        "user_count": len(user_entries),
        "user_chars": user_total,
        "status": "critical" if mem_pct >= 90 else "warning",
        "archivable_candidates": archivable,
        "archivable_total_chars": sum(a["chars"] for a in archivable),
        "archivable_count": len(archivable),
        "action_hint": f"可释放 ~{sum(a['chars'] for a in archivable)} 字符 ({len(archivable)} 条)" if archivable else "无可归档条目",
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
