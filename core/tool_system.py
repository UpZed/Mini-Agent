"""Tool system with standardized interface.

Every tool inherits from BaseTool and implements:
- name: str
- description: str
- run(**kwargs) -> str
"""

import inspect
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Standardized tool interface."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, **kwargs) -> str:
        """Execute the tool and return a string result."""
        ...

    def get_parameters(self) -> dict[str, dict]:
        """Return the tool's parameter schema (name → {type, default, required})."""
        sig = inspect.signature(self.run)
        params = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            params[name] = {
                "type": str(param.annotation) if param.annotation is not inspect.Parameter.empty else "string",
                "required": param.default is inspect.Parameter.empty,
            }
        return params


class ToolRegistry:
    """Registry that holds all available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")
        return tool

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.get_parameters(),
            }
            for t in self._tools.values()
        ]

    def run_tool(self, name: str, **kwargs) -> str:
        tool = self.get(name)
        return tool.run(**kwargs)
