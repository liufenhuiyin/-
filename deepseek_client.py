# core/services/deepseek_client.py
"""
DeepSeek API 客户端（使用标准库 urllib）。
无状态，不保存 api_key 或任何配置。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Dict


DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message     = message
        super().__init__(f"DeepSeek API Error {status_code}: {message}")


class DeepSeekClient:
    """无状态 HTTP 客户端。api_key 和 payload 由调用方每次传入。"""

    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout

    def chat_completion(self, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data    = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }
        req = urllib.request.Request(
            DEEPSEEK_API_URL,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                body      = json.loads(e.read().decode("utf-8"))
                error_msg = body.get("error", {}).get("message", str(e))
            except Exception:
                error_msg = str(e)
            raise DeepSeekAPIError(e.code, error_msg)
        except urllib.error.URLError as e:
            raise DeepSeekAPIError(0, f"Network error: {e.reason}")
        except Exception as e:
            raise DeepSeekAPIError(0, f"Request failed: {e}")

    def extract_content(self, response: Dict[str, Any]) -> str:
        choices = response.get("choices", [])
        if not choices:
            raise DeepSeekAPIError(0, "API returned empty choices")
        message = choices[0].get("message", {})
        content = message.get("content", "") or message.get("reasoning_content", "")
        return content.strip()
