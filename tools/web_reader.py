"""Web page content extraction tool.

Reads a URL and extracts readable text content from the HTML.
Uses only stdlib html.parser + requests (already a dependency).
"""

import re
import requests
from html.parser import HTMLParser
from urllib.parse import urlparse
from core.tool_system import BaseTool


class _HTMLTextExtractor(HTMLParser):
    """Strips HTML tags and extracts clean text."""

    def __init__(self):
        super().__init__()
        self._result = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._result.append("\n")

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._result.append(text)

    def get_text(self) -> str:
        raw = " ".join(self._result)
        # 合并多余空白和空行
        raw = re.sub(r"\n\s*\n", "\n\n", raw)
        raw = re.sub(r" {2,}", " ", raw)
        return raw.strip()


class ReadWebpageTool(BaseTool):
    name = "read_webpage"
    description = "Read the full text content of a webpage at the given URL. Use this when search result snippets are insufficient."

    MAX_CONTENT_LENGTH = 8000   # 单页最大截取字符数
    REQUEST_TIMEOUT = 15        # 单次请求超时（秒）

    def run(self, url: str = "") -> str:
        if not url:
            return "Error: 'url' argument is required."

        # 基本 URL 校验
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return f"Error: invalid URL '{url}'."

        try:
            resp = requests.get(
                url,
                timeout=self.REQUEST_TIMEOUT,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()

            # 检测编码
            if resp.encoding and resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"

            html = resp.text

        except requests.exceptions.Timeout:
            return f"Error: request to '{url}' timed out after {self.REQUEST_TIMEOUT}s."
        except requests.exceptions.ConnectionError as e:
            return f"Error: connection failed for '{url}': {e}"
        except requests.exceptions.HTTPError as e:
            return f"Error: HTTP {e.response.status_code} for '{url}'."
        except Exception as e:
            return f"Error reading '{url}': {e}"

        # 提取正文
        extractor = _HTMLTextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            return f"Error: failed to parse HTML from '{url}'."

        text = extractor.get_text()

        if not text:
            return f"No readable content found at '{url}'."

        # 截断过长的内容
        if len(text) > self.MAX_CONTENT_LENGTH:
            text = text[:self.MAX_CONTENT_LENGTH] + (
                f"\n\n... (truncated, full content is {len(text)} chars)"
            )

        return text
