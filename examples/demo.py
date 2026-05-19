"""Demo script — run example tasks through the Mini Agent Runtime."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLMClient
from core.agent import Agent


DEMO_TASKS = [
    "读取当前目录下的 requirements.txt 文件，总结其中的依赖，写入 output/demo_result.md",
]

if __name__ == "__main__":
    llm = LLMClient()
    agent = Agent(llm)

    for task in DEMO_TASKS:
        print(f"\n{'#'*60}")
        print(f"# Demo Task: {task}")
        print(f"{'#'*60}")
        agent.run(task)
