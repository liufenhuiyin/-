# main.py
from __future__ import annotations
import os
import sys

def load_env(path=".env"):
    """简单的 .env 加载器（不依赖 python-dotenv）"""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

load_env()

import flet as ft
from app.container import build_container
from ui.views.chat_view import ChatView


def main(page: ft.Page) -> None:
    page.title        = "DeepSeek Chat"
    page.theme_mode   = ft.ThemeMode.DARK
    page.window.width  = 900
    page.window.height = 700
    page.window.min_width  = 600
    page.window.min_height = 500
    page.padding      = 0
    page.bgcolor      = ft.Colors.SURFACE
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE, use_material3=True)

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        page.add(_no_key_view())
        return

    controller, store = build_container(api_key=api_key)
    page.add(ChatView(page=page, store=store, controller=controller))


def _no_key_view() -> ft.Control:
    return ft.Column(
        controls=[
            ft.Container(expand=True),
            ft.Column(
                controls=[
                    ft.Icon(ft.Icons.KEY_OFF_ROUNDED, size=48, color=ft.Colors.OUTLINE),
                    ft.Text("未找到 DeepSeek API Key", size=18, weight=ft.FontWeight.W_600,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("请在项目根目录创建 .env 文件：",
                            size=13, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        content=ft.Text("DEEPSEEK_API_KEY=sk-xxxxxxxx",
                                        font_family="monospace", size=12, color=ft.Colors.PRIMARY),
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                        border_radius=8,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            ft.Container(expand=True),
        ],
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


if __name__ == "__main__":
    ft.app(target=main)
