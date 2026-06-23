"""使用 spec 打包 exe（嵌入图标）。"""
import subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent

result = subprocess.run(
    [sys.executable, "-m", "PyInstaller", str(root / "ReWrite.spec")],
    cwd=root,
    capture_output=True, text=True, timeout=300,
)
for line in result.stdout.split("\n"):
    if "INFO:" in line and ("completed" in line or "Building" in line or "EXE" in line):
        print(line)
if result.returncode != 0:
    for line in result.stderr.split("\n"):
        if "Error" in line or "error" in line:
            print(line)
print(f"Exit code: {result.returncode}")
