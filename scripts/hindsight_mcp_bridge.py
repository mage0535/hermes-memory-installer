#!/usr/bin/env python3
"""Lightweight MCP stdio bridge for Hindsight REST API (port 8890).
No second Hindsight instance needed — wraps existing API via HTTP calls."""
import json, os, sys, urllib.request, urllib.error, traceback

HINDSIGHT = os.environ.get("HINDSIGHT_BASE_URL", "http://127.0.0.1:8890")
BANK = os.environ.get("HINDSIGHT_BANK", "hermes")

def jsonrpc(req_id, method, params):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def call_api(method, path, body=None):
    url = f"{HINDSIGHT}/v1/default/banks/{BANK}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    if method == "POST":
        req.method = "POST"
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)}

TOOLS = [
    {
        "name": "hindsight_retain",
        "description": "Store a memory/experience in Hindsight. Best for conversation events, experiences, entity interactions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The memory content to store"},
                "context": {"type": "string", "description": "Optional context label"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "hindsight_recall",
        "description": "Semantic recall from Hindsight memory store. Returns ranked relevant memories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_tokens": {"type": "integer", "description": "Max tokens in results", "default": 1024}
            },
            "required": ["query"]
        }
    },
    {
        "name": "hindsight_reflect",
        "description": "Deep reasoning: synthesizes info from experiences, world facts, and opinions. Use for complex cross-memory questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question to reflect on"},
                "max_tokens": {"type": "integer", "description": "Max tokens in result", "default": 2048}
            },
            "required": ["query"]
        }
    },
    {
        "name": "hindsight_entities",
        "description": "List all known entities tracked by Hindsight.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max entities", "default": 20}
            }
        }
    },
    {
        "name": "hindsight_stats",
        "description": "Get Hindsight memory bank statistics.",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

req_id = 1
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue

    method = msg.get("method", "")
    params = msg.get("params", {})
    rid = msg.get("id", req_id)
    req_id += 1

    if method == "tools/list":
        jsonrpc(rid, "tools/list", {"result": {"tools": TOOLS}})
        continue

    if method == "tools/call":
        tool = params.get("name", "")
        args = params.get("arguments", {})

        try:
            if tool == "hindsight_retain":
                result = call_api("POST", "/memories", {
                    "items": [{"content": args["content"], "context": args.get("context", "")}]
                })
                jsonrpc(rid, "result", {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})

            elif tool == "hindsight_recall":
                result = call_api("POST", "/memories/recall", {
                    "query": args["query"],
                    "max_tokens": args.get("max_tokens", 1024)
                })
                texts = [r["text"] for r in result.get("results", [])]
                jsonrpc(rid, "result", {"content": [{"type": "text", "text": json.dumps(texts, indent=2, ensure_ascii=False)}]})

            elif tool == "hindsight_reflect":
                result = call_api("POST", "/reflect", {
                    "query": args["query"],
                    "max_tokens": args.get("max_tokens", 2048)
                })
                jsonrpc(rid, "result", {"content": [{"type": "text", "text": result.get("text", "")}]})

            elif tool == "hindsight_entities":
                result = call_api("GET", f"/entities?limit={args.get('limit', 20)}")
                jsonrpc(rid, "result", {"content": [{"type": "text", "text": json.dumps(result.get("items", []), indent=2, ensure_ascii=False)}]})

            elif tool == "hindsight_stats":
                result = call_api("GET", "/stats")
                jsonrpc(rid, "result", {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})

            else:
                jsonrpc(rid, "result", {"content": [{"type": "text", "text": f"Unknown tool: {tool}"}], "isError": True})
        except Exception as e:
            jsonrpc(rid, "result", {"content": [{"type": "text", "text": traceback.format_exc()}], "isError": True})

    elif method == "initialize":
        jsonrpc(rid, "initialized", {})

    elif method == "notifications/initialized":
        pass  # ok
