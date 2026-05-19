"""Planner module - decomposes a natural language task into a structured plan."""

import json
from core.llm import LLMClient
from core.tool_system import ToolRegistry


PLANNER_PROMPT = """You are a task planner for an AI Agent system. Your job is to break down a user's task into a clear, sequential plan.

Available tools (name, description, and expected parameters):
{tools_description}

Rules:
1. Analyze the task and break it into 2-6 steps.
2. Each step must be concrete and actionable.
3. Steps execute sequentially - each step receives the previous step's result.
4. If a step needs a web search, assign tool="web_search" and use the EXACT parameter names shown above (e.g. "query", not "keyword").
5. If a step writes a file, assign tool="write_file" and use the EXACT parameter names shown above (e.g. "path" and "content", not "file_path").
6. For any other tool, use the EXACT parameter names as shown in the tool listing.
7. If a step can be done with information already available, set tool=null (the LLM will reason directly).
8. Output ONLY valid JSON - no explanation, no markdown fences.

Output format:
{{
  "task_summary": "brief summary of the overall task",
  "steps": [
    {{
      "step_id": 1,
      "action": "what to do in this step",
      "tool": "tool_name_or_null",
      "tool_args": {{ "arg_name": "arg_value_or_$prev_result" }}
    }}
  ]
}}

Use "$prev_result" in tool_args when the argument should be filled from the previous step's output.
Use null for tool when the step is an LLM reasoning/calling step."""


class Planner:
    """Breaks down a user task into structured steps."""

    def __init__(self, llm: LLMClient, tool_registry: ToolRegistry):
        self.llm = llm
        self.tool_registry = tool_registry

    def plan(self, task: str) -> dict:
        """Generate a structured plan for the given task."""
        tools_info = self.tool_registry.list_tools()
        tools_str = json.dumps(tools_info, indent=2, ensure_ascii=False)

        messages = [
            {"role": "system", "content": PLANNER_PROMPT.format(tools_description=tools_str)},
            {"role": "user", "content": f"Task: {task}"},
        ]

        result = self.llm.chat_json(messages)

        # 校验：确保返回了 steps
        if not result.get("steps"):
            # 降级：生成一个 fallback 计划
            return {
                "task_summary": task[:100],
                "steps": [
                    {"step_id": 1, "action": f"处理任务: {task[:100]}", "tool": "null", "tool_args": {}},
                ],
            }

        return result
