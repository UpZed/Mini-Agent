"""LLM interface - abstracts API calls to any OpenAI-compatible provider."""

import os
import json
import time
from typing import Optional
import requests


# ── 预设 provider 配置 ──────────────────────────────────────────────
# 切换模型只需改 PROVIDER 常量，或在初始化时传入 provider="xxx"
PROVIDER = "deepseek"

PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-flash",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
    },
}

# 注意：不要在这里写 fallback key！通过环境变量设置。
# DeepSeek: set LLM_API_KEY   | OpenAI: set OPENAI_API_KEY
# SiliconFlow: set SILICONFLOW_API_KEY
API_KEYS = {
    "deepseek": os.getenv("LLM_API_KEY") or "",
    "openai": os.getenv("OPENAI_API_KEY") or "",
    "siliconflow": os.getenv("SILICONFLOW_API_KEY") or "",
}

MAX_RETRIES = 2          # 网络失败时重试次数
RETRY_DELAY = 3          # 重试间隔（秒）
REQUEST_TIMEOUT = 120    # 单次请求超时（秒）


class LLMClient:
    """LLM 客户端，支持重试、超时、JSON 容错。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        provider = provider or PROVIDER
        config = PROVIDERS.get(provider, {})

        self.api_key = api_key or API_KEYS.get(provider, "")
        self.base_url = (base_url or config.get("base_url", "")).rstrip("/")
        self.model = model or config.get("model", "")
        self._provider = provider

    def _request(self, messages: list[dict], temperature: float) -> str:
        """发送请求，带自动重试。"""
        last_error = None
        for attempt in range(1 + MAX_RETRIES):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout:
                last_error = f"Request timeout after {REQUEST_TIMEOUT}s"
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else "?"
                # 4xx 错误不重试（客户端问题），直接抛
                if status in (400, 401, 403, 404):
                    body = e.response.text[:200] if e.response is not None else ""
                    return f"API Error ({status}): {body}"
                last_error = f"HTTP {status}: {e}"
            except (KeyError, ValueError) as e:
                return f"API returned unexpected response: {e}"

            print(f"  [LLM] Retry {attempt+1}/{MAX_RETRIES} after error: {last_error}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        return f"Request failed after {MAX_RETRIES} retries: {last_error}"

    def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        """Send a chat completion request and return the content string."""
        return self._request(messages, temperature)

    def chat_stream(self, messages: list[dict], temperature: float = 0.3):
        """Send a streaming chat request and yield content chunks as they arrive (SSE).

        Falls back to yielding the full response on error.
        """
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                },
                stream=True,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8", errors="replace")
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except (requests.RequestException, json.JSONDecodeError) as e:
            import sys
            print(f"[Stream] Error: {e}, falling back to non-streaming", file=sys.stderr)
            yield self.chat(messages, temperature)

    def chat_json(self, messages: list[dict], temperature: float = 0.1) -> dict:
        """Chat and parse response as JSON. 解析失败时返回错误 dict，不崩溃。"""
        content = self.chat(messages, temperature=temperature)
        content = content.strip()

        # 尝试提取 JSON（兼容 markdown fence）
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
            content = content.strip()

        # 尝试从非 JSON 内容中查找 JSON 对象
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试查找 {...} 包裹的部分
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(content[start:end+1])
                except json.JSONDecodeError:
                    pass

            return {
                "complete": True,
                "reason": f"LLM returned non-JSON, treating as complete. Raw: {content[:200]}",
            }
