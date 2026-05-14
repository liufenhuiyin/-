# Layer: Controller
# File: app/controllers/app_controller.py
# Responsibility: 主控制器，接收 UI 事件，调用 Core 服务，将领域结果映射为 View Model。
#                 不含任何业务逻辑、不直接访问 adapter/storage/config 业务值。
# Input:  UI 原始参数（str, bool, list[str]）
# Output: View Model 实例或 AsyncGenerator[StreamChunkVM]
# 禁止: 业务判断、配置解析、直接调用 adapter/storage、维护全局状态对象。

from __future__ import annotations
from typing import AsyncGenerator

from app.controllers.command_builder import CommandBuilder
from app.controllers.view_models import (
    ConversationVM,
    ConversationDetailVM,
    MessageVM,
    StreamChunkVM,
)


class AppController:
    """
    主应用控制器。

    通过依赖注入持有 Core 层服务，不自行实例化任何服务。
    每个公开方法对应一个 UI 事件，仅做：
        1. 用 CommandBuilder 打包参数（可选）
        2. 调用 Core 服务对应方法
        3. 将返回的领域对象映射为 View Model

    用法（在 main.py 中）：
        conversation_service = ConversationService(...)
        controller = AppController(conversation_service=conversation_service)
        chat_app = ChatApp(app_controller=controller, ...)
    """

    def __init__(self, conversation_service) -> None:
        """
        Args:
            conversation_service: core.conversation_service.ConversationService 实例
        """
        self._conversation_svc = conversation_service

    # ──────────────────────────────────────────
    # 对话生命周期
    # ──────────────────────────────────────────

    def on_new_conversation(self) -> str:
        """
        UI 点击"新建对话"时调用。

        Returns:
            新对话的 session_id（str），UI 用于标记当前激活会话。
        """
        conversation = self._conversation_svc.create_conversation()
        return conversation.id

    def on_switch_conversation(self, session_id: str) -> ConversationDetailVM:
        """
        UI 点击侧边栏某条对话时调用。

        Args:
            session_id: 目标对话 ID

        Returns:
            ConversationDetailVM，包含完整消息列表，UI 据此重建聊天区。
        """
        cmd = CommandBuilder.build_switch_command(session_id)
        detail = self._conversation_svc.switch_conversation(**cmd)
        return self._map_to_detail_vm(detail)

    def on_delete_conversation(self, session_id: str) -> None:
        """
        UI 点击删除对话时调用。

        Args:
            session_id: 要删除的对话 ID
        """
        cmd = CommandBuilder.build_delete_command(session_id)
        self._conversation_svc.delete_conversation(**cmd)

    def on_load_history(self) -> list[ConversationVM]:
        """
        UI 初始化或刷新侧边栏列表时调用。

        Returns:
            list[ConversationVM]，按更新时间倒序。
        """
        conversations = self._conversation_svc.list_conversations()
        return [self._map_to_conversation_vm(c) for c in conversations]

    # ──────────────────────────────────────────
    # 消息生成
    # ──────────────────────────────────────────

    async def on_send_message(
        self,
        session_id: str,
        text: str,
        files: list[str],
    ) -> AsyncGenerator[StreamChunkVM, None]:
        """
        UI 发送消息时调用，返回流式 AsyncGenerator。

        Args:
            session_id: 当前对话 ID
            text:       用户输入的文本内容
            files:      附件文件路径列表（可为空）

        Yields:
            StreamChunkVM — 逐块返回，is_done=True 表示结束
        """
        cmd = CommandBuilder.build_send_command(session_id, text, files)
        async for chunk in self._conversation_svc.send_message(**cmd):
            yield self._map_to_stream_chunk_vm(chunk)

    async def on_regenerate_message(
        self,
        session_id: str,
        message_id: str,
    ) -> AsyncGenerator[StreamChunkVM, None]:
        """
        UI 点击"重新生成"时调用。

        Args:
            session_id: 当前对话 ID
            message_id: 要重新生成的消息 ID

        Yields:
            StreamChunkVM — 流式块，同 on_send_message
        """
        cmd = CommandBuilder.build_regenerate_command(session_id, message_id)
        async for chunk in self._conversation_svc.regenerate_message(**cmd):
            yield self._map_to_stream_chunk_vm(chunk)

    def on_stop_generation(self) -> None:
        """
        UI 点击"停止生成"时调用。
        直接透传给 Core 服务，不含任何逻辑。
        """
        self._conversation_svc.stop_generation()

    # ──────────────────────────────────────────
    # View Model 映射（纯数据转换，无业务判断）
    # ──────────────────────────────────────────

    @staticmethod
    def _map_to_conversation_vm(domain_obj) -> ConversationVM:
        """
        领域对象 Conversation -> ConversationVM。

        预期 domain_obj 字段:
            id: str
            title: str
            last_message_preview: str
            updated_at: datetime
        """
        return ConversationVM(
            id=domain_obj.id,
            title=domain_obj.title or "新对话",
            preview=domain_obj.last_message_preview or "",
            updated_at=_format_datetime(domain_obj.updated_at),
        )

    @staticmethod
    def _map_to_detail_vm(domain_obj) -> ConversationDetailVM:
        """
        领域对象 ConversationDetail -> ConversationDetailVM。

        预期 domain_obj 字段:
            id: str
            title: str
            messages: list[Message]
        """
        return ConversationDetailVM(
            id=domain_obj.id,
            title=domain_obj.title or "新对话",
            messages=[
                AppController._map_to_message_vm(m)
                for m in (domain_obj.messages or [])
            ],
        )

    @staticmethod
    def _map_to_message_vm(domain_obj) -> MessageVM:
        """
        领域对象 Message -> MessageVM。

        预期 domain_obj 字段:
            id: str
            role: str
            content: str
            is_thinking: bool
            created_at: datetime
        """
        return MessageVM(
            id=domain_obj.id,
            role=domain_obj.role,
            content=domain_obj.content,
            is_thinking=getattr(domain_obj, "is_thinking", False),
            created_at=_format_datetime(getattr(domain_obj, "created_at", None)),
        )

    @staticmethod
    def _map_to_stream_chunk_vm(domain_obj) -> StreamChunkVM:
        """
        领域对象 MessageChunk -> StreamChunkVM。

        预期 domain_obj 字段:
            delta: str
            is_done: bool
            chunk_type: str   ("text" | "thinking")
            message_id: str
        """
        return StreamChunkVM(
            delta=getattr(domain_obj, "delta", ""),
            is_done=getattr(domain_obj, "is_done", False),
            chunk_type=getattr(domain_obj, "chunk_type", "text"),
            message_id=getattr(domain_obj, "message_id", ""),
        )


# ──────────────────────────────────────────────
# 模块级辅助（不含业务知识，仅格式化）
# ──────────────────────────────────────────────

def _format_datetime(dt) -> str:
    """将 datetime 对象格式化为展示字符串，dt 为 None 时返回空串。"""
    if dt is None:
        return ""
    try:
        return dt.strftime("%m-%d %H:%M")
    except AttributeError:
        return str(dt)
