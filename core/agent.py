"""Main Agent Loop — orchestrates the full task → plan → execute → reflect → result flow."""

import re
from core.llm import LLMClient
from core.planner import Planner
from core.executor import Executor
from core.reflector import Reflector
from core.tool_system import ToolRegistry
from core.memory import AgentMemory
from tools.file_tools import ReadFileTool, WriteFileTool
from tools.web_tools import WebSearchTool
from tools.web_reader import ReadWebpageTool


class Agent:
    """Mini Agent Runtime — the main entry point."""

    def __init__(self, llm: LLMClient, max_reflection_rounds: int = 2, max_total_steps: int = 15):
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(ReadFileTool())
        self.tool_registry.register(WriteFileTool())
        self.tool_registry.register(WebSearchTool())
        self.tool_registry.register(ReadWebpageTool())

        self.planner = Planner(llm, self.tool_registry)
        self.executor = Executor(llm, self.tool_registry)
        self.reflector = Reflector(llm)
        self.llm = llm
        self.memory = AgentMemory(llm=llm)
        self.max_reflection_rounds = max_reflection_rounds
        self.max_total_steps = max_total_steps      # 防止无限循环的安全阀
        self._written_files: set[str] = set()       # 追踪写入的文件路径，用于最终回写

    @staticmethod
    def _stream_handler(chunk: str):
        """Callback for streaming LLM output — prints tokens in real-time."""
        print(chunk, end="", flush=True)


    def run(self, task: str) -> dict:
        """Run the full agent loop: plan → execute → reflect → repeat if needed."""
        print(f"\n{'='*60}")
        print(f"[Agent] Received task: {task}")
        print(f"{'='*60}\n")

        # Phase 1: Plan
        plan = self.planner.plan(task)
        task_summary = plan.get("task_summary", task)
        steps = plan.get("steps", [])
        print(f"[Planner] Task summary: {task_summary}")
        print(f"[Planner] Generated {len(steps)} steps:\n")
        for s in steps:
            tool_info = f" → tool: {s['tool']}" if s.get("tool") and s["tool"] != "null" else ""
            print(f"  Step {s['step_id']}: {s['action']}{tool_info}")
        print()

        # Phase 2: Execute
        all_step_results = []
        all_steps = []
        current_steps = steps
        reflection_round = 0
        prev_missing_steps = []  # 用于防循环：记录上一轮反思的 missing_steps

        while current_steps:
            prev_result = ""
            step_results = []

            for step in current_steps:
                print(f"{'─'*40}")
                print(f"[Executor] Step {step['step_id']}: {step['action']}")
                print(f"{'─'*40}")

                is_reasoning = not step.get("tool") or step["tool"] == "null"
                if is_reasoning:
                    print(f"[Executor] Reasoning: ", end="", flush=True)

                result = self.executor.execute_step(
                    step=step,
                    prev_result=prev_result,
                    context=self.memory.get_context(),
                    task_summary=task_summary,
                    on_token=self._stream_handler if is_reasoning else None,
                )

                if is_reasoning:
                    print()

                # 追踪文件写入，供最终回写使用
                if step.get("tool") == "write_file":
                    path = step.get("tool_args", {}).get("path", "")
                    if path and "Successfully wrote" in result:
                        self._written_files.add(path)

                print(f"[Executor] Step {step['step_id']} result ({len(result)} chars):")
                print(f"  {result[:300]}{'...' if len(result) > 300 else ''}\n")

                self.memory.add(
                    step_id=step["step_id"],
                    action=step["action"],
                    result=result,
                    tool=step.get("tool"),
                )
                prev_result = result
                step_results.append({"step": step, "result": result})

            all_step_results.extend(step_results)
            all_steps.extend(current_steps)

            # 搜索熔断：如果本轮所有 web_search 都失败了，直接终止
            if self._all_searches_failed(current_steps, step_results):
                print(f"[Agent] All searches failed in this round — stopping to avoid dead loop.\n")
                break

            # 安全阀：超过最大步骤数强制终止
            if len(all_steps) >= self.max_total_steps:
                print(f"[Agent] Max total steps ({self.max_total_steps}) reached. Stopping.\n")
                break

            # Phase 3: Reflect (check if task is complete)
            if reflection_round >= self.max_reflection_rounds:
                print(f"[Agent] Max reflection rounds ({self.max_reflection_rounds}) reached. Stopping.\n")
                break

            execution_log = self.memory.full_log

            print(f"{'─'*40}")
            print(f"[Reflector] Checking task completeness...")
            reflection = self.reflector.reflect(task_summary, execution_log)

            if reflection.get("complete"):
                print(f"[Reflector] Task is complete: {reflection.get('reason', '')}\n")
                break
            else:
                reflection_round += 1
                print(f"[Reflector] Task incomplete (round {reflection_round}): {reflection.get('reason', '')}")
                missing = reflection.get("missing_steps", [])

                # 防循环检测：连续两轮 missing_steps 高度相似 → 强制终止
                if prev_missing_steps and self._steps_similar(prev_missing_steps, missing):
                    print(f"[Reflector] Detected loop — consecutive reflection rounds request similar steps.")
                    print(f"[Reflector] Previous: {prev_missing_steps}")
                    print(f"[Reflector] Current:  {missing}")
                    print(f"[Reflector] Breaking loop to avoid infinite cycle.\n")
                    break
                prev_missing_steps = missing

                print(f"[Reflector] Generating {len(missing)} additional steps...\n")

                # 将缺失步骤重新交给 Planner 分配工具，确保反思轮也能调工具
                reflection_task = "继续完成任务。已完成步骤: " + task_summary + "。需要补充: " + "; ".join(missing)
                reflection_plan = self.planner.plan(reflection_task)
                new_steps = reflection_plan.get("steps", [])
                current_steps = []
                for i, s in enumerate(new_steps):
                    s["step_id"] = len(all_steps) + i + 1
                    current_steps.append(s)
                if not current_steps:
                    # 降级：尝试从 missing 文本推断工具，避开已失败的搜索词
                    current_steps = []
                    for i, step_text in enumerate(missing):
                        tool = "null"
                        tool_args = {}
                        text_lower = step_text.lower()
                        if any(w in text_lower for w in ["搜索", "search", "查", "查找", "查询", "find"]):
                            tool = "web_search"
                            # 降级时让 LLM 重新提取关键词，而不是直接用原文
                            tool_args = {"query": self._extract_search_keywords(step_text)}
                        elif any(w in text_lower for w in ["读取", "阅读", "打开", "查看", "read", "open", "fetch", "抓取"]):
                            tool = "read_webpage"
                            tool_args = {"url": "$prev_result"}
                        elif any(w in text_lower for w in ["写", "写入", "保存", "存为", "write", "save"]):
                            tool = "write_file"
                            tool_args = {"path": "output/result.md", "content": "$prev_result"}
                        current_steps.append({
                            "step_id": len(all_steps) + i + 1,
                            "action": step_text,
                            "tool": tool,
                            "tool_args": tool_args,
                        })

        # Phase 4: Compile final result
        final_result = self._compile_result(task_summary, all_steps, all_step_results, reflection_round)

        # 最终回写：如果有中途写入的文件，用完整结果覆盖
        for file_path in self._written_files:
            try:
                self.tool_registry.run_tool("write_file", path=file_path, content=final_result["log"])
                print(f"  [Agent] Final result re-written to {file_path}")
            except Exception:
                pass

        return final_result

    @staticmethod
    def _extract_search_keywords(step_text: str) -> str:
        """从反思降级步骤文本中提取搜索关键词，避免用重复的无效查询。"""
        # 去掉"搜索/查找/查询"等动词前缀
        cleaned = re.sub(r'^(搜索|查找|查询|搜一下|找一下|尝试搜索|请搜索|search|find|look for)\s*', '', step_text, flags=re.IGNORECASE)
        # 去掉常见无用后缀
        cleaned = re.sub(r'(的信息|的资料|的内容|的相关信息|的结果)$', '', cleaned)
        return cleaned.strip()[:100] or step_text[:100]

    def _compile_result(
        self, task_summary: str, steps: list, step_results: list, reflection_rounds: int = 0
    ) -> dict:
        """Compile execution traces into a final result."""
        full_log = []
        for sr in step_results:
            full_log.append(f"### Step {sr['step']['step_id']}: {sr['step']['action']}")
            full_log.append(sr["result"])
            full_log.append("")

        return {
            "task": task_summary,
            "steps_executed": len(steps),
            "reflection_rounds": reflection_rounds,
            "memory_stats": self.memory.stats(),
            "log": "\n".join(full_log),
            "summary": f"Completed {len(steps)} steps across {reflection_rounds + 1} pass(es) for task: {task_summary}",
        }

    @staticmethod
    def _steps_similar(a: list[str], b: list[str], threshold: float = 0.7) -> bool:
        """Check if two lists of step descriptions are too similar (防循环)."""
        if not a or not b:
            return False
        # 将步骤文本拼合后分词，用 Jaccard 相似度
        def _tokenize(text: str) -> set[str]:
            tokens = re.findall(r'[一-鿿\w]+', text)
            return {t for t in tokens if len(t) > 1}
        set_a = _tokenize(" ".join(a))
        set_b = _tokenize(" ".join(b))
        if not set_a or not set_b:
            return False
        overlap = len(set_a & set_b) / len(set_a | set_b)
        return overlap >= threshold

    @staticmethod
    def _all_searches_failed(steps: list[dict], step_results: list[dict]) -> bool:
        """Check if all web_search steps in this round returned no useful results."""
        search_steps = [
            sr for sr in step_results
            if sr["step"].get("tool") == "web_search"
        ]
        if not search_steps:
            return False  # 本轮没有搜索步骤
        # 所有搜索步骤都标记为失败 → 熔断
        return all("[SEARCH_FAILED]" in sr["result"] for sr in search_steps)
