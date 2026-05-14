# Layer: UI → widgets
# File: app/ui/widgets/context_panel.py
# Responsibility: 上下文管理面板（抽屉式），显示已选上下文块、拼接预览、模板列表
# Input:  list[ContextBlockVM]，Controller 回调
# Output: ft.Control — 右侧覆盖抽屉（BottomSheet / Drawer）
# 禁止: 任何业务逻辑、core/adapters/storage 导入

from __future__ import annotations
from typing import Callable
import flet as ft
from app.ui.theme import Colors, Fonts, Spacing, Radius, Borders


# ──────────────────────────────────────────────
# 单个上下文块条目
# ──────────────────────────────────────────────
class _ContextBlockItem(ft.Container):
    def __init__(
        self,
        block_id: str,
        label: str,
        preview: str,
        on_remove: Callable[[str], None],
        on_toggle: Callable[[str, bool], None],
        enabled: bool = True,
    ) -> None:
        self._block_id = block_id
        self._enabled = enabled
        self._toggle_ref = ft.Ref[ft.Switch]()

        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Switch(
                        ref=self._toggle_ref,
                        value=enabled,
                        active_color=Colors.PRIMARY,
                        inactive_thumb_color=Colors.TEXT_DISABLED,
                        on_change=lambda e: on_toggle(block_id, e.control.value),
                        scale=0.75,
                    ),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text(
                                label,
                                size=Fonts.SIZE_SM,
                                color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                preview,
                                size=Fonts.SIZE_XS,
                                color=Colors.TEXT_DISABLED,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                font_family=Fonts.MONO,
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                        icon_size=16,
                        icon_color=Colors.ERROR,
                        tooltip="移除",
                        style=ft.ButtonStyle(
                            padding=ft.Padding(left=4, right=4, top=4, bottom=4),
                        ),
                        on_click=lambda e: on_remove(block_id),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.SM,
            ),
            padding=ft.Padding(
                left=Spacing.SM, right=Spacing.SM,
                top=Spacing.SM, bottom=Spacing.SM,
            ),
            border=ft.Border(bottom=ft.BorderSide(1, Colors.DIVIDER)),
        )


# ──────────────────────────────────────────────
# 模板条目
# ──────────────────────────────────────────────
class _TemplateItem(ft.Container):
    def __init__(
        self,
        template_id: str,
        name: str,
        description: str,
        on_apply: Callable[[str], None],
    ) -> None:
        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.DESCRIPTION_OUTLINED,
                        size=16,
                        color=Colors.PRIMARY,
                    ),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text(
                                name,
                                size=Fonts.SIZE_SM,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Text(
                                description,
                                size=Fonts.SIZE_XS,
                                color=Colors.TEXT_DISABLED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.ElevatedButton(
                        content=ft.Text(
                            "应用",
                            size=Fonts.SIZE_XS,
                            color=Colors.PRIMARY,
                            font_family=Fonts.MONO,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor="transparent",
                            overlay_color=Colors.PRIMARY_GLOW,
                            side=ft.BorderSide(1, Colors.PRIMARY),
                            s