"""Executor module - executes each step of the plan sequentially."""

import re
from core.llm import LLMClient
from core.tool_system import ToolRegistry


EXECUTOR_PROMPT = """You are a step executor. Your job is to execute a single step of a plan.

Current step: {step_description}

Previous step result (if any): {prev_result}

All prior execution results (context for this step):
{context}

Overall task summary: {task_summary}

RULES (strict):
1. This is an analysis/reasoning step (no tool assigned). Do your best with the information above.
2. If the context contains article URLs and you need more detail to complete the step, list the URLs that need to be read so the next step can fetch them.
3. ⚠️ CRITICAL — ANTI-FABRICATION: If information is missing or insufficient, say "未找到可靠信息" honestly. Do NOT make up data.
4. ⚠️ CITATION REQUIRED — When you reference any specific data, number, or factual claim that came from a search result or webpage, append the source URL in parentheses after the claim. Format: `AutoGen 有 40k+ GitHub stars (source: https://github.com/microsoft/autogen)`. If you cannot determine the source for a claim, do NOT make that claim.
5. Output ONLY your analysis text, no special prefixes."""

TRANSLATE_PROMPT = """You are a search query translator. Translate the following Chinese search query to English.

Rules:
- Keep proper nouns (product names, people names, brands) unchanged
- Output ONLY the translated query, no explanation, no quotes
- If the query is already in English, output it as-is

Original query: {query}"""


class Executor:
    """Executes a single step of the plan."""

    # 参数别名映射：LLM 可能生成的错误参数名 → 正确的参数名
    PARAM_ALIASES = {
        "file_path": "path",
        "keyword": "query",
        "search_query": "query",
    }

    # 搜索引擎返回空结果的特征关键词
    _SEARCH_FAILED_PATTERNS = [
        "no results found",
        "未找到",
        "0 results",
        "没有找到",
    ]

    def __init__(self, llm: LLMClient, tool_registry: ToolRegistry):
        self.llm = llm
        self.tool_registry = tool_registry

    def execute_step(
        self,
        step: dict,
        prev_result: str,
        context: str = "",
        task_summary: str = "",
        on_token: callable = None,
    ) -> str:
        """Execute one step and return the result.

        If on_token is provided and this is an LLM reasoning step, tokens
        are yielded to on_token as they arrive (streaming).
        """
        tool_name = step.get("tool")
        tool_args = step.get("tool_args", {})

        # If a tool is specified, call it directly
        if tool_name and tool_name != "null":
            resolved_args = {}
            for k, v in tool_args.items():
                # 参数名别名修正
                canonical_k = self.PARAM_ALIASES.get(k, k)
                if isinstance(v, str) and "$prev_result" in v:
                    resolved_args[canonical_k] = v.replace("$prev_result", prev_result)
                else:
                    resolved_args[canonical_k] = v

            # 查询翻译：web_search 前将中文查询翻译为英文
            if tool_name == "web_search":
                query = resolved_args.get("query", "")
                if query and self._contains_chinese(query):
                    translated = self._translate_query(query)
                    print(f"  [Executor] Query translated: '{query[:60]}' → '{translated[:60]}'")
                    resolved_args["query"] = translated

            # URL 提取：read_webpage 前从文本中提取干净 URL
            if tool_name == "read_webpage":
                url_param = resolved_args.get("url", "")
                if url_param:
                    cleaned = self._extract_url(url_param)
                    if cleaned != url_param:
                        print(f"  [Executor] Extracted URL from text")
                        resolved_args["url"] = cleaned

            try:
                result = self.tool_registry.run_tool(tool_name, **resolved_args)
            except Exception as e:
                return f"Error calling tool '{tool_name}': {e}"

            # 搜索失败标记：如果搜索结果为空，打上 SEARCH_FAILED 标签
            if tool_name == "web_search" and self._is_search_failed(result):
                result = f"[SEARCH_FAILED] {result}"

            return result

        # Otherwise, use LLM to reason about this step
        messages = [
            {
                "role": "system",
                "content": EXECUTOR_PROMPT.format(
                    step_description=step.get("action", ""),
                    prev_result=prev_result[:3000],
                    context=context or "(no prior results yet)",
                    task_summary=task_summary,
                ),
            }
        ]

        # Streaming or non-streaming LLM call
        if on_token:
            full_content = ""
            try:
                for chunk in self.llm.chat_stream(messages):
                    on_token(chunk)
                    full_content += chunk
                return full_content
            except Exception as e:
                return f"Error during LLM reasoning step: {e}"
        else:
            try:
                return self.llm.chat(messages)
            except Exception as e:
                return f"Error during LLM reasoning step: {e}"

    def _translate_query(self, query: str) -> str:
        """Translate a Chinese search query to English using LLM."""
        messages = [
            {"role": "system", "content": TRANSLATE_PROMPT.format(query=query)},
        ]
        try:
            result = self.llm.chat(messages, temperature=0.1)
            result = result.strip().strip('"').strip("'")
            return result if result else query
        except Exception:
            return query  # fallback: 翻译失败就用原查询

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        """Check if text contains Chinese characters."""
        return bool(re.search(r'[一-鿿㐀-䶿]', text))

    @staticmethod
    def _is_search_failed(result: str) -> bool:
        """Check if a search result indicates empty/no results."""
        if not result or len(result) < 20:
            return True
        lowered = result.lower()
        return any(p in lowered for p in Executor._SEARCH_FAILED_PATTERNS)

    @staticmethod
    def _extract_url(text: str) -> str:
        """Extract the first http/https URL from text, or return original if none found."""
        text = text.strip()
        # 如果本身就是干净 URL，直接返回
        url_match = re.search(r'(https?://[^\s\)\]》」\'\"<>，,。、]+)', text)
        if url_match:
            return url_match.group(1)
        return text
