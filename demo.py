"""
Mini Agent Runtime — Interview Demo

一键运行，展示 Agent 的三种核心能力。
适合在面试或简历展示中快速演示项目。

Usage:
    python demo.py
"""

import sys
import io
import time

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.llm import LLMClient
from core.agent import Agent


BANNER = """
╔══════════════════════════════════════════════════╗
║         Mini Agent Runtime — Interview Demo      ║
║     Plan → Execute → Reflect  Agent Loop        ║
╚══════════════════════════════════════════════════╝
"""

SEPARATOR = "─" * 55

DEMOS = [
    {
        "id": "1",
        "title": "纯推理场景",
        "subtitle": "Planner + Executor 基本链路",
        "task": "用中文写一首关于人工智能的短诗，不超过50字",
        "note": "不依赖工具，纯 LLM 推理，速度最快",
    },
    {
        "id": "2",
        "title": "搜索 + 整合场景",
        "subtitle": "Web 搜索 + 多步骤协作",
        "task": "搜索2025年最热门的3个AI编程工具，列出它们的名称和主要特点",
        "note": "搜索获取实时信息 → LLM 整合分析",
    },
    {
        "id": "3",
        "title": "完整工作流场景",
        "subtitle": "搜索 → 分析 → 文件输出 + 反思",
        "task": "搜索2025年AI领域的重要突破，整理成3个要点，保存到 output/ai_breakthroughs_2025.md",
        "note": "展示 Plan → Execute → Reflect 完整闭环",
    },
]


def print_header(text: str):
    print(f"\n{SEPARATOR}")
    print(f"  {text}")
    print(SEPARATOR)


def run_demo(demo: dict):
    """Run a demo scenario."""
    print(f"\n{'=' * 55}")
    print(f"  Demo {demo['id']}: {demo['title']}")
    print(f"  {demo['subtitle']}")
    print(f"  → {demo['note']}")
    print(f"{'=' * 55}\n")

    print(f"  [Task] {demo['task']}\n")

    # Confirm before running
    input("  按 Enter 开始执行（或 Ctrl+C 取消）...")

    print()
    start = time.time()

    llm = LLMClient()
    agent = Agent(llm)
    result = agent.run(demo["task"])

    elapsed = time.time() - start

    # Show summary
    print(f"\n{'=' * 55}")
    print(f"  ✅ Demo {demo['id']} 完成")
    print(f"  执行步骤: {result['steps_executed']}")
    print(f"  反思轮数: {result['reflection_rounds']}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"{'=' * 55}\n")

    return result


def show_menu() -> str:
    """Show demo selection menu."""
    print(BANNER)
    print("  选择要运行的 Demo:\n")
    for d in DEMOS:
        print(f"    [{d['id']}] {d['title']}")
        print(f"        {d['subtitle']}")
        print(f"        任务: {d['task']}")
        print()
    print("    [a] 全部运行")
    print("    [q] 退出\n")

    choice = input("  请输入选择 [1/2/3/a/q]: ").strip().lower()
    return choice


def main():
    while True:
        choice = show_menu()

        if choice == "q":
            print("\n  再见！\n")
            break

        if choice == "a":
            for d in DEMOS:
                run_demo(d)
                input("\n  按 Enter 继续下一个 Demo...")
            print("\n  🎉 所有 Demo 执行完成！\n")
            break

        for d in DEMOS:
            if choice == d["id"]:
                run_demo(d)
                print("\n  按 Enter 返回菜单...", end="")
                input()
                break
        else:
            print(f"\n  无效选择: {choice}\n")
            input("  按 Enter 继续...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  已退出。\n")
