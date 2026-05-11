# core/services/conversation_service.py
"""
ConversationService — 支持流式输出。

流式原理：
  DeepSeek API 返回 SSE（Server-Sent Events）格式的数据流。
  每收到一个 chunk 就立刻通过 on_token 回调推送给 Controller，
  Controller 再推送给 UIStateStore，UI 实时渲染。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Callable, Iterator

from core.services.deepseek_client import DeepSeekAPIError

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class ConversationService:
    """无状态对话服务。支持流式和非流式两种模式。"""

    def __init__(self, timeout: float = 120.0):
        self._timeout = timeout

    def send_message_stream(
        self,
        api_key:      str,
        messages:     List[Dict[str, str]],
        model_config: Dict[str, Any],
        on_token:     Callable[[str], None],
    ) -> str:
        """
        流式发送消息。每收到一个 token 立刻调用 on_token 回调。
        返回完整的响应文本。

        Args:
            api_key:      从 Controller 传入，Service 不自行读取
            messages:     完整消息列表，由 Controller 构建
            model_config: 来自 ModelConfig.to_api_payload()
            on_token:     每收到一个 token 时的回调，由 AppController 传入
        """
        payload = {
            **model_config,
            "messages":   messages,
            "max_tokens": 4096,
            "stream":     True,   # 开启流式
        }

        data    = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "Accept":        "text/event-stream",
        }

        req = urllib.request.Request(
            DEEPSEEK_API_URL,
            data=data,
            headers=headers,
            method="POST",
        )

        full_response = ""

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()

                    # SSE 格式：每行以 "data: " 开头
                    if not line.startswith("data:"):
                        continue

                    data_str = line[len("data:"):].strip()

                    # 流结束标志
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # 提取 delta content
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta   = choices[0].get("delta", {})
                    token   = delta.get("content", "")

                    if token:
                        full_response += token
                        on_token(token)   # 立刻推送给 Controller

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
            raise DeepSeekAPIError(0, f"Stream failed: {e}")

        return full_response
