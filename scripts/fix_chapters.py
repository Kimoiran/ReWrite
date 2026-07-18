"""修复章节文件：合并 toMarkdown() 迁移导致的不自然断行。"""
import re
from pathlib import Path

works_dir = Path("works/novel-新生神明与实习教皇/chapters")

for md_path in sorted(works_dir.glob("*.md")):
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    fixed = []
    pending = ""

    for line in lines:
        stripped = line.rstrip()
        # 空行 → 刷新当前段落
        if not stripped:
            if pending:
                fixed.append(pending.rstrip())
                pending = ""
            fixed.append("")
            continue
        # 标题行：保留原样
        if stripped.startswith("#"):
            if pending:
                fixed.append(pending.rstrip())
                pending = ""
            fixed.append(stripped)
            continue
        # 已有 pending：判断是否续接上一行
        if pending:
            # 上一行以句末标点结束 → 断开，另起段落
            if re.search(r"[。！？）」\"'）\)]$", pending.rstrip()):
                fixed.append(pending.rstrip())
                pending = stripped
            else:
                # 续接：直接拼（中间无空格）
                pending = pending.rstrip() + stripped
        else:
            pending = stripped

    if pending:
        fixed.append(pending.rstrip())

    result = "\n".join(fixed)
    # 清理过多连续空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    # 确保末尾有换行
    if not result.endswith("\n"):
        result += "\n"

    md_path.write_text(result, encoding="utf-8")
    print(f"{md_path.name}: {len(text.splitlines())} -> {len(result.splitlines())} lines")
