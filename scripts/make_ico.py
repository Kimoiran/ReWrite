"""将 icon.png 转为 icon.ico（嵌入 exe 用）。"""
import struct, zlib, io
from pathlib import Path

def png_to_ico(png_path: Path, ico_path: Path, sizes=None):
    """PNG 转 ICO（Windows 图标格式）。"""
    if sizes is None:
        sizes = [256]
    png_data = png_path.read_bytes()

    # ICO 文件结构
    buf = io.BytesIO()
    # Header
    buf.write(struct.pack('<HHH', 0, 1, len(sizes)))  # reserved, type=1(ico), count

    offset = 6 + 16 * len(sizes)  # header + dir entries
    for size in sizes:
        # 目录项
        w = size if size < 256 else 0
        h = size if size < 256 else 0
        buf.write(struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(png_data), offset))
        offset += len(png_data)

    # 写入 PNG 数据
    buf.write(png_data)

    ico_path.write_bytes(buf.getvalue())
    print(f"ICO saved: {ico_path} ({ico_path.stat().st_size} bytes)")

if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    png_path = base / "assets" / "icon.png"
    ico_path = base / "assets" / "icon.ico"
    png_to_ico(png_path, ico_path)
