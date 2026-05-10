# ui/views/chat_view.py
"""
ChatView — 主聊天界面。

规则：
  - 不包含任何业务逻辑
  - 所有用户操作委托给 AppController
  - 所有数据从 UIStateStore 读取
  - page.update() 只在订阅回调里调用
"""
from __future__ import annotations

import flet as ft
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controllers.app_controller import AppController
    from ui.state.ui_state_store import UIStateStore


class MessageBubble(ft.Container):
    """
    单条消息气泡。
    支持 user / assistant 两种样式。
    """

    def __init__(self, message):
        is_user = message.role == "user"

        # 角色标签
        role_label = ft.Text(
            "You" if is_user else message.model_label,
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
        )

        # 消息内容（Markdown 渲染）
        content = ft.Markdown(
            value=message.content,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            on_tap_link=lambda e: ft.app,
            code_theme=ft.MarkdownCodeTheme.ATOM_ONE_DARK,
            code_style_sheet=ft.MarkdownStyleSheet(
                code_text_style=ft.TextStyle(
                    font_family="monospace",
                    size=13,
                ),
            ),
        )

        bubble_content = ft.Column(
            controls=[role_label, content],
            spacing=4,
            tight=True,
        )

        super().__init__(
            content=bubble_content,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            margin=ft.margin.only(
                left=48 if is_user else 0,
                right=0 if is_user else 48,
                bottom=4,
            ),
            bgcolor=ft.Colors.with_opacity(
                0.06 if is_user else 0.03,
                ft.Colors.ON_SURFACE,
            ),
            border_radius=ft.border_radius.all(12),
        )

    def update_content(self, new_text: str) -> None:
        """流式更新时调用（MVP 暂不使用，为后续扩展保留）"""
        col = self.content
        if isinstance(col, ft.Column) and len(col.controls) > 1:
            md = col.controls[1]
            if isinstance(md, ft.Markdown):
                md.value = new_text


class ChatView(ft.Column):
    """
    聊天主视图。

    订阅的 UIStateStore 事件：
      - messages  → 重建消息列表
      - loading   → 切换输入禁用 / loading 指示器
      - error     → 显示错误提示
      - model_config → 更新模型选择器显示
    """

    def __init__(
        self,
        page:       ft.Page,
        store:      "UIStateStore",
        controller: "AppController",
    ):
        super().__init__(expand=True, spacing=0)

        self._page       = page
        self._store      = store
        self._controller = controller

        # ── UI 组件定义 ────────────────────────────
        self._message_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            auto_scroll=True,
        )

        self._input_field = ft.TextField(
            hint_text="发送消息...",
            border_radius=12,
            expand=True,
            multiline=True,
            max_lines=6,
            min_lines=1,
            shift_enter=True,             # Shift+Enter 换行，Enter 发送
            on_submit=self._handle_submit,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=12),
        )

        self._send_btn = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_size=20,
            bgcolor=ft.Colors.PRIMARY,
            icon_color=ft.Colors.ON_PRIMARY,
            on_click=self._handle_submit,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.all(10),
            ),
        )

        self._loading_ring = ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            visible=False,
            color=ft.Colors.PRIMARY,
        )

        self._model_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(value="Flash", label=ft.Text("Flash", size=12)),
                ft.Segment(value="Pro",   label=ft.Text("Pro ✦", size=12)),
            ],
            selected={"Flash"},
            on_change=self._handle_model_change,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
            ),
        )

        self._new_chat_btn = ft.TextButton(
            text="新对话",
            icon=ft.Icons.ADD_ROUNDED,
            on_click=lambda _: self._controller.new_conversation(),
            style=ft.ButtonStyle(
                color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
            ),
        )

        self._error_banner = ft.Container(
            visible=False,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            bgcolor=ft.Colors.ERROR_CONTAINER,
            border_radius=8,
            margin=ft.margin.symmetric(horizontal=16),
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.ERROR, size=16),
                    ft.Text("", color=ft.Colors.ON_ERROR_CONTAINER, size=13, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=16,
                        on_click=lambda _: self._dismiss_error(),
                    ),
                ],
                spacing=8,
            ),
        )

        # ── 布局组装 ───────────────────────────────
        toolbar = ft.Row(
            controls=[
                ft.Text(
                    "DeepSeek",
                    size=15,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Container(expand=True),
                self._model_selector,
                self._new_chat_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        input_row = ft.Row(
            controls=[
                self._input_field,
                ft.Column(
                    controls=[self._loading_ring, self._send_btn],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.END,
            spacing=8,
        )

        self.controls = [
            ft.Container(
                content=toolbar,
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                border=ft.border.only(
                    bottom=ft.BorderSide(
                        1,
                        ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    )
                ),
            ),
            self._message_list,
            self._error_banner,
            ft.Container(
                content=input_row,
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border=ft.border.only(
                    top=ft.BorderSide(
                        1,
                        ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    )
                ),
            ),
        ]

        # ── 订阅 UIStateStore ──────────────────────
        self._store.subscribe("messages",     self._on_messages_changed)
        self._store.subscribe("loading",      self._on_loading_changed)
        self._store.subscribe("error",        self._on_error_changed)
        self._store.subscribe("model_config", self._on_model_config_changed)

    # ──────────────────────────────────────────────
    # UI 事件处理（只做输入校验 + 委托 Controller）
    # ──────────────────────────────────────────────

    def _handle_submit(self, e) -> None:
        """发送按钮 / Enter 键处理"""
        text = self._input_field.value or ""
        if not text.strip():
            return
        self._input_field.value = ""
        self._input_field.update()
        # 唯一的业务委托：把文本交给 Controller
        self._controller.send_message(text)

    def _handle_model_change(self, e) -> None:
        """模型切换（Flash / Pro）"""
        selected = list(e.control.selected)[0] if e.control.selected else "Flash"
        self._controller.switch_model(selected)

    def _dismiss_error(self) -> None:
        self._store.clear_error()

    # ──────────────────────────────────────────────
    # UIStateStore 订阅回调（只读 store，只渲染，只 update）
    # ──────────────────────────────────────────────

    def _on_messages_changed(self) -> None:
        """消息列表变化 → 重建气泡列表"""
        self._message_list.controls = [
            MessageBubble(msg)
            for msg in self._store.messages
        ]
        self._page.update()

    def _on_loading_changed(self) -> None:
        """加载状态变化 → 切换 loading 指示器和输入禁用"""
        loading = self._store.is_loading
        self._loading_ring.visible    = loading
        self._send_btn.visible        = not loading
        self._input_field.disabled    = loading
        self._model_selector.disabled = loading
        self._page.update()

    def _on_error_changed(self) -> None:
        """错误状态变化 → 显示/隐藏 error banner"""
        error = self._store.error
        if error:
            error_text = self._error_banner.content.controls[1]
            error_text.value              = error
            self._error_banner.visible    = True
        else:
            self._error_banner.visible    = False
        self._page.update()

    def _on_model_config_changed(self) -> None:
        """模型配置变化 → 更新选择器显示"""
        model = self._store.current_model
        self._model_selector.selected = {model}
        self._page.update()

    def destroy(self) -> None:
        """视图销毁时取消订阅，防止内存泄漏"""
        self._store.unsubscribe("messages",     self._on_messages_changed)
        self._store.unsubscribe("loading",      self._on_loading_changed)
        self._store.unsubscribe("error",        self._on_error_changed)
        self._store.unsubscribe("model_config", self._on_model_config_changed)
