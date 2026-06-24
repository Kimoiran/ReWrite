#!/usr/bin/env python
"""ReWrite MCP 服务器 — 使用共享工具库。"""

import json
import sys

# 从共享模块导入工具
sys.path.insert(0, __file__.rsplit("/", 2)[0] if "/" in __file__ else __file__.rsplit("\\", 2)[0])
from mcp.tools import TOOL_FUNCTIONS


def send(msg: dict):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def read() -> dict:
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return json.loads(line)


def _build_schema(name: str) -> dict:
    schemas = {
        "list_works": {},
        "get_characters": {"work": {"type": "string"}},
        "create_character": {"work": {"type": "string"}, "name": {"type": "string"}},
        "update_character": {"work": {"type": "string"}, "name": {"type": "string"}, "field": {"type": "string"}, "value": {"type": "string"}},
        "add_group": {"work": {"type": "string"}, "name": {"type": "string"}},
        "get_outline": {"work": {"type": "string"}},
        "update_outline_entry": {"work": {"type": "string"}, "name": {"type": "string"}, "field": {"type": "string"}, "value": {"type": "string"}},
        "get_timeline": {"work": {"type": "string"}},
        "update_timeline_event": {"work": {"type": "string"}, "title": {"type": "string"}, "field": {"type": "string"}, "value": {"type": "string"}},
        "get_worldview": {"work": {"type": "string"}},
        "create_worldview_entry": {"work": {"type": "string"}, "title": {"type": "string"}},
        "get_chapters": {"work": {"type": "string"}},
        "read_chapter": {"work": {"type": "string"}, "path": {"type": "string"}},
    }
    s = schemas.get(name, {})
    return {"type": "object", "properties": {k: {"type": v["type"]} for k, v in s.items()},
            "required": ["work"] if s else []}


def main():
    while True:
        try:
            msg = read()
        except json.JSONDecodeError:
            continue
        except Exception:
            break

        mid = msg.get("id")

        if msg.get("method") == "initialize":
            send({"jsonrpc": "2.0", "result": {
                "protocolVersion": "0.1.0",
                "serverInfo": {"name": "rewrite-mcp", "version": "1.0.0"},
                "capabilities": {
                    "tools": {n: {"description": f"ReWrite tool"} for n in TOOL_FUNCTIONS}
                }
            }, "id": mid})

        elif msg.get("method") == "tools/list":
            tools = [{"name": n, "description": f"ReWrite: {n}", "inputSchema": _build_schema(n)}
                     for n in TOOL_FUNCTIONS]
            send({"jsonrpc": "2.0", "result": {"tools": tools}, "id": mid})

        elif msg.get("method") == "tools/call":
            name = msg.get("params", {}).get("name", "")
            args = msg.get("params", {}).get("arguments", {})
            fn = TOOL_FUNCTIONS.get(name)
            if fn:
                try:
                    result = fn(args)
                    text = json.dumps(result, ensure_ascii=False, indent=2)
                    send({"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": text}]}, "id": mid})
                except Exception as e:
                    send({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": mid})
            else:
                send({"jsonrpc": "2.0", "error": {"code": -32601, "message": f"未知: {name}"}, "id": mid})

        else:
            send({"jsonrpc": "2.0", "result": {}, "id": mid})


if __name__ == "__main__":
    main()
