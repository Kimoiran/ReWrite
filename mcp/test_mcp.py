"""快速测试 MCP 服务器。"""
import subprocess, json, sys, os

server_path = os.path.join(os.path.dirname(__file__), "server.py")
proc = subprocess.Popen(
    [sys.executable, server_path],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, bufsize=1,
)

def send(msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    resp = proc.stdout.readline()
    return json.loads(resp)

# 初始化
r = send({"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1})
print("初始化:", "OK" if "result" in r else "FAIL")

# 列出工具
r = send({"jsonrpc": "2.0", "method": "tools/list", "id": 2})
tools = r["result"]["tools"]
print(f"工具数: {len(tools)}")
for t in tools[:5]:
    print(f"  - {t['name']}")

# 列出作品
r = send({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "list_works", "arguments": {}}, "id": 3})
result = json.loads(r["result"]["content"][0]["text"])
print(f"作品数: {len(result)}")
for w in result:
    print(f"  - {w['title']} ({w['type']})")

proc.kill()
print("MCP 测试通过!")
