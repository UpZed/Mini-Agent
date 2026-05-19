"""Mini Agent Runtime — Entry point.

Usage:
    python main.py              # 运行 TASK 变量中的任务
    python main.py "your task"  # 直接传参
    python main.py --interactive # 交互模式
"""

import sys
import json
import io
import subprocess

# ═══════════════════════════════════════════════════
# 【在这里输入你的需求】
TASK = "搜索 2026 年最值得关注的 5 个Agent工具，给出每个项目的名称、GitHub star数、主要功能，以及它们分别解决了什么问题。然后对比分析它们的优劣，最后把结果保存到 output/agent_2026.md。"
# ═══════════════════════════════════════════════════

# Windows GBK 终端编码修补
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.llm import LLMClient
from core.agent import Agent


def _beep():
    """任务完成提示音（Windows 兼容）。"""
    try:
        subprocess.run(
            ["powershell", "-c", "[System.Console]::Beep(880, 200)"],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass  # 响不了就算了


def run_task(task: str, output_path: str = "output/result.md"):
    """Run a single task through the agent and save the result."""
    llm = LLMClient()
    agent = Agent(llm)
    result = agent.run(task)

    # Save result
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent Execution Result\n\n")
        f.write(f"**Task:** {result['task']}\n\n")
        f.write(f"**Steps executed:** {result['steps_executed']}\n\n")
        f.write("---\n\n")
        f.write(result["log"])

    print(f"\n{'='*60}")
    print(f"[Done] Result saved to {output_path}")
    print(f"{'='*60}")
    _beep()
    return result


def interactive_mode():
    """Run in interactive loop mode."""
    print("Mini Agent Runtime — Interactive Mode")
    print("Type 'exit' to quit, 'save <path>' to save the last result.\n")

    llm = LLMClient()
    agent = Agent(llm)
    last_result = None

    while True:
        task = input(">>> ").strip()
        if not task:
            continue
        if task.lower() in ("exit", "quit"):
            break
        if task.lower().startswith("save "):
            if last_result:
                path = task[5:].strip()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(last_result["log"])
                print(f"Saved to {path}")
            else:
                print("No result to save.")
            continue

        last_result = agent.run(task)
        _beep()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    elif len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        run_task(task)
    else:
        run_task(TASK)
