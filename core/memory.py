"""Agent Memory module — structured episodic memory with auto-summarization.

Provides three tiers of memory:
1. Recent entries — full detail (last 2-3 steps)
2. Summarized history — LLM-compressed summary of older steps
3. Search — keyword lookup across all entries
"""

from core.llm import LLMClient

# 超过此条目数自动触发摘要压缩
_MAX_ENTRIES_BEFORE_SUMMARY = 8


class AgentMemory:
    """Lightweight episodic memory for the Agent loop."""

    def __init__(self, llm: LLMClient | None = None):
        self._entries: list[dict] = []
        self._summary: str = ""
        self._entry_counter: int = 0
        self._llm = llm

    # ── write ───────────────────────────────────────────────────────

    def add(self, step_id: int, action: str, result: str,
            tool: str | None = None, metadata: dict | None = None):
        """Record a step execution into memory."""
        self._entries.append({
            "id": self._entry_counter,
            "step_id": step_id,
            "action": action,
            "tool": tool,
            "result": result,
            "metadata": metadata or {},
        })
        self._entry_counter += 1

        if self._llm and len(self._entries) >= _MAX_ENTRIES_BEFORE_SUMMARY:
            self._summarize()

    def clear(self):
        """Reset all memory."""
        self._entries = []
        self._summary = ""
        self._entry_counter = 0

    # ── read ────────────────────────────────────────────────────────

    def get_context(self, max_chars: int = 4000) -> str:
        """Build a context string for the Executor.

        Returns the summary (if any) followed by the most recent entries
        in full detail. Truncates if over *max_chars*.
        """
        parts = []
        if self._summary:
            parts.append(f"[Memory Summary]\n{self._summary}\n")

        recent = self._entries[-3:]
        for entry in recent:
            result_snippet = entry["result"][:500]
            parts.append(
                f"--- Step {entry['step_id']}: {entry['action']} ---\n"
                f"{result_snippet}"
            )

        context = "\n\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n...(truncated)"
        return context

    @property
    def full_log(self) -> str:
        """Complete execution trace for the Reflector."""
        parts = []
        if self._summary:
            parts.append(f"[Memory Summary]\n{self._summary}")
        for entry in self._entries:
            parts.append(
                f"--- Step {entry['step_id']}: {entry['action']} ---\n"
                f"{entry['result']}"
            )
        return "\n\n".join(parts)

    def search(self, keyword: str) -> list[dict]:
        """Simple case-insensitive keyword search across stored entries."""
        kw = keyword.lower()
        return [
            e for e in self._entries
            if kw in e["action"].lower() or kw in e["result"].lower()
        ]

    # ── internal ────────────────────────────────────────────────────

    def _summarize(self):
        """Use LLM to condense older entries into a persistent summary."""
        text = "\n".join(
            f"Step {e['step_id']}: {e['action']}\n{e['result'][:200]}"
            for e in self._entries[:-2]  # keep 2 most recent in full
        )
        prompt = [
            {
                "role": "system",
                "content": "You are a memory compression engine. Summarize the "
                           "following execution trace concisely. Keep key findings, "
                           "decisions, and outputs. Output a short paragraph.",
            },
            {"role": "user", "content": text},
        ]
        try:
            self._summary = self._llm.chat(prompt)
        except Exception:
            pass  # summarization is best-effort

        self._entries = self._entries[-2:]

    @property
    def entry_count(self) -> int:
        return len(self._entries) + (1 if self._summary else 0)

    def stats(self) -> dict:
        """Return a small stats dict for logging / compile result."""
        return {
            "entries": len(self._entries),
            "summarized": bool(self._summary),
            "total": self.entry_count,
        }
