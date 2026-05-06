#!/usr/bin/env python3
"""gbrain 会话并发检索工具 — Memory 2.0

支持同时对 gbrain 进行混合搜索（向量+关键词），
返回结构化结果供 Hermes 上下文注入。

Usage:
  python3 gbrain_search.py "查询关键词"
  python3 gbrain_search.py "查询" --limit 5 --expand
  python3 gbrain_search.py "查询" --source telegram
"""
import argparse, json, subprocess, sys, time

def gbrain_query(query: str, limit: int = 5, expand: bool = True,
                 source: str = None, detail: str = "medium"):
    """调用 gbrain MCP 进行混合搜索"""
    params = {
        "query": query,
        "limit": limit,
        "detail": detail,
        "expand": expand
    }
    if source:
        params["lang"] = source

    try:
        cmd = ["gbrain", "call", "query", json.dumps(params)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout.strip() else []
        else:
            print(f"[ERROR] gbrain query failed: {result.stderr[:200]}", file=sys.stderr)
            return []
    except subprocess.TimeoutExpired:
        print("[ERROR] gbrain query timed out", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON from gbrain: {result.stdout[:200]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return []

def search_concurrent(queries: list, limit_per: int = 3):
    """并发搜索多个查询"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(gbrain_query, q, limit_per): q for q in queries}
        for future in as_completed(futures):
            q = futures[future]
            try:
                results[q] = future.result(timeout=35)
            except Exception as e:
                results[q] = []
    return results

def format_results(results: list, max_per_source: int = 3) -> str:
    """格式化搜索结果为可读文本"""
    if not results:
        return "未找到相关记录。"
    lines = [f"在 gbrain 知识图谱中找到 {len(results)} 条相关记录：\\n"]
    count = 0
    for r in results:
        if count >= max_per_source:
            break
        title = r.get('title', 'Untitled')
        summary = r.get('summary', '')[:200]
        slug = r.get('slug', '')
        score = r.get('score', 0)
        lines.append(f"  {count+1}. **{title}** (匹配度: {float(score):.0%})")
        if summary:
            lines.append(f"     {summary}")
        lines.append("")
        count += 1
    return "\\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description='gbrain 搜索')
    parser.add_argument('query', nargs='?', help='搜索关键词')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--no-expand', action='store_false', dest='expand')
    parser.add_argument('--source', help='过滤来源 (telegram/cli/cron)')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    args = parser.parse_args()

    if not args.query:
        print("用法: python3 gbrain_search.py <查询词> [--limit 5] [--source telegram]")
        sys.exit(1)

    results = gbrain_query(args.query, args.limit, args.expand, args.source)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results(results))

if __name__ == '__main__':
    main()
