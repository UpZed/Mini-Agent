"""File read/write tools for the agent runtime."""

import os
from core.tool_system import BaseTool


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the content of a file at the given path."

    def run(self, path: str = "") -> str:
        if not path:
            return "Error: 'path' argument is required."
        if not os.path.exists(path):
            return f"Error: file not found at '{path}'."
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file at the given path."

    def run(self, path: str = "", content: str = "") -> str:
        if not path:
            return "Error: 'path' argument is required."
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to '{path}'."
        except Exception as e:
            return f"Error writing file: {e}"
