# Layer: Core
# File: app/core/conversation_service.py
# Responsibility: 对话生命周期与消息发送的业务编排。
#                 决定"做什么"：创建会话、构建上下文、调用 LLM、持久化、返回结果。
#                 "怎么做"（HTTP、SQL、文件解析）全部委托给注入的底层服务。
# Input:  来自 Controller 的业务参数（session_id, text, files 等简单类型）
# Output: 领域对象（Conversation, ConversationDetail, MessageChunk AsyncGenerator）
# 禁止: HTTP 调用、SQL 语句、文件 I/O、导入 Flet

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, Protocol, runtime_checkable

import config as app_config
from app.storage.models import (
    Conversation,
    ConversationDetail,
    Message,
    MessageChunk,
    MessageRole,
)


# ──────────────────────────────────────────────
# 依赖接口（由 Adapters 实现，Core 只依赖抽象）
# ──────────────────────────────────────────────

@runtime_checkable
class LLMClientProtocol(Protocol):
    """LLM 客户端抽象接口，由 adapters/deepseek_client.py 实现。"""

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        thinking_enabled: bool,
    ) -> AsyncGenerator[MessageChunk, None]:
        """
        发起流式对话请求。

        Args:
            messages:         OpenAI 格式消息列表 [{"role": ..., "content": ...}]
            model:            模型标识符，直接透传，不在此解释
            thinking_enabled: 是否开启思考模式

        Yields:
            MessageChunk — 逐块返回，is_done=True 时结束
        """
        ...

    def cancel(self) -> None:
        """中止当前流式请求。"""
        ...


@runtime_checkable
class ConversationRepoProtocol(Protocol):
    """对话历史仓库抽象，由 storage/conversation_repo.py 实现。"""

    def save_conversation(self, conversation: Conversation) -> None: ...
    def get_conversation(self, session_id: str) -> Conversation | None: ...
    def get_conversation_detail(self, session_id: str) -> ConversationDetail | None: ...
    def list_conversations(self) -> list[Conversation]: ...
    def delete_conversation(self, session_id: str) -> None: ...
    def append_message(self, session_id: str, message: Message) -> None: ...
    def update_message(self, session_id: str, message: Message) -> None: ...


# ──────────────────────────────────────────────
# ConversationService
# ──────────────────────────────────────────────

class ConversationService:
    """
    对话业务编排服务。

    职责：
    - 创建 / 切换 / 删除对话（维护领域状态）
    - send_message：构建上下文 → 调用 LLM 流 → 持久化 → yield chunk
    - regenerate_message：截断历史 → 重新调用 LLM → 更新持久化
    - stop_generation：中止当前流

    注入依赖（不自行实例化）：
        llm_client:       LLMClientProtocol
        conversation_repo: ConversationRepoProtocol
        context_service:  ContextService
        file_service:     FileService（可选，有附件时使用）
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        conversation_repo: ConversationRepoProtocol,
        context_service: "ContextService",
        file_service: "FileService | None" = None,
    ) -> None:
        self._llm = llm_client
        self._repo = conversation_repo
        self._context_svc = context_service
        self._file_svc = file_service
        self._stop_event = asyncio.Event()

    # ── 对话生命周期 ──────────────────────────

    def create_conversation(self) -> Conversation:
        """
        新建一个空对话并持久化。

        Returns:
            Conversation — 含新生成的 id 和空消息列表
        """
        conversation = Conversation(
            id=_new_id(),
            title="",
            last_message_preview="",
            updated_at=datetime.now(),
            message_count=0,
        )
        self._repo.save_conversation(conversation)
        return conversation

    def switch_conversation(self, session_id: str) -> ConversationDetail:
        """
        切换到指定对话，加载完整消息历史。

        Args:
            session_id: 目标对话 ID

        Returns:
            ConversationDetail — 含完整 messages 列表

        Raises:
            ConversationNotFoundError: 若 session_id 不存在
        """
        detail = self._repo.get_conversation_detail(session_id)
        if detail is None:
            raise ConversationNotFoundError(session_id)
        return detail

    def delete_conversation(self, session_id: str) -> None:
        """
        删除指定对话及其所有消息。

        Args:
            session_id: 要删除的对话 ID
        """
        self._repo.delete_conversation(session_id)

    def list_conversations(self) -> list[Conversation]:
        """
        获取所有对话摘要列表，按 updated_at 倒序。

        Returns:
            list[Conversation]
        """
        conversations = self._repo.list_conversations()
        return sorted(conversations, key=lambda c: c.updated_at, reverse=True)

    # ── 消息发送（核心编排） ──────────────────

    async def send_message(
        self,
        session_id: str,
        text: str,
        files: list[str],
    ) -> AsyncGenerator[MessageChunk, None]:
        """
        发送消息完整流程：
            1. 提取附件内容（如有）
            2. 持久化用户消息
            3. 构建 LLM 上下文（调用 ContextService）
            4. 读取当前配置（model, thinking_enabled, search_enabled）
            5. 若 search_enabled，先执行搜索并注入结果
            6. 流式调用 LLM，逐块 yield
            7. 流结束后将完整回复持久化
            8. 更新对话摘要（title 自动生成、preview、updated_at）

        Args:
            session_id: 当前对话 ID
            text:       用户输入文本
            files:      附件路径列表

        Yields:
            MessageChunk — 逐块，包含 delta / chunk_type / is_done
        """
        self._stop_event.clear()

        # ── 1. 提取附件内容 ──────────────────
        file_contents: list[str] = []
        if files and self._file_svc:
            for path in files:
                content = await self._file_svc.extract_content(path)
                if content:
                    file_contents.append(content)

        # ── 2. 组装用户消息并持久化 ───────────
        user_content = _compose_user_content(text, file_contents)
        user_message = Message(
            id=_new_id(),
            role=MessageRole.USER,
            content=user_content,
            is_thinking=False,
            created_at=datetime.now(),
        )
        self._repo.append_message(session_id, user_message)

        # ── 3. 构建 LLM 上下文 ────────────────
        messages = await self._context_svc.build_llm_context(session_id)

        # ── 4. 读取当前配置 ───────────────────
        model: str = app_config.model_type
        thinking_enabled: bool = app_config.thinking_enabled
        search_enabled: bool = app_config.search_enabled

        # ── 5. 搜索增强（如启用） ─────────────
        if search_enabled:
            search_injection = await self._context_svc.inject_search_context(
                session_id=session_id,
                query=text,
            )
            if search_injection:
                # 将搜索结果作为 system 追加注入上下文末尾
                messages = messages + [
                    {"role": "system", "content": search_injection}
                ]

        # ── 6. 流式调用 LLM ──────────────────
        full_content = ""
        full_thinking = ""
        assistant_msg_id = _new_id()

        async for chunk in self._llm.stream_chat(
            messages=messages,
            model=model,
            thinking_enabled=thinking_enabled,
        ):
            if self._stop_event.is_set():
                # 用户主动停止，发送 done 后退出
                yield MessageChunk(
                    delta="",
                    is_done=True,
                    chunk_type="text",
                    message_id=assistant_msg_id,
                )
                break

            # 追加到完整回复缓冲
            if chunk.chunk_type == "thinking":
                full_thinking += chunk.delta
            else:
                full_content += chunk.delta

            yield MessageChunk(
                delta=chunk.delta,
                is_done=chunk.is_done,
                chunk_type=chunk.chunk_type,
                message_id=assistant_msg_id,
            )

            if chunk.is_done:
                break

        # ── 7. 持久化助手回复 ─────────────────
        if full_content or full_thinking:
            assistant_message = Message(
                id=assistant_msg_id,
                role=MessageRole.ASSISTANT,
                content=full_content,
                thinking_content=full_thinking if full_thinking else None,
                is_thinking=bool(full_thinking),
                created_at=datetime.now(),
            )
            self._repo.append_message(session_id, assistant_message)

        # ── 8. 更新对话摘要 ───────────────────
        await self._refresh_conversation_meta(session_id, full_content or text)

    async def regenerate_message(
        self,
        session_id: str,
        message_id: str,
    ) -> AsyncGenerator[MessageChunk, None]:
        """
        重新生成指定消息之后的助手回复：
            1. 从历史中截断 message_id 之后的所有消息
            2. 重新构建上下文
            3. 流式调用 LLM（配置同 send_message）
            4. 持久化新回复

        Args:
            session_id: 当前对话 ID
            message_id: 触发重新生成的消息 ID（通常是上一条助手消息）

        Yields:
            MessageChunk
        """
        self._stop_event.clear()

        # 截断到 message_id 之前
        detail = self._repo.get_conversation_detail(session_id)
        if detail is None:
            raise ConversationNotFoundError(session_id)

        truncated_messages = _truncate_after(detail.messages, message_id)
        # 将截断后的消息重新写回（由 repo 完成具体实现）
        await self._context_svc.reset_messages(session_id, truncated_messages)

        # 复用 send_message 的 LLM 调用逻辑
        messages = await self._context_svc.build_llm_context(session_id)
        model: str = app_config.model_type
        thinking_enabled: bool = app_config.thinking_enabled

        full_content = ""
        full_thinking = ""
        new_msg_id = _new_id()

        async for chunk in self._llm.stream_chat(
            messages=messages,
            model=model,
            thinking_enabled=thinking_enabled,
        ):
            if self._stop_event.is_set():
                yield MessageChunk(
                    delta="", is_done=True,
                    chunk_type="text", message_id=new_msg_id,
                )
                break

            if chunk.chunk_type == "thinking":
                full_thinking += chunk.delta
            else:
                full_content += chunk.delta

            yield MessageChunk(
                delta=chunk.delta,
                is_done=chunk.is_done,
                chunk_type=chunk.chunk_type,
                message_id=new_msg_id,
            )

            if chunk.is_done:
                break

        if full_content or full_thinking:
            new_message = Message(
                id=new_msg_id,
                role=MessageRole.ASSISTANT,
                content=full_content,
                thinking_content=full_thinking if full_thinking else None,
                is_thinking=bool(full_thinking),
                created_at=datetime.now(),
            )
            self._repo.append_message(session_id, new_message)

        await self._refresh_conversation_meta(session_id, full_content)

    def stop_generation(self) -> None:
        """
        中止当前进行中的流式生成。
        通过 asyncio.Event 通知 send_message / regenerate_message 退出循环。
        同时调用 LLM 客户端的 cancel() 关闭底层连接。
        """
        self._stop_event.set()
        self._llm.cancel()

    # ── 私有辅助 ──────────────────────────────

    async def _refresh_conversation_meta(
        self, session_id: str, last_content: str
    ) -> None:
        """更新对话的标题（首次）、预览、updated_at。"""
        conversation = self._repo.get_conversation(session_id)
        if conversation is None:
            return

        # 仅在标题为空时自动截取首条消息前 20 字作为标题
        if not conversation.title and last_content:
            conversation.title = last_content[:20].replace("\n", " ")

        conversation.last_message_preview = last_content[:60].replace("\n", " ")
        conversation.updated_at = datetime.now()
        self._repo.save_conversation(conversation)


# ──────────────────────────────────────────────
# 领域异常
# ──────────────────────────────────────────────

class ConversationNotFoundError(Exception):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Conversation not found: {session_id}")
        self.session_id = session_id


# ──────────────────────────────────────────────
# 模块级辅助（纯函数，无副作用）
# ──────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _compose_user_content(text: str, file_contents: list[str]) -> str:
    """将文本与附件内容拼合为用户消息正文。"""
    if not file_contents:
        return text
    attachments = "\n\n---\n".join(
        f"[附件内容 {i + 1}]\n{c}" for i, c in enumerate(file_contents)
    )
    return f"{text}\n\n{attachments}" if text else attachments


def _truncate_after(messages: list[Message], message_id: str) -> list[Message]:
    """
    返回截断到 message_id（含）之前的消息列表。
    若 message_id 不存在，返回原列表。
    """
    for i, msg in enumerate(messages):
        if msg.id == message_id:
            return messages[:i]
    return messages
