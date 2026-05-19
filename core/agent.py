"""Main Agent Loop — orchestrates the full task → plan → execute → reflect → result flow."""

import re
from datetime import datetime
from core.llm import LLMClient
from core.planner import Planner
from core.executor import Executor
from core.reflector import Reflector
from core.tool_system import ToolRegistry
from core.memory import AgentMemory
from tools.file_tools import ReadFileTool, WriteFileTool
from tools.web_tools import WebSearchTool
from tools.web_reader import ReadWebpageTool
from workflow import WorkflowRegistry, Workflow


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
        self.workflow_registry = WorkflowRegistry()
        self.workflow: Workflow = None
        self.state: dict = {
            "evidence": [],       # 结构化证据列表: [{id, fact, source_url, source_tool, step_id}, ...]
            "searches_done": set(),
            "evidence_counter": 0,
        }
        self.max_reflection_rounds = max_reflection_rounds
        self.max_total_steps = max_total_steps
        self._written_files: set[str] = set()
        self._task_name: str = ""  # 用于报告文件名

    @staticmethod
    def _stream_handler(chunk: str):
        """Callback for streaming LLM output — prints tokens in real-time."""
        print(chunk, end="", flush=True)

    def _format_evidence(self) -> str:
        """Format accumulated evidence for injection into Executor context."""
        if not self.state["evidence"]:
            return ""
        lines = ["=== 已掌握事实（带来源引用） ==="]
        for e in self.state["evidence"]:
            src = f" (source: {e['source_url']})" if e.get("source_url") else ""
            lines.append(f"- [{e['id']}] {e['fact']}{src}")
        return "\n".join(lines)

    def _parse_evidence(self, result: str, step_id: int) -> list[dict]:
        """Extract structured evidence from [EVIDENCE] lines in LLM output.

        Expected format: [EVIDENCE] fact statement (source: URL)
        Returns list of dicts with id, fact, source_url.
        """
        lines = re.findall(r'^\[EVIDENCE\]\s*(.+)$', result, re.MULTILINE)
        parsed = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Extract URL from (source: URL) suffix
            url_match = re.search(r'\(source:\s*(https?://[^\s\)]+)\)', line)
            source_url = url_match.group(1) if url_match else ""
            # Remove the (source: URL) part to get the fact
            fact = re.sub(r'\s*\(source:\s*https?://[^\s\)]+\)', '', line).strip()

            self.state["evidence_counter"] += 1
            ev_id = f"ev_{self.state['evidence_counter']:03d}"

            # Dedup: skip if same fact already exists
            if any(e["fact"] == fact for e in self.state["evidence"]):
                continue

            entry = {
                "id": ev_id,
                "fact": fact,
                "source_url": source_url,
                "source_tool": "reasoning",
                "step_id": step_id,
            }
            parsed.append(entry)
            self.state["evidence"].append(entry)

        return parsed

    @staticmethod
    def _strip_evidence(result: str) -> str:
        """Remove [EVIDENCE] lines from result for clean memory storage."""
        return re.sub(r'^\[EVIDENCE\].*$\n?', '', result, flags=re.MULTILINE).rstrip()

    def _generate_report(self, task_summary: str, all_step_results: list) -> str:
        """Generate a structured Markdown report using accumulated evidence."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# 调研报告：{task_summary}",
            f"生成时间：{now}",
            "",
        ]

        # Summary
        ev_count = len(self.state["evidence"])
        src_count = len(set(e["source_url"] for e in self.state["evidence"] if e.get("source_url")))
        lines += [
            "## 摘要",
            f"- 执行步骤：{len(all_step_results)} 步",
            f"- 发现证据：{ev_count} 条",
            f"- 引用来源：{src_count} 个",
            "",
        ]

        # Key findings (from evidence)
        if self.state["evidence"]:
            lines += ["## 核心发现\n"]
            for ev in self.state["evidence"]:
                src = f" [来源]({ev['source_url']})" if ev.get("source_url") else ""
                lines.append(f"- **{ev['fact']}**{src}")
            lines.append("")

        # Full execution log
        lines += ["## 执行过程\n"]
        for sr in all_step_results:
            step = sr["step"]
            result = sr["result"]
            lines.append(f"### Step {step['step_id']}: {step['action']}")
            lines.append(result)
            lines.append("")

        # Sources appendix
        urls = []
        for ev in self.state["evidence"]:
            if ev.get("source_url") and ev["source_url"] not in urls:
                urls.append(ev["source_url"])
        if urls:
            lines += ["## 参考来源\n"]
            for i, url in enumerate(urls, 1):
                lines.append(f"{i}. {url}")
            lines.append("")

        return "\n".join(lines)

    def run(self, task: str) -> dict:
        """Run the full agent loop: plan → execute → reflect → repeat if needed."""
        print(f"\n{'='*60}")
        print(f"[Agent] Received task: {task}")
        print(f"{'='*60}\n")

        # Phase 0: Workflow matching
        self.workflow = self.workflow_registry.match(task)
        self._task_name = re.sub(r'[^\w一-鿿]', '_', task.strip())[:40]
        print(f"[Workflow] Matched: \033[36m{self.workflow.name}\033[0m — {self.workflow.description}\n")

        # Phase 1: Plan (with workflow context)
        plan_task = task
        if self.workflow.plan_instructions:
            plan_task = self.workflow.plan_instructions + "\n\n原始任务：" + task
        plan = self.planner.plan(plan_task)
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

                # 注入当前已积累的结构化证据到 context
                evidence_block = self._format_evidence()
                context_with_state = self.memory.get_context()
                if evidence_block:
                    context_with_state += "\n\n" + evidence_block

                result = self.executor.execute_step(
                    step=step,
                    prev_result=prev_result,
                    context=context_with_state,
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

                # 从 LLM 推理步骤结果中提取结构化证据
                if is_reasoning:
                    new_ev = self._parse_evidence(result, step["step_id"])
                    if new_ev:
                        for ev in new_ev:
                            print(f"  [State] +{ev['id']}: {ev['fact'][:60]}...")
                            if ev.get("source_url"):
                                print(f"          source: {ev['source_url']}")
                        print(f"  [State] Total evidence: {len(self.state['evidence'])}\n")

                # 追踪搜索查询（避免后续重复搜索）
                if step.get("tool") == "web_search":
                    query = step.get("tool_args", {}).get("query", "")
                    if query:
                        self.state["searches_done"].add(query.strip().lower())

                print(f"[Executor] Step {step['step_id']} result ({len(result)} chars):")
                print(f"  {result[:300]}{'...' if len(result) > 300 else ''}\n")

                # 存储到 memory（去掉 [EVIDENCE] 行以保持干净）
                clean_result = self._strip_evidence(result) if is_reasoning else result
                self.memory.add(
                    step_id=step["step_id"],
                    action=step["action"],
                    result=clean_result,
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
            reflect_task = task_summary
            if self.workflow.reflect_checks:
                reflect_task = self.workflow.reflect_checks + "\n\n原始任务：" + task_summary

            print(f"{'─'*40}")
            print(f"[Reflector] Checking task completeness...")
            reflection = self.reflector.reflect(reflect_task, execution_log)

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

                # 将结构化证据传给 Planner，避免重复规划已查过的内容
                evidence_str = ""
                if self.state["evidence"]:
                    facts = [e["fact"] for e in self.state["evidence"]]
                    evidence_str = "。已掌握信息: " + "; ".join(facts)
                reflection_task = ("继续完成任务。已完成步骤: " + task_summary
                                   + "。需要补充: " + "; ".join(missing)
                                   + evidence_str)
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

        # Phase 4: Compile final result with structured report
        report = self._generate_report(task_summary, all_step_results)
        final_result = self._compile_result(task_summary, all_steps, all_step_results, reflection_round)
        final_result["report"] = report

        # 最终回写：如果有中途写入的文件，用完整结果覆盖
        for file_path in self._written_files:
            try:
                self.tool_registry.run_tool("write_file", path=file_path, content=report)
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
