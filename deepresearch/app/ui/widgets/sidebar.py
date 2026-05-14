# Layer: UI → widgets
# File: app/ui/widgets/sidebar.py
# Responsibility: 侧边栏，包含对话历史列表、新建对话按钮、上下文管理面板入口
# Input:  list[ConversationVM]，Controller 回调
# Output: ft.Control — 左侧固定栏
# 禁止: 任何业务逻辑、core/adapters/storage 导入

from __future__ import annotations
from typing import Callable
import flet as ft
from app.ui.theme import Colors, Fonts, Spacing, Radius, Borders


class ConversationItem(ft.Container):
    """单条对话历史条目"""

    def __init__(
        self,
        session_id: str,
        title: str,
        preview: str,
        updated_at: str,
        is_active: bool,
        on_click: Callable[[str], None],
        on_delete: Callable[[str], None],
    ) -> None:
        self.session_id = session_id
        self._delete_visible_ref = ft.Ref[ft.IconButton]()

        bg = Colors.BG_OVERLAY if is_active else "transparent"
        border = (
            ft.Border(
                top=ft.BorderSide(0, "transparent"),
                bottom=ft.BorderSide(0, "transparent"),
                right=ft.BorderSide(0, "transparent"),
                left=ft.BorderSide(2, Colors.PRIMARY),
            )
            if is_active else
            ft.Border(
                top=ft.BorderSide(0, "transparent"),
                bottom=ft.BorderSide(1, Colors.DIVIDER),
                left=ft.BorderSide(2, "transparent"),
                right=ft.BorderSide(0, "transparent"),
            )
        )

        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text(
                                title or "新对话",
                                size=Fonts.SIZE_MD,
                                color=Colors.TEXT_PRIMARY if is_active else Colors.TEXT_SECONDARY,
                                weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.NORMAL,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                preview,
                                size=Fonts.SIZE_XS,
                                color=Colors.TEXT_DISABLED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            ft.Text(
                                updated_at,
                                size=Fonts.SIZE_XS,
                                color=Colors.TEXT_DISABLED,
                                font_family=Fonts.MONO,
                            ),
                            ft.IconButton(
                                ref=self._delete_visible_ref,
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=14,
                                icon_color=Colors.ERROR,
                                tooltip="删除对话",
                                visible=False,
                                style=ft.ButtonStyle(
                                    padding=ft.Padding(left=2, right=2, top=2, bottom=2),
                                ),
                                on_click=lambda e: on_delete(session_id),
                            ),
                        ],
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.SM,
            ),
            padding=ft.Padding(
                left=Spacing.MD, right=Spacing.SM,
                top=Spacing.SM, bottom=Spacing.SM,
            ),
            bgcolor=bg,
            border=border,
            on_click=lambda e: on_click(session_id),
            on_hover=self._on_hover,
            ink=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _on_hover(self, e: ft.HoverEvent) -> None:
        if self._delete_visible_ref.current:
            self._delete_visible_ref.current.visible = e.data == "true"
            e.control.update()


class Sidebar(ft.Container):
    """
    左侧边栏。

    公开接口：
        load_conversations(items: list[ConversationVM]) -> None
        set_active(session_id: str) -> None
    """

    def __init__(
        self,
        on_new_conversation: Callable[[], None],
        on_switch_conversation: Callable[[str], None],
        on_delete_conversation: Callable[[str], None],
        on_open_context_panel: Callable[[], None],
    ) -> None:
        self._on_switch = on_switch_conversation
        self._on_delete = on_delete_conversation
        self._active_id: str = ""

        self._list_ref = ft.Ref[ft.ListView]()

        # ── 顶部 Logo / 标题 ─