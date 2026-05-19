"""
模拟测试模式 —— 不依赖真实 API，模拟 LLM 回复来验证 Agent 逻辑。

跑这个脚本：
    python test_mock.py

你会看到完整的 Agent 执行流程，但不花一分钱。
"""

import sys
import os
import json

# 确保能引入 core 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tool_system import ToolRegistry
from core.planner import Planner
from core.executor import Executor
from core.reflector import Reflector
from core.agent import Agent
from tools.file_tools import ReadFileTool, WriteFileTool


class MockLLM:
    """模拟 LLM —— 返回预设回复，不调 API。"""

    def __init__(self):
        self.call_count = 0  # 记录调用次数，帮助你理解每一步谁调了 LLM

    def chat(self, messages, temperature=0.3):
        self.call_count += 1
        # 从消息里提取任务关键词，模拟不同回复
        last_msg = messages[-1]["content"] if messages else ""

        if "quality checker" in last_msg or "complete" in last_msg:
            # Reflector 调用 —— 返回检查结果
            return json.dumps({"complete": True, "reason": "All required steps executed successfully."})
        elif "execute a single step" in last_msg or "step executor" in last_msg:
            # Executor 调用 —— 模拟执行结果
            return f"[Mock] Successfully processed step. Output: analysis complete."
        else:
            # Planner 或其他 —— 返回模拟计划
            return json.dumps({
                "task_summary": "模拟任务：读取文件并总结",
                "steps": [
                    {"step_id": 1, "action": "读取 requirements.txt 文件", "tool": "read_file", "tool_args": {"path": "requirements.txt"}},
                    {"step_id": 2, "action": "分析读取到的内容并生成总结", "tool": "null", "tool_args": {}},
                    {"step_id": 3, "action": "将总结写入结果文件", "tool": "write_file", "tool_args": {"path": "output/mock_result.md", "content": "$prev_result"}},
                ]
            })

    def chat_json(self, messages, temperature=0.1):
        result = self.chat(messages, temperature)
        # 移除代码 fence（兼容真实 LLM 行为）
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[-1]
            result = result.rsplit("```", 1)[0]
        return json.loads(result.strip())


def test_agent_flow():
    """模拟完整 Agent 执行流程，逐步骤打印，展示内部运转。"""
    print("=" * 60)
    print("  Mini Agent Runtime — 模拟测试模式")
    print("  不依赖真实 API，验证逻辑链路")
    print("=" * 60)

    # 创建模拟 LLM
    mock_llm = MockLLM()

    # 创建 Agent（传入模拟 LLM）
    agent = Agent(llm=mock_llm)

    # 运行测试任务
    task = "读取 requirements.txt 并总结内容"
    print(f"\n[INPUT] 任务: {task}\n")

    result = agent.run(task)

    # 输出总体结果
    print("\n" + "=" * 60)
    print(" 执行结果总览")
    print("=" * 60)
    print(f"  任务: {result['task']}")
    print(f"  执行步骤数: {result['steps_executed']}")
    print(f"  LLM 调用次数: {mock_llm.call_count}")
    print(f"  Reflection 轮数: {result.get('reflection_rounds', 0)}")
    print(f"  总结: {result['summary']}")

    print("\n[PASS] 模拟测试通过！逻辑链路正常。")
    print("  下一步可以切到真实 LLM 正式运行。")
    print("  命令: python main.py \"你的任务\"")


if __name__ == "__main__":
    test_agent_flow()
