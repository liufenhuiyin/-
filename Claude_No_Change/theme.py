# Layer: UI
# File: app/ui/theme.py
# Responsibility: 全局颜色、字体、间距、样式常量
# Input: 无
# Output: 供所有 UI 模块 import 的常量与 ColorScheme 工厂函数

import flet as ft

# ──────────────────────────────────────────────
# 色彩系统（工业精密风 · 深色）
# ──────────────────────────────────────────────
class Colors:
    # 背景层次
    BG_BASE       = "#0D0F14"   # 最底层背景
    BG_SURFACE    = "#13161D"   # 卡片 / 面板背景
    BG_ELEVATED   = "#1A1E28"   # 悬浮元素 / 输入框
    BG_OVERLAY    = "#1F2433"   # hover / 选中态

    # 主色 & 强调
    PRIMARY       = "#4A9EFF"   # 冷钢蓝 - 主交互色
    PRIMARY_DIM   = "#2E6FCC"   # 按压态
    PRIMARY_GLOW  = "#4A9EFF22" # 光晕背景（低透明度）
    ACCENT        = "#64FFDA"   # 薄荷绿 - 思考模式 / 特殊高亮

    # 文字层次
    TEXT_PRIMARY   = "#E8EAF0"  # 主要文字
    TEXT_SECONDARY = "#7A8099"  # 次要 / 占位符
    TEXT_DISABLED  = "#3D4255"  # 禁用态
    TEXT_CODE      = "#A8C4E8"  # 代码块 / 等宽内容

    # 角色标识
    ROLE_USER      = "#4A9EFF"  # 用户气泡标识
    ROLE_ASSISTANT = "#64FFDA"  # 助手气泡标识
    ROLE_THINKING  = "#9C7FE8"  # 思考块标识（紫）

    # 状态色
    SUCCESS        = "#4CAF82"
    WARNING        = "#E8A838"
    ERROR          = "#F06B6B"
    INFO           = "#4A9EFF"

    # 边框 & 分割线
    BORDER         = "#252A38"  # 普通边框
    BORDER_FOCUS   = "#4A9EFF"  # 聚焦态边框
    DIVIDER        = "#1E2230"  # 分割线


# ──────────────────────────────────────────────
# 字体系统
# ──────────────────────────────────────────────
class Fonts:
    BODY        = "Noto Sans SC"
    MONO        = "JetBrains Mono"
    # 字号
    SIZE_XS     = 11
    SIZE_SM     = 12
    SIZE_MD     = 14
    SIZE_LG     = 16
    SIZE_XL     = 18
    SIZE_XXL    = 22


# ──────────────────────────────────────────────
# 间距系统
# ──────────────────────────────────────────────
class Spacing:
    XS  = 4
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 24
    XXL = 32


# ──────────────────────────────────────────────
# 圆角系统
# ──────────────────────────────────────────────
class Radius:
    SM  = ft.BorderRadius(top_left=4,  top_right=4,  bottom_left=4,  bottom_right=4)
    MD  = ft.BorderRadius(top_left=8,  top_right=8,  bottom_left=8,  bottom_right=8)
    LG  = ft.BorderRadius(top_left=12, top_right=12, bottom_left=12, bottom_right=12)
    XL  = ft.BorderRadius(top_left=16, top_right=16, bottom_left=16, bottom_right=16)
    # 气泡专用（右下角方形）
    BUBBLE_USER = ft.BorderRadius(top_left=12, top_right=12, bottom_left=12, bottom_right=2)
    # 气泡专用（左下角方形）
    BUBBLE_ASST = ft.BorderRadius(top_left=12, top_right=12, bottom_left=2,  bottom_right=12)


# ──────────────────────────────────────────────
# Flet ColorScheme 工厂（Material 3 深色）
# ──────────────────────────────────────────────
def build_color_scheme() -> ft.ColorScheme:
    return ft.ColorScheme(
        brightness=ft.Brightness.DARK,
        primary=Colors.PRIMARY,
        on_primary=Colors.BG_BASE,
        secondary=Colors.ACCENT,
        on_secondary=Colors.BG_BASE,
        surface=Colors.BG_SURFACE,
        on_surface=Colors.TEXT_PRIMARY,
        background=Colors.BG_BASE,
        on_background=Colors.TEXT_PRIMARY,
        error=Colors.ERROR,
        on_error=Colors.BG_BASE,
        surface_variant=Colors.BG_ELEVATED,
        on_surface_variant=Colors.TEXT_SECONDARY,
        outline=Colors.BORDER,
        outline_variant=Colors.DIVIDER,
    )


def build_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme=build_color_scheme(),
        font_family=Fonts.BODY,
        use_material3=True,
    )


# ──────────────────────────────────────────────
# 常用边框预设
# ──────────────────────────────────────────────
class Borders:
    DEFAULT = ft.Border(
        top=ft.BorderSide(1, Colors.BORDER),
        bottom=ft.BorderSide(1, Colors.BORDER),
        left=ft.BorderSide(1, Colors.BORDER),
        right=ft.BorderSide(1, Colors.BORDER),
    )
    FOCUS = ft.Border(
        top=ft.BorderSide(1, Colors.BORDER_FOCUS),
        bottom=ft.BorderSide(1, Colors.BORDER_FOCUS),
        left=ft.BorderSide(1, Colors.BORDER_FOCUS),
        right=ft.BorderSide(1, Colors.BORDER_FOCUS),
    )
    BOTTOM_ONLY = ft.Border(
        bottom=ft.BorderSide(1, Colors.DIVIDER)
    )
    LEFT_ACCENT = ft.Border(
        left=ft.BorderSide(2, Colors.PRIMARY)
    )
    LEFT_THINKING = ft.Border(
        left=ft.BorderSide(2, Colors.ROLE_THINKING)
    )
