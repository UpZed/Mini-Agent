"""开发日志自动记录工具。

用法:
    python -m tools.dev_logger "条目标题" "条目内容(多行用\n分隔)"
    python -m tools.dev_logger --section "section标题" --title "条目标题" --content "条目内容"

自动在桌面的 Mini-Agent-Runtime_开发日志.md 中追加记录。
"""

import sys
import os
from datetime import datetime


DEV_LOG_PATH = os.path.expanduser(
    "~/Desktop/Mini-Agent-Runtime_开发日志.md"
)


def append_entry(title: str, content: str, section: str = None):
    """追加一条记录到开发日志。"""
    if not os.path.exists(DEV_LOG_PATH):
        print(f"[dev_logger] Error: Dev log not found at {DEV_LOG_PATH}")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry_lines = [f"\n### {timestamp} — {title}\n"]

    if section:
        entry_lines.insert(0, f"\n## {section}\n")

    for line in content.split("\\n"):
        entry_lines.append(f"\n{line}" if line.strip() else "\n")

    entry_text = "".join(entry_lines)

    try:
        with open(DEV_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry_text)
        print(f"[dev_logger] OK 已记录: {title[:40]}{'...' if len(title) > 40 else ''}")
        return True
    except Exception as e:
        print(f"[dev_logger] Error writing to dev log: {e}")
        return False


def list_recent(limit: int = 5):
    """列出最近的日志条目。"""
    if not os.path.exists(DEV_LOG_PATH):
        print(f"[dev_logger] Dev log not found at {DEV_LOG_PATH}")
        return

    with open(DEV_LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    entries = content.split("### ")
    entries = [e.strip() for e in entries if e.strip() and len(e) > 20]

    print(f"[dev_logger] 最近 {min(limit, len(entries))} 条记录:")
    for entry in entries[-limit:]:
        first_line = entry.split("\n")[0][:60]
        print(f"  - {first_line}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="开发日志记录工具")
    parser.add_argument("title", nargs="?", help="记录标题")
    parser.add_argument("content", nargs="?", help="记录内容（用 \\n 换行）")
    parser.add_argument("--section", help="所属章节")
    parser.add_argument("--list", action="store_true", help="列出最近记录")

    args = parser.parse_args()

    if args.list:
        list_recent()
    elif args.title and args.content:
        append_entry(args.title, args.content, args.section)
    else:
        print(__doc__)
