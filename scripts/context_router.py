#!/usr/bin/env python3
"""
Hermes Memory Installer - 上下文路由器
【核心创新】

原理：
1. 分析最近 N 条对话，提取关键词
2. 在档案库 FTS5 中检索匹配的档案
3. 将匹配档案的摘要写入 memory（临时注入）
4. 下一轮对话时，Hermes 自动通过原生 memory 机制获取这些摘要

优势：不需要修改 Hermes 核心，利用已有的 memory 注入机制。
局限：延迟 1 轮对话（当前分析上一轮的内容）。
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ArchiveMatch:
    """档案匹配结果"""
    path: str
    title: str
    summary: str
    score: float        # BM25 相关性得分
    priority: int


class ContextRouter:
    """上下文路由器"""
    
    def __init__(self, db_path: str = None, archives_dir: str = None):
        self.db_path = db_path or str(Path.home() / ".hermes" / "pool.db")
        self.archives_dir = archives_dir or str(Path.home() / ".hermes" / "archives")
    
    def extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 简化版：提取 2~10 个字的中文/英文词组
        # 真实实现可以接入 LLM 做 NER
        words = re.findall(r'[\u4e00-\u9fff]{2,10}|[a-zA-Z]{2,20}', text)
        return list(set(words))[:10]  # 去重，最多 10 个
    
    def search_archives(self, keywords: List[str], limit: int = 3) -> List[ArchiveMatch]:
        """在档案库中检索相关档案"""
        if not keywords:
            return []
        
        query = " OR ".join(keywords)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT a.path, a.title, a.summary, a.priority,
                   rank AS score
            FROM archives_fts
            JOIN archives a ON archives_fts.rowid = a.id
            WHERE archives_fts MATCH ?
            ORDER BY bm25(archives_fts) ASC, a.priority DESC
            LIMIT ?
        """, (query, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append(ArchiveMatch(
                path=row[0],
                title=row[1],
                summary=row[2] or "",
                score=row[4] or 0.0,
                priority=row[3] or 0
            ))
        
        conn.close()
        return results
    
    def generate_memory_entries(self, matches: List[ArchiveMatch]) -> List[str]:
        """生成临时 memory 条目"""
        entries = []
        for match in matches:
            entry = f"[档案: {match.title}] {match.summary[:200]}"
            entries.append(entry)
        return entries
    
    def route(self, recent_messages: List[Dict]) -> List[str]:
        """主入口：接收最近对话，返回应该注入的 memory 条目"""
        # 1. 合并最近消息
        text = " ".join([msg.get("content", "") for msg in recent_messages])
        
        # 2. 提取关键词
        keywords = self.extract_keywords(text)
        
        # 3. 检索档案
        matches = self.search_archives(keywords)
        
        # 4. 生成 memory 条目
        entries = self.generate_memory_entries(matches)
        
        return entries
    
    def sync_to_memory(self, entries: List[str]) -> bool:
        """将条目写入 memory（调用 hermes_tools.memory）"""
        # 注：这是在 Hermes 会话内执行的脚本
        # 在独立运行时需要通过 API 或文件方式写入
        
        try:
            from hermes_tools import memory
            for entry in entries:
                memory(action="add", target="memory", content=entry)
            return True
        except ImportError:
            # 回退：写入临时文件，下次对话时读取
            temp_file = Path.home() / ".hermes" / "archives" / "_pending_memory.json"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 写入 memory 失败: {e}")
            return False


def main():
    """独立运行示例"""
    router = ContextRouter()
    
    # 模拟最近对话
    recent = [
        {"role": "user", "content": "Alice 最近怎么样了？"},
    ]
    
    entries = router.route(recent)
    print(f"检索到 {len(entries)} 条相关档案:")
    for entry in entries:
        print(f"  → {entry[:80]}...")


if __name__ == "__main__":
    main()
