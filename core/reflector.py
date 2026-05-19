"""Reflection module — checks task completeness after execution."""

import json
from core.llm import LLMClient


REFLECTOR_PROMPT = """You are a task quality checker. Review the execution results and determine if the task is fully complete.

Original task: {task_summary}

Execution log:
{execution_log}

Rules:
1. Be strict — check that the final output file/result actually satisfies the original request.
2. If complete, respond ONLY with: {{"complete": true, "reason": "explain why it's complete"}}
3. If NOT complete, respond ONLY with: {{"complete": false, "reason": "what's missing", "missing_steps": ["step1", "step2"]}}
4. ⚠️ IMPORTANT — If the execution log contains [SEARCH_FAILED] markers, it means the search engine returned no useful results for those queries. Do NOT generate missing_steps that repeat the same failed searches. Instead, check if the task can be completed with what's already available, or consider if the task needs a fundamentally different search strategy.
5. ⚠️ CITATION CHECK — If the execution results make factual claims (names, numbers, stars, features) but do NOT cite source URLs in the format `(source: URL)`, flag this as incomplete with reason "claims missing source citations".
6. JSON only — no explanation, no markdown fences."""


class Reflector:
    """Checks whether the task is done, and if not, describes what's missing."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def reflect(self, task_summary: str, execution_log: str) -> dict:
        """Check completeness and return structured result."""
        messages = [
            {
                "role": "system",
                "content": REFLECTOR_PROMPT.format(
                    task_summary=task_summary,
                    execution_log=execution_log[-4000:],  # keep context manageable
                ),
            }
        ]
        return self.llm.chat_json(messages)
