# Layer: UI → widgets
# File: app/ui/widgets/chat_message.py
# Responsibility: 渲染单条消息气泡（用户 / 助手 / 思考块），支持流式逐字更新
# Input:  MessageVM（来自 Controller ViewModels）
# Output: ft.Control — 可直接插入 ListView
# 禁止: 任何业务逻辑、网络调用、core/adapters/storage 导入

from __future__ import annotations
import flet as ft
from app.ui.theme import Colors, Fonts, Spacing, Radius, Borders


# ──────────────────────────────────────────────
# 顶部"角色标签"徽章
# ──────────────────────────────────────────────
def _role_badge(role: str) -> ft.Control:
    label_map = {
        "user":      ("YOU",      Colors.ROLE_USER),
        "assistant": ("DEEP",     Colors.ROLE_ASSISTANT),
        "thinking":  ("THINKING", Colors.ROLE_THINKING),
    }
    text, color = label_map.get(role, ("???", Colors.TEXT_SECONDARY))
    return ft.Container(
        content=ft.Text(
            text,
            size=Fonts.SIZE_XS,
            font_family=Fonts.MONO,
            color=color,
            weight=ft.FontWeight.BOLD,
            letter_spacing=1.5,
        ),
        padding=ft.Padding(left=6, right=6, top=2, bottom=2),
        border=ft.Border(
            top=ft.BorderSide(1, color),
            bottom=ft.BorderSide(1, color),
            left=ft.BorderSide(1, color),
            right=ft.BorderSide(1, color),
        ),
        border_radius=Radius.SM,
    )


# ──────────────────────────────────────────────
# 思考块（可折叠）
# ──────────────────────────────────────────────
class ThinkingBlock(ft.Column):
    """
    可折叠的思考过程块。
    通过 append_text(delta) 追加流式内容。
    """

    def __init__(self) -> None:
        self._text_ref = ft.Ref[ft.Text]()
        self._content_ref = ft.Ref[ft.Container]()
        self._toggle_icon_ref = ft.Ref[ft.Icon]()
        self._expanded = True
        self._buffer = ""

        super().__init__(
            spacing=0,
            controls=[
                # 折叠头
                ft.Container(
                    content=ft.Row(
                        controls=[
                            _role_badge("thinking"),
                            ft.Container(expand=True),
                            ft.Icon(
                                ref=self._toggle_icon_ref,
                                name=ft.Icons.EXPAND_LESS,
                                size=16,
                                color=Colors.TEXT_SECONDARY,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(left=Spacing.MD, right=Spacing.MD,
                                       top=Spacing.SM, bottom=Spacing.SM),
                    border=Borders.BOTTOM_ONLY,
                    on_click=self._on_toggle,
                    ink=True,
                ),
                # 内容区（可折叠）
                ft.Container(
                    ref=self._content_ref,
                    content=ft.Text(
                        ref=self._text_ref,
                        value="",
                        size=Fonts.SIZE_SM,
                        font_family=Fonts.MONO,
                        color=Colors.TEXT_SECONDARY,
                        selectable=True,
                        no_wrap=False,
                    ),
                    padding=ft.Padding(left=Spacing.MD, right=Spacing.MD,
                                       top=Spacing.SM, bottom=Spacing.SM),
                    visible=True,
                ),
            ],
            # 左侧思考色竖线
            # 使用外层 Container 包裹实现，见 ChatMessage
        )

    def append_text(self, delta: str) -> None:
        """流式追加思考内容（由外部在事件循环中调用后需 update）"""
        self._buffer += delta
        if self._text_ref.current:
            self._text_ref.current.value = self._buffer

    def _on_toggle(self, e: ft.ControlEvent) -> None:
        self._expanded = not self._expanded
        if self._content_ref.current:
            self._content_ref.current.visible = self._expanded
        if self._toggle_icon_ref.current:
            self._toggle_icon_ref.current.name = (
                ft.Icons.EXPAND_LESS if self._expanded else ft.Icons.EXPAND_MORE
            )
        e.control.page.update()


# ──────────────────────────────────────────────
# 主消息气泡
# ──────────────────────────────────────────────
class ChatMessage(ft.Container):
    """
    单条消息气泡，支持三种角色：user / assistant / thinking。

    流式使用方式：
        msg = ChatMessage(role="assistant", content="")
        # 每次收到 delta：
        msg.append_stream(delta)
        page.update()
        # 完成时：
        msg.finalize_stream()
        page.update()
    """

    def __init__(
        self,
        role: str,
        content: str,
        message_id: str = "",
        is_thinking: bool = False,
        on_copy: ft.OptionalEventCallable = None,
        on_regenerate: ft.OptionalEventCallable = None,
    ) -> None:
        self.role = role
        self.message_id = message_id
        self._is_streaming = False
        self._stream_buffer = content

        self._md_re