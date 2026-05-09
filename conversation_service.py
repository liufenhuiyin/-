# core/services/conversation_service.py
"""
ConversationService — MVP 版本（非流式）。

职责：
  - 构建符合 DeepSeek API 规范的完整 payload
  - 调用 DeepSeekClient 发送请求
  - 返回纯文本响应

禁止：
  - 保存任何状态（messages、model config 等）
  - 决定上下文内容（messages 由 Controller 传入）
  - 直接访问数据库
"""
from __future__ import annotations

from typing import List, Dict, Any
from core.services.deepseek_client import DeepSeekClient, DeepSeekAPIError


class ConversationService:
    """
    无状态对话服务。
    所有输入参数由 Controller 构建后传入，Service 不做业务决策。
    """

    def __init__(self, client: DeepSeekClient):
        # 唯一依赖：HTTP 客户端（也是无状态的）
        self._client = client

    def send_message(
        self,
        api_key:      str,
        messages:     List[Dict[str, str]],   # [{"role": ..., "content": ...}]
        model_config: Dict[str, Any],          # 来自 ModelConfig.to_api_payload()
        max_tokens:   int = 4096,
    ) -> str:
        """
        发送消息并返回 assistant 的回复文本。

        Args:
            api_key:      从 Controller（SettingsController）获取，不自行读取环境变量
            messages:     完整消息列表，由 Controller 构建（包含历史上下文）
            model_config: API 配置片段，来自 ModelConfig.to_api_payload()
            max_tokens:   最大 token 数

        Returns:
            assistant 回复的纯文本

        Raises:
            DeepSeekAPIError: API 调用失败
        """
        # 构建完整 payload
        # 严格遵循 DeepSeek API 规范，不重新设计字段
        payload: Dict[str, Any] = {
            **model_config,        # model, thinking, reasoning_effort
            "messages":   messages,
            "max_tokens": max_tokens,
            "stream":     False,   # MVP 阶段不使用流式
        }

        response = self._client.chat_completion(api_key=api_key, payload=payload)
        return self._client.extract_content(response)
