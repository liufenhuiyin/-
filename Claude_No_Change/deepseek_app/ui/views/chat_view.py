# ui/views/chat_view.py
"""
ChatView — 兼容 Flet 0.85+
完全避免 ft.border.only() / ft.padding.symmetric() 等模块级方法调用。
全部改用类实例化形式。
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

        role_label = ft.Text(
            "You" if is_user else message.model_label,
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
        )

        content = ft.Markdown(
            value=message.content,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        )

        super().__init__(
            content=ft.Column(
                controls=[role_label, content],
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


class ChatView(ft.Column):

    def __init__(self, page: ft.Page, store: "UIStateStore", controller: "AppController"):
        super().__init__(expand=True, spacing=0)

        self._page       = page
        self._store      = store
        self._controller = controller

        # ── 消息列表 ──────────────────────────────
        self._message_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            auto_scroll=True,
        )

        # ── 输入框 ────────────────────────────────
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

        # ── 发送按钮 ──────────────────────────────
        self._send_btn = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_size=20,
            bgcolor=ft.Colors.PRIMARY,
            icon_color=ft.Colors.ON_PRIMARY,
            on_click=self._handle_submit,
        )

        # ── 加载指示器 ────────────────────────────
        self._loading_ring = ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            visible=False,
            color=ft.Colors.PRIMARY,
        )

        # ── 模型切换 ──────────────────────────────
        self._model_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="Flash", label=ft.Text("Flash", size=12)),
                ft.Segment(value="Pro",   label=ft.Text("Pro ✦", size=12)),
            ],
            selected={"Flash"},
            on_change=self._handle_model_change,
        )

        # ── 新对话按钮 ────────────────────────────
        self._new_chat_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16),
                    ft.Text("新对话", size=13),
                ],
                spacing=4,
                tight=True,
            ),
            on_click=lambda _: self._controller.new_conversation(),
        )

        # ── 错误提示 ──────────────────────────────
        self._error_text = ft.Text(
            "",
            color=ft.Colors.ON_ERROR_CONTAINER,
            size=13,
            expand=True,
        )
        self._error_banner = ft.Container(
            visible=False,
            padding=ft.Padding(left=16, right=16, top=8, bottom=8),
            bgcolor=ft.Colors.ERROR_CONTAINER,
            border_radius=ft.BorderRadius(
                top_left=8, top_right=8,
                bottom_left=8, bottom_right=8,
            ),
            margin=ft.Margin(left=16, right=16, top=4, bottom=4),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.ERROR, size=16),
                    self._error_text,
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=16,
                        on_click=lambda _: self._dismiss_error(),
                    ),
                ],
                spacing=8,
            ),
        )

        # ── 顶部工具栏 ────────────────────────────
        toolbar = ft.Row(
            controls=[
                ft.Text("DeepSeek", size=15, weight=ft.FontWeight.W_600),
                ft.Container(expand=True),
                self._model_selector,
                self._new_chat_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── 底部输入区 ────────────────────────────
        input_row = ft.Row(
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
        )

        # ── 用 Container + border 属性替代 ft.border.only() ──
        # ft.Border() 直接传各边的 BorderSide
        divider_color = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)

        self.controls = [
            ft.Container(
                content=toolbar,
                padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                border=ft.Border(
                    bottom=ft.BorderSide(1, divider_color),
                ),
            ),
            self._message_list,
            self._error_banner,
            ft.Container(
                content=input_row,
                padding=ft.Padding(left=16, right=16, top=12, bottom=12),
                border=ft.Border(
                    top=ft.BorderSide(1, divider_color),
                ),
            ),
        ]

        # ── 订阅 Store ────────────────────────────
        self._store.subscribe("messages",     self._on_messages_changed)
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
        self._message_list.controls = [
            MessageBubble(msg) for msg in self._store.messages
        ]
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
        self._model_selector.selected = {self._store.current_model}
        self._page.update()

    def destroy(self) -> None:
        self._store.unsubscribe("messages",     self._on_messages_changed)
        self._store.unsubscribe("loading",      self._on_loading_changed)
        self._store.unsubscribe("error",        self._on_error_changed)
        self._store.unsubscribe("model_config", self._on_model_config_changed)
