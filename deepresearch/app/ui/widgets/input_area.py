# Layer: UI → widgets
# File: app/ui/widgets/input_area.py
# Responsibility: 底部输入区复合体——输入框、模型切换、思考/搜索开关、文件上传、发送/停止按钮
# Input:  Controller 回调、config 读写
# Output: ft.Control — 底部固定栏
# 禁止: 任何业务逻辑、core/adapters/storage 导入

from __future__ import annotations
from typing import Callable
import flet as ft
import config as app_config  # 全局集中配置，直接读写
from app.ui.theme import Colors, Fonts, Spacing, Radius


# ──────────────────────────────────────────────
# 开关芯片
# ──────────────────────────────────────────────
class _ToggleChip(ft.Container):
    def __init__(
        self,
        label: str,
        icon: str,
        active_color: str,
        initial: bool = False,
        on_change: Callable[[bool], None] | None = None,
    ) -> None:
        self._active = initial
        self._active_color = active_color
        self._on_change = on_change
        self._label_ref = ft.Ref[ft.Text]()
        self._icon_ref = ft.Ref[ft.Icon]()

        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ref=self._icon_ref,
                        name=icon,
                        size=14,
                        color=active_color if initial else Colors.TEXT_DISABLED,
                    ),
                    ft.Text(
                        ref=self._label_ref,
                        value=label,
                        size=Fonts.SIZE_XS,
                        font_family=Fonts.MONO,
                        color=active_color if initial else Colors.TEXT_DISABLED,
                        letter_spacing=0.8,
                    ),
                ],
                tight=True,
                spacing=4,
            ),
            padding=ft.Padding(left=8, right=8, top=4, bottom=4),
            border=ft.Border(
                top=ft.BorderSide(1, active_color if initial else Colors.BORDER),
                bottom=ft.BorderSide(1, active_color if initial else Colors.BORDER),
                left=ft.BorderSide(1, active_color if initial else Colors.BORDER),
                right=ft.BorderSide(1, active_color if initial else Colors.BORDER),
            ),
            border_radius=Radius.SM,
            bgcolor=f"{active_color}22" if initial else "transparent",
            on_click=self._toggle,
            ink=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _toggle(self, e: ft.ControlEvent) -> None:
        self._active = not self._active
        color = self._active_color if self._active else Colors.TEXT_DISABLED
        border_color = self._active_color if self._active else Colors.BORDER
        self.bgcolor = f"{self._active_color}22" if self._active else "transparent"
        self.border = ft.Border(
            top=ft.BorderSide(1, border_color),
            bottom=ft.BorderSide(1, border_color),
            left=ft.BorderSide(1, border_color),
            right=ft.BorderSide(1, border_color),
        )
        if self._icon_ref.current:
            self._icon_ref.current.color = color
        if self._label_ref.current:
            self._label_ref.current.color = color
        e.control.update()
        if self._on_change:
            self._on_change(self._active)

    @property
    def value(self) -> bool:
        return self._active

    def set_value(self, val: bool) -> None:
        if self._active != val:
            self._active = val
            color = self._active_color if val else Colors.TEXT_DISABLED
            border_color = self._active_color if val else Colors.BORDER
            self.bgcolor = f"{self._active_color}22" if val else "transparent"
            self.border = ft.Border(
                top=ft.BorderSide(1, border_color),
                bottom=ft.BorderSide(1, border_color),
                left=ft.BorderSide(1, border_color),
                right=ft.BorderSide(1, border_color),
            )
            if self._icon_ref.current:
                self._icon_ref.current.color = color
            if self._label_ref.current:
                self._label_ref.current.color = color


# ──────────────────────────────────────────────
# 模型选择器
# ──────────────────────────────────────────────
class _ModelSelector(ft.Container):
    """下拉模型选择，写入 app_config.model_type"""

    _MODEL_OPTIONS = [
        ("deepseek-chat",     "Chat"),
        ("deepseek-reasoner", "Reasoner"),
    ]

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self._on_change = on_change
        current = getattr(app_config, "model_type", "deepseek-chat")

        options = [
            ft.dropdown.Option(key=k, text=v)
            for k, v in self._MODEL_OPTIONS
        ]

        self._dd = ft.Dropdown(
            value=current,
            options=options,
            width=150,
            text_size=Fonts.SIZE_SM,
            text_style=ft.TextStyle(
                font_family=Fonts.MONO,
                color=Colors.TEXT_PRIMARY,
            ),
            bgcolor=Colors.BG