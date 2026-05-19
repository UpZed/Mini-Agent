"""Workflow definitions — each workflow guides plan decomposition, verification rules, and output format."""


class Workflow:
    """A workflow template: defines how a task type is planned, verified, and reported."""

    def __init__(
        self,
        name: str,
        description: str,
        plan_instructions: str = "",
        reflect_checks: str = "",
        report_sections: list[str] = None,
    ):
        self.name = name
        self.description = description
        self.plan_instructions = plan_instructions  # injected into Planner context
        self.reflect_checks = reflect_checks        # injected into Reflector context
        self.report_sections = report_sections or ["summary", "findings", "sources"]


TECH_RESEARCH = Workflow(
    name="tech_research",
    description="技术调研：搜索并整理某个主题的结构化信息，输出带来源引用的调研报告",
    plan_instructions=(
        "此任务为「技术调研」工作流，请严格按以下规范拆解：\n"
        "1. 先搜索主题的概览信息，识别关键实体（工具名/框架名/人名等）\n"
        "2. 对每个关键实体分别精确搜索，获取具体数据（star数、版本、特点等）\n"
        "3. 如搜索结果片段信息不足，安排 read_webpage 读取完整页面\n"
        "4. 每个实体的关键指标必须附带来源 URL\n"
        "5. 最后安排整合步骤，将所有数据汇总为结构化文本"
    ),
    reflect_checks=(
        "技术调研专项检查（严格）：\n"
        "1. 是否获取了关键实体的具体数据（star数、版本、特点等）？\n"
        "2. 每条数据是否附带 (source: URL) 来源引用？\n"
        "3. 是否有实体被遗漏没有被搜索到？\n"
        "4. 最终输出是否能完整回答原始调研问题？"
        "5. ⚠️ 如果搜索结果已确认无法提供所需数据（如 star 数），"
        "检查是否已有合理的替代方案（如用其他指标代替），而不是继续要求重复搜索"
    ),
    report_sections=["summary", "key_findings", "details", "sources"],
)

COMPARISON = Workflow(
    name="comparison",
    description="产品/框架对比：对多个目标进行横向对比分析，输出对比表",
    plan_instructions=(
        "此任务为「对比分析」工作流，请严格按以下规范拆解：\n"
        "1. 先识别需要对比的所有目标实体\n"
        "2. 对每个目标实体分别搜索，收集统一维度的数据（star数、特点、发布时间等）\n"
        "3. 确保所有目标都被搜索到，不遗漏任何一方\n"
        "4. 每条数据必须附带来源 URL\n"
        "5. 最后安排对比总结步骤，以表格形式横向对比所有目标"
    ),
    reflect_checks=(
        "对比分析专项检查（严格）：\n"
        "1. 是否覆盖了所有待对比的目标？\n"
        "2. 每个目标的信息维度是否一致（不能 A 有 star 数而 B 没有）？\n"
        "3. 是否有横向对比表或对比总结？\n"
        "4. 每条数据是否附带 (source: URL) 来源引用？"
    ),
    report_sections=["summary", "comparison_table", "detailed_analysis", "sources"],
)

DEFAULT = Workflow(
    name="default",
    description="通用任务：无预设场景约束，按常规流程处理",
    plan_instructions="",
    reflect_checks="",
    report_sections=["summary", "details", "sources"],
)


class WorkflowRegistry:
    """Registry of all available workflows, with auto-matching logic."""

    def __init__(self):
        self._workflows: dict[str, Workflow] = {}
        self.register(DEFAULT)
        self.register(TECH_RESEARCH)
        self.register(COMPARISON)

    def register(self, workflow: Workflow):
        self._workflows[workflow.name] = workflow

    def get(self, name: str) -> Workflow:
        return self._workflows.get(name, DEFAULT)

    def match(self, task: str) -> Workflow:
        """Auto-detect the best workflow for a given task string."""
        task_lower = task.lower()

        # Comparison keywords
        comparison_signals = ["对比", "比较", "vs", "versus", "还是", "哪个好",
                              "区别", "差异", "comparison", "compare", "difference"]
        research_signals = ["调研", "调查", "研究", "分析", "介绍", "趋势",
                            "最新", "2025", "2026", "research", "analysis",
                            "survey", "overview"]

        comparison_score = sum(1 for s in comparison_signals if s in task_lower)
        research_score = sum(1 for s in research_signals if s in task_lower)

        if comparison_score >= research_score and comparison_score > 0:
            return COMPARISON
        if research_score > 0:
            return TECH_RESEARCH

        return DEFAULT
