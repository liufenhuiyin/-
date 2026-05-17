# Layer: UI
# File: app/ui/app.py
# Responsibility: Flet 页面挂载、顶级布局组装、Controller 绑定、流式事件分发
# Input:  AppController, SettingsController（依赖注入）
# Output: 运行中的 Flet Page
# 禁止: 任何业务逻辑、core/adapters/storage 导入

from __future__ import annotations
import asyncio
import flet as ft

from app.ui.theme import Colors, Fonts, Spacing, build_theme
from app.ui.widgets.chat_message import ChatMessage
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.input_area import InputArea
from app.ui.widgets.context_panel import ContextPanel


class ChatApp:
    """
    顶级 UI 组装器。

    职责：
    - 将各 Widget 拼装为完整页面布局
    - 将用户事件路由到 AppController / SettingsController
    - 接收 Controller 推送的 ViewModels，分发给对应 Widget

    注入接口（Controller 需实现）：
        app_controller.on_new_conversation() -> str  (返回新 session_id)
        app_controller.on_switch_conversation(session_id: str)
        app_controller.on_delete_conversation(session_id: str)
        app_controller.on_send_message(session_id, text, files) -> AsyncGenerator
        app_controller.on_stop_generation()
        app_controller.on_regenerate_message(session_id, message_id)
        app_controller.on_load_history() -> list[ConversationVM]
        settings_controller.on_change_model(model_type: str)
        settings_controller.on_toggle_thinking(enabled: bool)
    """

    def __init__(self, app_controller, settings_controller) -> None:
        self._ctrl = app_controller
        self._settings_ctrl = settings_controller
        self._current_session_id: str = ""
        self._streaming_message: ChatMessage | None = None

        # 组件引用（在 build 时赋值）
        self._sidebar: Sidebar | None = None
        self._input_area: InputArea | None = None
        self._context_panel: ContextPanel | None = None
        self._message_list_ref = ft.Ref[ft.ListView]()
        self._empty_hint_ref = ft.Ref[ft.Container]()
        self._page: ft.Page | None = None

    # ──────────────────────────────────────────
    # 页面构建
    # ──────────────────────────────────────────

    def build(self, page: ft.Page) -> None:
        self._page = page
        self._configure_page(page)

        # ── 实例化各 Widget ────────────────────
        self._sidebar = Sidebar(
            on_new_conversation=self._handle_new_conversation,
            on_switch_conversation=self._handle_switch_conversation,
            on_delete_conversation=self._handle_delete_conversation,
            on_open_context_panel=self._handle_open_context_panel,
        )

        self._input_area = InputArea(
            on_send=self._handle_send,
            on_stop=self._handle_stop,
            on_model_change=self._settings_ctrl.on_change_model,
            on_thinking_change=self._settings_ctrl.on_toggle_thinking,
        )

        self._context_panel = ContextPanel(
            on_remove_block=self._handle_remove_context_block,
            on_toggle_block=self._handle_toggle_context_block,
            on_apply_template=self._handle_apply_template,
            on_add_text_block=self._handle_add_text_block,
            on_close=self._handle_close_context_panel,
        )

        # ── 消息列表区 ─────────────────────────
        message_list = ft.ListView(
            ref=self._message_list_ref,
            expand=True,
            spacing=Spacing.SM,
            padding=ft.Padding(
                left=Spacing.XL, right=Spacing.XL,
                top=Spacing.LG, bottom=Spacing.LG,
            ),
            auto_scroll=True,
        )

        # 空状态提示
        empty_hint = ft.Container(
            ref=self._empty_hint_ref,
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            "DR",
                            size=32,
                            font_family=Fonts.MONO,
                            color=Colors.PRIMARY,
                            weight=ft.FontWeight.BOLD,
                        ),
                        width=64, height=64,
                        border_radius=ft.BorderRadius(
                            top_left=12, top_right=12,
                            bottom_left=12, bottom_right=12,
                        ),
                        bgcolor=Colors.PRIMARY_GLOW,
                        alignment=ft.Alignment(0, 0),
                        border=ft.Border(
                            top=ft.BorderSide(1, Colors.PRIMARY),
                            bottom=ft.BorderSide(1, Colors.PRIMARY),
                            left=ft.BorderSide(1, Colors.PRIMARY),
                            right=ft.BorderSide(1, Colors.PRIMARY),
                        ),
                    ),
                    ft.Text(
                        "DeepResearch",
                        size=Fonts.SIZE_XXL,
                        font_family=Fonts.MONO,
                        color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(
                        "选择或新建一个对话以开始",
                        size=Fonts.SIZE_MD,
                        color=Colors.TEXT_SECONDARY,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.MD,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
            visible=True,
        )

        # ── 聊天主区域 ─────────────────────────
        chat_area = ft.Stack(
            controls=[
                empty_hint,
                ft.Container(content=message_list, expand=True),
            ],
            expand=True,
        )

        # ── 右侧内容区（聊天 + 输入 + 上下文面板）
        content_area = ft.Row(
            controls=[
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        chat_area,
                        self._input_area,
                    ],
                ),
                self._context_panel,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # ── 最终页面布局 ───────────────────────
        page.add(
            ft.Row(
                controls=[
                    self._sidebar,
                    ft.VerticalDivider(width=1, color=Colors.BORDER),
                    content_area,
                ],
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )

        # 加载历史对话列表
        self._load_history()

    # ──────────────────────────────────────────
    # 页面配置
    # ──────────────────────────────────────────

    def _configure_page(self, page: ft.Page) -> None:
        page.title = "DeepResearch"
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = build_theme()
        page.bgcolor = Colors.BG_BASE
        page.padding = 0
        page.spacing = 0
        page.fonts = {
            "JetBrains Mono": "https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ.woff2",
            "Noto Sans SC": "https://fonts.gstatic.com/s/notosanssc/v36/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG9_FnYxNbPzS5HE.woff2",
        }
        page.window.min_width = 900
        page.window.min_height = 600

    # ──────────────────────────────────────────
    # 事件处理（纯路由，不含逻辑）
    # ──────────────────────────────────────────

    def _load_history(self) -> None:
        conversations = self._ctrl.on_load_history()
        if self._sidebar:
            self._sidebar.load_conversations(conversations)

    def _handle_new_conversation(self) -> None:
        session_id = self._ctrl.on_new_conversation()
        self._current_session_id = session_id
        self._clear_message_list()
        self._set_empty_hint(True)
        if self._sidebar:
            self._sidebar.set_active(session_id)
        self._load_history()

    def _handle_switch_conversation(self, session_id: str) -> None:
        self._current_session_id = session_id
        result = self._ctrl.on_switch_conversation(session_id)
        # result 预期为 list[MessageVM]
        self._rebuild_message_list(result.messages if result else [])
        if self._sidebar:
            self._sidebar.set_active(session_id)
        if self._page:
            self._page.update()

    def _handle_delete_conversation(self, session_id: str) -> None:
        self._ctrl.on_delete_conversation(session_id)
        if session_id == self._current_session_id:
            self._current_session_id = ""
            self._clear_message_list()
            self._set_empty_hint(True)
        self._load_history()
        if self._page:
            self._page.update()

    def _handle_send(self, text: str, files: list[str]) -> None:
        if not self._current_session_id:
            self._handle_new_conversation()
        if not text and not files:
            return

        # 1. 立刻渲染用户消息气泡
        self._append_message(ChatMessage(role="user", content=text))
        self._set_empty_hint(False)

        # 2. 清空输入区
        if self._input_area:
            self._input_area.clear()
            self._input_area.set_generating(True)

        # 3. 启动流式生成（异步）
        if self._page:
            self._page.run_task(
                self._stream_response,
                self._current_session_id,
                text,
                files,
            )

    def _handle_stop(self) -> None:
        self._ctrl.on_stop_generation()
        if self._input_area:
            self._input_area.set_generating(False)
        if self._streaming_message:
            self._streaming_message.finalize_stream()
            self._streaming_message = None

    async def _stream_response(
        self, session_id: str, text: str, files: list[str]
    ) -> None:
        """消费 Controller 返回的异步流，逐 delta 更新气泡"""
        # 创建助手气泡（空内容占位）
        assistant_msg = ChatMessage(
            role="assistant",
            content="",
            on_copy=self._make_copy_handler(),
            on_regenerate=self._make_regenerate_handler(session_id),
        )
        assistant_msg.start_stream()
        self._streaming_message = assistant_msg
        self._append_message(assistant_msg)

        try:
            async for chunk_vm in self._ctrl.on_send_message(session_id, text, files):
                if chunk_vm.is_done:
                    break
                assistant_msg.append_stream(chunk_vm.delta)
                if self._page:
                    self._page.update()
                await asyncio.sleep(0)  # 让出事件循环
        finally:
            assistant_msg.finalize_stream()
            self._streaming_message = None
            if self._input_area:
                self._input_area.set_generating(False)
            if self._page:
                self._page.update()

    def _handle_open_context_panel(self) -> None:
        if self._context_panel:
            self._context_panel.show()

    def _handle_close_context_panel(self) -> None:
        if self._context_panel:
            self._context_panel.hide()

    def _handle_remove_context_block(self, block_id: str) -> None:
        # 转发给 Controller（待 context_controller 实现后对接）
        pass

    def _handle_toggle_context_block(self, block_id: str, enabled: bool) -> None:
        pass

    def _handle_apply_template(self, template_id: str) -> None:
        pass

    def _handle_add_text_block(self, text: str) -> None:
        pass

    # ──────────────────────────────────────────
    # 视图辅助
    # ──────────────────────────────────────────

    def _append_message(self, msg: ChatMessage) -> None:
        if self._message_list_ref.current:
            self._message_list_ref.current.controls.append(msg)
            self._message_list_ref.current.update()

    def _clear_message_list(self) -> None:
        if self._message_list_ref.current:
            self._message_list_ref.current.controls.clear()
            self._message_list_ref.current.update()

    def _rebuild_message_list(self, message_vms: list) -> None:
        """根据 list[MessageVM] 重建消息列表"""
        if not self._message_list_ref.current:
            return
        self._message_list_ref.current.controls.clear()
        has_messages = bool(message_vms)
        self._set_empty_hint(not has_messages)
        for vm in message_vms:
            self._message_list_ref.current.controls.append(
                ChatMessage(
                    role=vm.role,
                    content=vm.content,
                    message_id=vm.id,
                    is_thinking=getattr(vm, "is_thinking", False),
                    on_copy=self._make_copy_handler(),
                    on_regenerate=self._make_regenerate_handler(
                        self._current_session_id
                    ),
                )
            )
        self._message_list_ref.current.update()

    def _set_empty_hint(self, visible: bool) -> None:
        if self._empty_hint_ref.current:
            self._empty_hint_ref.current.visible = visible
            self._empty_hint_ref.current.update()

    def _make_copy_handler(self):
        def _handler(e: ft.ControlEvent):
            if isinstance(e.control.parent, ChatMessage):
                self._page.set_clipboard(e.control.parent.current_content)
        return _handler

    def _make_regenerate_handler(self, session_id: str):
        def _handler(e: ft.ControlEvent):
            self._ctrl.on_regenerate_message(session_id, "")
        return _handler
