# ui/views/chat_view.py
"""
ChatView — 兼容 Flet 0.85+，支持流式 token 实时渲染。
"""
from __future__ import annotations

import flet as ft
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controllers.app_controller import AppController
    from ui.state.ui_state_store import UIStateStore


class MessageBubble(ft.Container):

    def __init__(self, message):
        is_user = message.role == "user"

        self._md = ft.Markdown(
            value=message.content if message.content else "▋",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        )

        role_label = ft.Text(
            "You" if is_user else message.model_label,
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
        )

        super().__init__(
            content=ft.Column(
                controls=[role_label, self._md],
                spacing=4,
                tight=True,
            ),
            padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            margin=ft.Margin(
                left=48 if is_user else 0,
                right=0 if is_user else 48,
                top=0,
                bottom=4,
            ),
            bgcolor=ft.Colors.with_opacity(
                0.06 if is_user else 0.03,
                ft.Colors.ON_SURFACE,
            ),
            border_radius=ft.BorderRadius(
                top_left=12, top_right=12,
                bottom_left=12, bottom_right=12,
            ),
        )

    def update_content(self, new_text: str) -> None:
        self._md.value = new_text if new_text else "▋"
        self._md.update()


class ChatView(ft.Column):

    def __init__(self, page: ft.Page, store: "UIStateStore", controller: "AppController"):
        super().__init__(expand=True, spacing=0)

        self._page       = page
        self._store      = store
        self._controller = controller

        self._message_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            auto_scroll=True,
        )

        self._input_field = ft.TextField(
            hint_text="发送消息...（Enter 发送，Shift+Enter 换行）",
            border_radius=12,
            expand=True,
            multiline=True,
            max_lines=6,
            min_lines=1,
            shift_enter=True,
            on_submit=self._handle_submit,
            content_padding=ft.Padding(left=16, right=16, top=12, bottom=12),
        )

        self._send_btn = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_size=20,
            bgcolor=ft.Colors.PRIMARY,
            icon_color=ft.Colors.ON_PRIMARY,
            on_click=self._handle_submit,
        )

        self._loading_ring = ft.ProgressRing(
            width=20, height=20, stroke_width=2,
            visible=False, color=ft.Colors.PRIMARY,
        )

        self._model_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="Flash", label=ft.Text("Flash", size=12)),
                ft.Segment(value="Pro",   label=ft.Text("Pro ✦", size=12)),
            ],
            selected=["Flash"],
            on_change=self._handle_model_change,
        )

        self._new_chat_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16),
                    ft.Text("新对话", size=13),
                ],
                spacing=4, tight=True,
            ),
            on_click=lambda _: self._controller.new_conversation(),
        )

        self._error_text = ft.Text(
            "", color=ft.Colors.ON_ERROR_CONTAINER, size=13, expand=True,
        )
        self._error_banner = ft.Container(
            visible=False,
            padding=ft.Padding(left=16, right=16, top=8, bottom=8),
            bgcolor=ft.Colors.ERROR_CONTAINER,
            border_radius=ft.BorderRadius(
                top_left=8, top_right=8, bottom_left=8, bottom_right=8,
            ),
            margin=ft.Margin(left=16, right=16, top=4, bottom=4),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.ERROR, size=16),
                    self._error_text,
                    ft.IconButton(
                        icon=ft.Icons.CLOSE, icon_size=16,
                        on_click=lambda _: self._dismiss_error(),
                    ),
                ],
                spacing=8,
            ),
        )

        divider = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)

        self.controls = [
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text("DeepSeek", size=15, weight=ft.FontWeight.W_600),
                        ft.Container(expand=True),
                        self._model_selector,
                        self._new_chat_btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                border=ft.Border(bottom=ft.BorderSide(1, divider)),
            ),
            self._message_list,
            self._error_banner,
            ft.Container(
                content=ft.Row(
                    controls=[
                        self._input_field,
                        ft.Column(
                            controls=[self._loading_ring, self._send_btn],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    spacing=8,
                ),
                padding=ft.Padding(left=16, right=16, top=12, bottom=12),
                border=ft.Border(top=ft.BorderSide(1, divider)),
            ),
        ]

        # 订阅 store 事件
        self._store.subscribe("messages",     self._on_messages_changed)
        self._store.subscribe("stream",       self._on_stream_updated)   # 新增
        self._store.subscribe("loading",      self._on_loading_changed)
        self._store.subscribe("error",        self._on_error_changed)
        self._store.subscribe("model_config", self._on_model_config_changed)

    # ── UI 事件 ───────────────────────────────────

    def _handle_submit(self, e) -> None:
        text = self._input_field.value or ""
        if not text.strip():
            return
        self._input_field.value = ""
        self._input_field.update()
        self._controller.send_message(text)

    def _handle_model_change(self, e) -> None:
        selected = list(e.control.selected)[0] if e.control.selected else "Flash"
        self._controller.switch_model(selected)

    def _dismiss_error(self) -> None:
        self._store.clear_error()

    # ── Store 订阅回调 ────────────────────────────

    def _on_messages_changed(self) -> None:
        """消息列表变化时重建气泡列表（新增/删除消息时触发）"""
        self._message_list.controls = [
            MessageBubble(msg) for msg in self._store.messages
        ]
        self._page.update()

    def _on_stream_updated(self) -> None:
        """
        流式 token 到达时只更新最后一个气泡，不重建列表。
        O(1) 操作，保证流式输出流畅。
        """
        if not self._message_list.controls:
            return
        last_bubble = self._message_list.controls[-1]
        streaming_msg = self._store.messages[-1] if self._store.messages else None
        if streaming_msg and isinstance(last_bubble, MessageBubble):
            last_bubble.update_content(streaming_msg.content)
        self._page.update()

    def _on_loading_changed(self) -> None:
        loading = self._store.is_loading
        self._loading_ring.visible    = loading
        self._send_btn.visible        = not loading
        self._input_field.disabled    = loading
        self._model_selector.disabled = loading
        self._page.update()

    def _on_error_changed(self) -> None:
        error = self._store.error
        if error:
            self._error_text.value     = error
            self._error_banner.visible = True
        else:
            self._error_banner.visible = False
        self._page.update()

    def _on_model_config_changed(self) -> None:
        self._model_selector.selected = [self._store.current_model]
        self._page.update()

    def destroy(self) -> None:
        self._store.unsubscribe("messages",     self._on_messages_changed)
        self._store.unsubscribe("stream",       self._on_stream_updated)
        self._store.unsubscribe("loading",      self._on_loading_changed)
        self._store.unsubscribe("error",        self._on_error_changed)
        self._store.unsubscribe("model_config", self._on_model_config_changed)
