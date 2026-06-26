#!/usr/bin/env python3
"""
Session → Gbrain Pipeline
==========================
将智能体会话摘要自动摄入 gbrain 知识图谱。
每个会话生成一个 gbrain page，带 tag + timeline + 主题链接。

运行: python3 scripts/session_to_gbrain.py [--batch N] [--dry-run]
Cron: 每 6 小时一次，增量处理新会话
"""

import os
import json
import time
import hashlib
import sqlite3
import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import re
from tempfile import NamedTemporaryFile

# --- gbrain MCP API bridge (auto-patched) ---
import urllib.request as _urllib
import json as _json

_GBRAIN_MCP = os.environ.get("GBRAIN_MCP_URL", "http://localhost:8787/mcp")
_GBRAIN_TOKEN = os.environ.get("GBRAIN_MCP_TOKEN", "")
# Configure authentication through GBRAIN_MCP_TOKEN.

def _mcp_call(method, params, req_id=1):
    """Call gbrain via MCP API directly (bypasses broken CLI)"""
    data = _json.dumps({"jsonrpc":"2.0","id":req_id,"method":"tools/call","params":{"name":method,"arguments":params}}).encode()
    req = _urllib.Request(_GBRAIN_MCP, data=data,
        headers={"Content-Type":"application/json","Authorization":f"Bearer {_GBRAIN_TOKEN}"})
    try:
        resp = _urllib.urlopen(req, timeout=15)
        result = _json.loads(resp.read())
        if "error" in result:
            raise subprocess.CalledProcessError(1, "gbrain-mcp", result["error"].get("message",""))
        tool_result = result.get("result") or {}
        if tool_result.get("isError"):
            content = tool_result.get("content") or []
            message = "; ".join(
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict) and item.get("text")
            ) or "MCP tool call failed"
            raise RuntimeError(message)
        return result
    except Exception as e:
        raise subprocess.CalledProcessError(1, ["gbrain-mcp", str(e)]) from e

def run_gbrain_mcp(args, input_text=None):
    """MCP-based replacement for run_gbrain(). Same interface, uses MCP API."""
    cmd = args[0] if args else ""

    if cmd == "put":
        slug = args[1]
        _mcp_call("put_page", {"slug": slug, "content": input_text or ""})
    elif cmd == "tag":
        slug, tag = args[1], args[2]
        _mcp_call("add_tag", {"slug": slug, "tag": tag})
    elif cmd == "timeline-add":
        slug, date, text = args[1], args[2], args[3]
        _mcp_call("add_timeline_entry", {"slug": slug, "date": date, "summary": text})
    elif cmd == "link":
        from_slug, to_slug = args[1], args[2]
        link_type = "belongs_to"
        if "--type" in args:
            idx = args.index("--type")
            if idx + 1 < len(args):
                link_type = args[idx + 1]
        _mcp_call("add_link", {"from": from_slug, "to": to_slug, "link_type": link_type})
    elif cmd == "get":
        slug = args[1]
        _mcp_call("get_page", {"slug": slug})
    else:
        raise subprocess.CalledProcessError(1, "gbrain-mcp", f"Unknown command: {cmd}")
    # Return a CompletedProcess-like result
    class FakeResult:
        returncode = 0
    return FakeResult()
# --- end bridge ---


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from memory_family_registry import active_focus_profiles, focus_profile_archive_tags, focus_profile_ids_for_text

# Config
AGENT_HOME = Path(os.environ.get("AGENT_HOME") or os.environ.get("HERMES_HOME", str(Path.home() / ".agent"))).expanduser()
SESSIONS_DIR = AGENT_HOME / "sessions"
STATE_DB = AGENT_HOME / "state.db"
CHECKPOINT_FILE = AGENT_HOME / ".session_to_gbrain_checkpoint.json"
CST = timezone(timedelta(hours=8))
SESSION_FILE_PATTERN = re.compile(r"(?:session|request_dump)_[^\"\\/\s]+\.json")

# Topic hubs - these are gbrain pages that group sessions by topic
TOPIC_HUBS = {
    "relationships": {
        "slug": "hub-relationships",
        "title": "Relationships Hub",
        "tags": ["relationships", "social"],
        "keywords": ["friend", "relationship", "social", "chat", "connection"]
    },
    "a-stock": {
        "slug": "hub-a-stock-trading",
        "title": "A股投资分析中枢",
        "tags": ["a-stock", "trading", "investment"],
        "keywords": ["A股", "stock", "HS300", "ZZ500", "推荐", "LightGBM", "止损", "因子", "hedge"]
    },
    "system": {
        "slug": "hub-system-operations",
        "title": "系统运维中枢",
        "tags": ["devops", "system", "hermes"],
        "keywords": ["config", "gateway", "cron", "api_key", "provider", "systemd", "docker", "pip install"]
    },
    "social": {
        "slug": "hub-social-media",
        "title": "社媒运营中枢",
        "tags": ["social-media", "douyin", "tiktok", "content"],
        "keywords": ["抖音", "douyin", "tiktok", "视频", "自媒体", "粉丝", "播放", "YouTube", "变现"]
    },
    "coding": {
        "slug": "hub-dev-coding",
        "title": "开发编程中枢",
        "tags": ["coding", "development", "programming"],
        "keywords": ["python", "git", "github", "代码", "deploy", "API", "skill", "tool", "script"]
    }
}


def merge_focus_profile_hubs(topic_hubs):
    merged = dict(topic_hubs)
    for profile_id, profile in active_focus_profiles().items():
        merged[profile_id] = {
            "slug": profile.get("slug") or f"hub-{profile_id}",
            "title": profile.get("title") or profile_id,
            "tags": list(profile.get("tags", ()) or (profile_id,)),
            "keywords": list(profile.get("keywords", ()) or profile.get("aliases", ())),
        }
    return merged


TOPIC_HUBS = merge_focus_profile_hubs(TOPIC_HUBS)

GBRAIN_BIN = shutil.which("gbrain") or os.environ.get("GBRAIN_BIN", "gbrain")


def load_checkpoint():
    """加载已处理会话列表"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                raw = f.read()
            recovered = sorted(set(SESSION_FILE_PATTERN.findall(raw)))
            corrupt_copy = f"{CHECKPOINT_FILE}.corrupt-{int(time.time())}"
            try:
                shutil.copy2(CHECKPOINT_FILE, corrupt_copy)
            except Exception:
                print(f"[session_to_gbrain] failed to backup corrupt checkpoint: {CHECKPOINT_FILE}", file=sys.stderr)
            return {
                "processed_sessions": recovered,
                "last_run": None,
                "recovered_from_corrupt_checkpoint": True,
            }
    return {"processed_sessions": [], "last_run": None}


def save_checkpoint(data):
    checkpoint_dir = os.path.dirname(CHECKPOINT_FILE) or "."
    with NamedTemporaryFile("w", delete=False, dir=checkpoint_dir, encoding='utf-8') as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.replace(tmp_path, CHECKPOINT_FILE)


def get_unprocessed_sessions(processed_set, batch_size=50):
    """获取未处理的新会话"""
    session_files = sorted(Path(SESSIONS_DIR).glob("*.json"), 
                          key=lambda p: p.stat().st_mtime, reverse=True)
    unprocessed = []
    for sf in session_files:
        if sf.name not in processed_set:
            unprocessed.append(sf)
            if len(unprocessed) >= batch_size:
                break
    return unprocessed


def _sanitize_session_json_text(text: str) -> str:
    cleaned_lines = []
    for line in text.splitlines():
        line = "".join(ch for ch in line if ord(ch) >= 32 or ch in "\n\r\t")
        line = line.replace("\ufffd", "")
        if '"' in line:
            last_quote = line.rfind('"')
            suffix = line[last_quote + 1 :]
            if suffix and not re.fullmatch(r"[\s,:{}\[\]]*", suffix):
                valid_suffix = "".join(ch for ch in suffix if ch in " \t,:{}[]")
                line = line[: last_quote + 1] + valid_suffix
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _load_session_payload(content: str):
    try:
        return json.loads(content), content, False
    except Exception:
        sanitized = _sanitize_session_json_text(content)
        return json.loads(sanitized), sanitized, True


def normalize_message_content(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                item_type = str(item.get("type") or "").lower()
                if item_type and item_type not in {"text", "input_text", "output_text"}:
                    continue
                text = normalize_message_content(item.get("text") or item.get("content"))
                if text:
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part and part.strip())
    if isinstance(value, dict):
        return normalize_message_content(value.get("text") or value.get("content") or value.get("value"))
    return ""


def extract_session_info(filepath: Path) -> dict:
    """从会话文件中提取关键信息"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        stat = filepath.stat()
        session_id = filepath.stem.replace("session_", "")
        
        # Try to parse as JSON
        messages = []
        title = ""
        try:
            data, cleaned_content, was_sanitized = _load_session_payload(content)
            if isinstance(data, list):
                messages = data
            elif isinstance(data, dict):
                messages = data.get("messages", data.get("history", []))
                title = data.get("title", "")
            if was_sanitized:
                filepath.with_suffix(filepath.suffix + ".repaired").write_text(cleaned_content, encoding='utf-8')
        except Exception as exc:
            print(f"[session_to_gbrain] unable to parse session {filepath.name}: {exc}", file=sys.stderr)
            return None
        
        # Extract first user message as title hint
        first_user_msg = ""
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                if role == "user":
                    first_user_msg = normalize_message_content(msg.get("content"))[:200]
                    break
        
        if not title and first_user_msg:
            title = first_user_msg.strip()[:100]
        if not title:
            title = f"Session {session_id[:12]}"
        
        # Count messages
        user_count = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
        assistant_count = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "assistant")
        
        # Detect topics by keyword matching
        content_lower = content.lower()
        topics = list(focus_profile_ids_for_text(content))
        for topic_key, hub in TOPIC_HUBS.items():
            if topic_key in topics:
                continue
            score = sum(content_lower.count(kw.lower()) for kw in hub["keywords"])
            if score > 10:
                topics.append(topic_key)
        
        # Generate summary (first 500 chars after cleaning)
        summary = ""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                c = normalize_message_content(msg.get("content"))
                if c:
                    summary = c[:500].strip()
                    break
        
        return {
            "session_id": session_id,
            "title": title,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=CST).isoformat(),
            "user_msgs": user_count,
            "assistant_msgs": assistant_count,
            "topics": topics,
            "summary": summary,
            "first_msg": first_user_msg[:200]
        }
    except Exception as e:
        return None


# ============================================================
# 中文实体关系提取（补充 gbrain 的英文 inferLinkType）
# ============================================================

CHINESE_RELATION_PATTERNS = None  # Built at module init


def _build_relation_patterns():
    """从已知实体列表构建关系匹配模式"""
    entity_names = sorted(set(_ALL_ENTITIES), key=len, reverse=True)
    ent_pat = "(" + "|".join(re.escape(e) for e in entity_names) + ")"

    return [
        (re.compile(ent_pat + r'\s*(?:投资|入股|领投|跟投)(?:了)?\s*' + ent_pat), "invested_in"),
        (re.compile(ent_pat + r'\s*(?:收购|并购|买入)(?:了)?\s*' + ent_pat), "acquired"),
        (re.compile(ent_pat + r'\s*(?:在|于)\s*' + ent_pat + r'\s*(?:工作|任职|担任|负责|从事)'), "works_at"),
        (re.compile(ent_pat + r'\s*(?:是|为)\s*' + ent_pat + r'\s*(?:的)?\s*(?:创始人|CEO|董事长|总裁|负责人)'), "leads"),
        (re.compile(ent_pat + r'\s*(?:开发|创建|创立|创办|搭建|做|写)(?:了)?\s*' + ent_pat), "created"),
        (re.compile(ent_pat + r'\s*(?:制作|生成|输出)(?:了)?\s*' + ent_pat), "authored"),
        (re.compile(ent_pat + r'\s*(?:使用|基于|依赖|用)(?:了)?\s*' + ent_pat), "uses"),
        (re.compile(ent_pat + r'\s*(?:参加|参与|出席|去)(?:了)?\s*' + ent_pat), "attended"),
        (re.compile(ent_pat + r'\s*(?:认识|见到|联系|见了|见)(?:了)?\s*' + ent_pat), "met"),
        (re.compile(ent_pat + r'\s*(?:辅导|指导|教|带)(?:了)?\s*' + ent_pat), "mentors"),
    ]


def _ensure_patterns():
    global CHINESE_RELATION_PATTERNS
    if CHINESE_RELATION_PATTERNS is None:
        CHINESE_RELATION_PATTERNS = _build_relation_patterns()


# 中文专名列表（用于辅助实体识别）
KNOWN_ENTITIES = {
    'person': ['Hermes'],
    'company': ['字节跳动', '抖音', '腾讯', '阿里巴巴', '百度', '华为', '小米', '美团',
                '宁德时代', '茅台', '比亚迪', 'OpenAI', 'Anthropic', 'Google'],
    'project': ['Hermes Agent', 'Hermes', 'gbrain', 'LightGBM', 'CodeX',
                'WeChat', 'v2raya', 'SearXNG'],
    'platform': ['抖音', 'TikTok', 'YouTube', '微信', 'Telegram', 'GitHub', 'Twitter', '小红书'],
    'venue': ['斑马', '斑马驻唱', '烟台', '车展'],
    'product': [],
}

# 构建专名正则（用于提取关系中的主体）
_ALL_ENTITIES = set()
for cat, entities in KNOWN_ENTITIES.items():
    _ALL_ENTITIES.update(entities)

# 按长度降序排列，避免短名匹配截断长名
_ALL_ENTITIES_SORTED = sorted(_ALL_ENTITIES, key=len, reverse=True)
_ENTITY_PATTERN = '|'.join(re.escape(e) for e in _ALL_ENTITIES_SORTED)


def extract_chinese_relations(text: str) -> list:
    """
    从中文文本中提取实体关系对。
    返回: [(source, relation_type, target, context), ...]
    
    使用两层匹配:
    1. 已知实体 + 关系动词模式匹配
    2. 同句共现实体（通用 related_to）
    """
    _ensure_patterns()
    relations = []
    
    # 第一层: 已知实体 + 关系动词模式
    for pattern, rel_type in CHINESE_RELATION_PATTERNS:
        for match in pattern.finditer(text):
            source = match.group(1).strip()
            target = match.group(2).strip()
            # 过滤过短或明显非实体的匹配
            if len(source) < 2 or len(target) < 2:
                continue
            # 过滤纯标点或数字
            if source.isdigit() or target.isdigit():
                continue
            ctx_start = max(0, match.start() - 20)
            ctx_end = min(len(text), match.end() + 20)
            context = text[ctx_start:ctx_end].replace('\n', ' ').strip()
            relations.append((source, rel_type, target, context))
    
    # 第二层: 已知实体相邻关系（通用关系: 'related_to'）
    # 查找文中同时出现的两个已知实体（在3句话内）
    # re already imported at module level
    entity_patterns = {e: re.compile(re.escape(e)) for e in _ALL_ENTITIES}
    sentences = re.split(r'[。！？\n]', text)
    
    for sent in sentences:
        found = []
        for ent_name, pat in entity_patterns.items():
            if pat.search(sent):
                found.append(ent_name)
        # 如果句子中包含多个已知实体且长度适中
        # 排除子串关系
        found = sorted(set(found), key=len, reverse=True)
        found = [e for e in found if not any(e != f and e in f for f in found)]
        if len(found) >= 2 and len(sent) < 500:
            for i in range(len(found)):
                for j in range(i+1, len(found)):
                    # 避免与第一层重复
                    pair = (found[i], found[j])
                    pair_rev = (found[j], found[i])
                    already_found = any(
                        (r[0] == pair[0] and r[2] == pair[1]) or
                        (r[0] == pair[1] and r[2] == pair[0])
                        for r in relations
                    )
                    if not already_found:
                        context = sent.strip()[:120]
                        relations.append((found[i], 'related_to', found[j], context))
    
    return relations


def render_wikilinks(text: str, relations: list, platform='gbrain') -> str:
    """将关系中的实体渲染为 wikilinks 追加到文本末尾"""
    if not relations:
        return text
    
    link_lines = []
    seen_pairs = set()
    for source, rel_type, target, context in relations:
        pair = (source, target)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        # 生成 wikilink 格式: [[source]] -- rel_type --> [[target]]
        link_lines.append(f'- [[{source}]] -- {rel_type} --> [[{target}]]')
    
    if link_lines:
        text += '\n\n## 关系提取\n\n'
        text += '\n'.join(link_lines)
    
    return text


def run_gbrain(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run gbrain via MCP API (CLI is broken due to embedding server)"""
    try:
        return run_gbrain_mcp(args, input_text=input_text)
    except Exception:
        # Fallback to CLI if MCP fails
        return subprocess.run(
            [GBRAIN_BIN, *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )


def ensure_gbrain_page(slug: str, content: str, tags: list[str], *, timeline_entry: tuple[str, str] | None = None) -> bool:
    """Persist a page into gbrain and attach metadata idempotently."""
    try:
        run_gbrain(["put", slug], input_text=content)
        for tag in sorted({tag.strip() for tag in tags if tag and tag.strip()}):
            run_gbrain(["tag", slug, tag])
        if timeline_entry:
            date_value, text_value = timeline_entry
            run_gbrain(["timeline-add", slug, date_value, text_value])
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"[session_to_gbrain] gbrain command failed for slug={slug}: {exc}", file=sys.stderr)
        return False


def ensure_gbrain_link(from_slug: str, to_slug: str, *, link_type: str = "belongs_to") -> None:
    if not from_slug or not to_slug or from_slug == to_slug:
        return
    try:
        run_gbrain(["link", from_slug, to_slug, "--type", link_type])
    except subprocess.CalledProcessError as exc:
        print(f"[session_to_gbrain] gbrain link failed {from_slug} -> {to_slug}: {exc}", file=sys.stderr)


def gbrain_page_exists(slug: str) -> bool:
    try:
        run_gbrain(["get", slug])
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def create_gbrain_page(info: dict, dry_run=False):
    """通过 MCP 创建 gbrain 页面"""
    slug = f"session-{info['session_id'][:16]}"
    raw_title = str(info.get("title") or "")[:100]
    display_title = " ".join(raw_title.split())
    
    # Build page content
    tags = ["session", f"date-{info['created_at'][:10]}"] + info["topics"]
    tags.extend(focus_profile_archive_tags(info.get('summary', ''), info.get('first_msg', ''), info.get('title', '')))
    tags_str = ", ".join(tags)
    
    # 提取中文实体关系
    # re already imported at module level
    session_text = f"{info['summary'][:800]} {info['first_msg'][:300]} {info['title']}"
    relations = extract_chinese_relations(session_text)
    
    content = f"""---
title: {json.dumps(raw_title, ensure_ascii=False)}
type: session
tags: [{tags_str}]
created: "{info['created_at']}"
---

# {display_title}

**会话ID**: {info['session_id']}
**日期**: {info['created_at'][:10]}
**消息数**: 用户{info['user_msgs']} + Hermes{info['assistant_msgs']}
**大小**: {info['size']/1024:.1f} KB
**主题**: {', '.join(info['topics']) if info['topics'] else '未分类'}

## 摘要

{info['summary'][:800] if info['summary'] else '（无摘要）'}

## 首条消息

{info['first_msg'][:300]}
"""
    
    # 追加关系 wikilinks
    if relations:
        link_lines = []
        seen_pairs = set()
        for source, rel_type, target, context in relations:
            pair = (source, target)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            link_lines.append(f'- [[{source}]] -- {rel_type} --> [[{target}]]')
        if link_lines:
            content += '\n\n## 关系提取\n\n'
            content += '\n'.join(link_lines)
    
    if dry_run:
        print(f"  [DRY-RUN] Would create: {slug}")
        return slug
    
    timeline_text = info['summary'][:180] if info.get('summary') else info['first_msg'][:180]
    persisted = ensure_gbrain_page(
        slug,
        content,
        tags,
        timeline_entry=(info['created_at'][:10], timeline_text) if timeline_text else None,
    )
    return slug if persisted else None


def create_topic_hubs(dry_run=False, refresh=False):
    """创建主题中枢页面"""
    for topic_key, hub in TOPIC_HUBS.items():
        slug = hub["slug"]
        content = f"""---
title: "{hub['title']}"
type: hub
tags: [{', '.join(hub['tags'])}]
---

# {hub['title']}

本页是「{hub['title']}」相关所有会话和档案的**索引中枢**。

## 关联关键词

{', '.join(hub['keywords'])}

## 关联会话

<!-- 会话链接由 session_to_gbrain.py 自动维护 -->

## 关联档案

<!-- 手动或自动添加 -->
"""
        
        if dry_run:
            print(f"  [DRY-RUN] Would create hub: {slug}")
        else:
            if not refresh and gbrain_page_exists(slug):
                continue
            ensure_gbrain_page(slug, content, hub["tags"])
    
    return list(TOPIC_HUBS.keys())


def link_session_to_hubs(session_slug, topics, dry_run=False):
    """将会话链接到主题中枢"""
    links = []
    for topic in topics:
        if topic in TOPIC_HUBS:
            hub_slug = TOPIC_HUBS[topic]["slug"]
            links.append((session_slug, hub_slug))
    
    if dry_run:
        for s, h in links:
            print(f"  [DRY-RUN] Link: {s} → {h}")
    
    if not dry_run:
        for s, h in links:
            ensure_gbrain_link(s, h)
    return links


def main():
    dry_run = "--dry-run" in sys.argv
    batch_size = 50
    
    for arg in sys.argv:
        if arg.startswith("--batch="):
            batch_size = int(arg.split("=")[1])
    
    cp = load_checkpoint()
    processed = set(cp.get("processed_sessions", []))
    
    print(f"📋 Session→Gbrain Pipeline")
    print(f"   Processed: {len(processed)} | Batch size: {batch_size} | Dry-run: {dry_run}")
    
    # Step 1: Ensure topic hubs exist
    print(f"\n🔧 Step 1: Topic Hubs")
    create_topic_hubs(dry_run=dry_run)
    
    # Step 2: Get unprocessed sessions
    unprocessed = get_unprocessed_sessions(processed, batch_size)
    print(f"\n📂 Step 2: Found {len(unprocessed)} new sessions")
    
    if not unprocessed:
        print("   ✅ No new sessions. Done.")
        cp["last_run"] = datetime.now(CST).isoformat()
        save_checkpoint(cp)
        return 0
    
    # Step 3: Process sessions
    results = {"created": 0, "skipped": 0, "errors": 0}
    
    for i, sf in enumerate(unprocessed):
        info = extract_session_info(sf)
        if not info:
            results["errors"] += 1
            continue
        
        slug = create_gbrain_page(info, dry_run=dry_run)
        if dry_run:
            results["created"] += 1
            continue
        if slug:
            results["created"] += 1
            if info["topics"]:
                link_session_to_hubs(slug, info["topics"], dry_run=dry_run)
            processed.add(sf.name)
        else:
            results["errors"] += 1
        
        if (i + 1) % 10 == 0:
            print(f"   ... {i+1}/{len(unprocessed)}")
    
    # Save checkpoint
    cp["processed_sessions"] = list(processed)
    cp["last_run"] = datetime.now(CST).isoformat()
    save_checkpoint(cp)
    
    print(f"\n📊 Results: {results['created']} created, {results['skipped']} skipped, {results['errors']} errors")
    print(f"✅ Done. Next batch starts from checkpoint.")
    return 1 if results["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
