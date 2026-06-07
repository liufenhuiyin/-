# Layer: UI → widgets
# File: app/ui/widgets/kg_panel.py
# Responsibility: 知识图谱管理面板——查看实体、关系，支持删除操作。
# Input:  Controller 回调
# Output: ft.Control — 右侧面板
# 禁止: 业务逻辑、core/adapters/storage 导入

from __future__ import annotations
from typing import Callable
import flet as ft
from app.ui.theme import Colors, Fonts, Spacing, Borders


class KGPanel(ft.Container):
    """
    知识图谱管理面板。

    公开接口：
        show() / hide()
        load_data(entities, relations, stats)
    """

    def __init__(
        self,
        on_delete_entity: Callable[[str], None],
        on_delete_relation: Callable[[str], None],
        on_close: Callable[[], None],
    ) -> None:
        self._on_delete_entity   = on_delete_entity
        self._on_delete_relation = on_delete_relation

        self._entities_list_ref  = ft.Ref[ft.ListView]()
        self._relations_list_ref = ft.Ref[ft.ListView]()
        self._stats_ref          = ft.Ref[ft.Text]()

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ACCOUNT_TREE_OUTLINED, size=18, color=Colors.ACCENT),
                    ft.Text(
                        "知识图谱",
                        size=Fonts.SIZE_LG,
                        color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600,
                        font_family=Fonts.MONO,
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        ref=self._stats_ref,
                        value="",
                        size=Fonts.SIZE_XS,
                        color=Colors.TEXT_SECONDARY,
                        font_family=Fonts.MONO,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=18,
                        icon_color=Colors.TEXT_SECONDARY,
                        on_click=lambda e: on_close(),
                        style=ft.ButtonStyle(
                            padding=ft.Padding(left=6, right=6, top=6, bottom=6),
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.SM,
            ),
            padding=ft.Padding(
                left=Spacing.LG, right=Spacing.MD,
                top=Spacing.MD, bottom=Spacing.MD,
            ),
            border=Borders.BOTTOM_ONLY,
        )

        entities_view = ft.ListView(
            ref=self._entities_list_ref,
            expand=True,
            spacing=0,
        )

        relations_view = ft.ListView(
            ref=self._relations_list_ref,
            expand=True,
            spacing=0,
        )

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=150,
            tabs=[
                ft.Tab(
                    text="实体",
                    content=ft.Container(content=entities_view, expand=True),
                ),
                ft.Tab(
                    text="关系",
                    content=ft.Container(content=relations_view, expand=True),
                ),
            ],
            expand=True,
            label_color=Colors.PRIMARY,
            unselected_label_color=Colors.TEXT_SECONDARY,
            indicator_color=Colors.PRIMARY,
        )

        super().__init__(
            content=ft.Column(
                controls=[header, tabs],
                spacing=0,
                expand=True,
            ),
            width=380,
            bgcolor=Colors.BG_SURFACE,
            border=ft.Border(
                left=ft.BorderSide(1, Colors.BORDER),
                top=ft.BorderSide(0, "transparent"),
                right=ft.BorderSide(0, "transparent"),
                bottom=ft.BorderSide(0, "transparent"),
            ),
            visible=False,
        )

    # ── 公开接口 ──────────────────────────────

    def show(self) -> None:
        self.visible = True
        self.update()

    def hide(self) -> None:
        self.visible = False
        self.update()

    def load_data(
        self,
        entities: list[dict],
        relations: list[dict],
        stats: dict,
    ) -> None:
        if self._stats_ref.current:
            ec = stats.get("entity_count", 0)
            rc = stats.get("relation_count", 0)
            self._stats_ref.current.value = f"{ec} 实体 · {rc} 关系"
            self._stats_ref.current.update()

        if self._entities_list_ref.current:
            self._entities_list_ref.current.controls.clear()
            if not entities:
                self._entities_list_ref.current.controls.append(
                    self._empty_hint("暂无实体\n点击 AI 回复下方的书签按钮开始提取")
                )
            else:
                for e in entities:
                    self._entities_list_ref.current.controls.append(
                        self._entity_item(e)
                    )
            self._entities_list_ref.current.update()

        if self._relations_list_ref.current:
            self._relations_list_ref.current.controls.clear()
            if not relations:
                self._relations_list_ref.current.controls.append(
                    self._empty_hint("暂无关系")
                )
            else:
                for r in relations:
                    self._relations_list_ref.current.controls.append(
                        self._relation_item(r)
                    )
            self._relations_list_ref.current.update()

    # ── 私有控件构造 ──────────────────────────

    def _entity_item(self, e: dict) -> ft.Container:
        name  = e.get("name", "")
        etype = e.get("entity_type", "")
        desc  = e.get("description", "")

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            etype,
                            size=Fonts.SIZE_XS,
                            color=Colors.ACCENT,
                            font_family=Fonts.MONO,
                        ),
                        padding=ft.Padding(left=4, right=4, top=2, bottom=2),
                        border=ft.Border(
                            top=ft.BorderSide(1, Colors.ACCENT),
                            bottom=ft.BorderSide(1, Colors.ACCENT),
                            left=ft.BorderSide(1, Colors.ACCENT),
                            right=ft.BorderSide(1, Colors.ACCENT),
                        ),
                        border_radius=ft.BorderRadius(2, 2, 2, 2),
                    ),
                    ft.Column(
                        expand=True,
                        spacing=1,
                        controls=[
                            ft.Text(
                                name,
                                size=Fonts.SIZE_SM,
                                color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                desc or "—",
                                size=Fonts.SIZE_XS,
                                color=Colors.TEXT_DISABLED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=14,
                        icon_color=Colors.ERROR,
                        tooltip="删除实体（同时删除相关关系）",
                        style=ft.ButtonStyle(
                            padding=ft.Padding(left=4, right=4, top=4, bottom=4),
                        ),
                        on_click=lambda ev, n=name: self._on_delete_entity(n),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.SM,
            ),
            padding=ft.Padding(
                left=Spacing.MD, right=Spacing.SM,
                top=Spacing.SM, bottom=Spacing.SM,
            ),
            border=ft.Border(bottom=ft.BorderSide(1, Colors.DIVIDER)),
        )

    def _relation_item(self, r: dict) -> ft.Container:
        src  = r.get("source_entity_name", "")
        rel  = r.get("relation_type", "")
        tgt  = r.get("target_entity_name", "")
        rid  = r.get("id", "")
        desc = r.get("description", "")

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(src, size=Fonts.SIZE_SM,
                                            color=Colors.PRIMARY,
                                            weight=ft.FontWeight.W_500),
                                    ft.Text(f"[{rel}]", size=Fonts.SIZE_XS,
                                            color=Colors.TEXT_SECONDARY,
                                            font_family=Fonts.MONO),
                                    ft.Text(tgt, size=Fonts.SIZE_SM,
                                            color=Colors.ACCENT,
                                            weight=ft.FontWeight.W_500),
                                ],
                                spacing=4,
                                wrap=True,
                            ),
                            ft.Text(
                                desc,
                                size=Fonts.SIZE_XS,
                                color=Colors.TEXT_DISABLED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ) if desc else ft.Container(height=0),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=14,
                        icon_color=Colors.ERROR,
                        tooltip="删除此关系",
                        style=ft.ButtonStyle(
                            padding=ft.Padding(left=4, right=4, top=4, bottom=4),
                        ),
                        on_click=lambda ev, i=rid: self._on_delete_relation(i),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.SM,
            ),
            padding=ft.Padding(
                left=Spacing.MD, right=Spacing.SM,
                top=Spacing.SM, bottom=Spacing.SM,
            ),
            border=ft.Border(bottom=ft.BorderSide(1, Colors.DIVIDER)),
        )

    @staticmethod
    def _empty_hint(text: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(
                text,
                size=Fonts.SIZE_SM,
                color=Colors.TEXT_DISABLED,
                text_align=ft.TextAlign.CENTER,
            ),
            padding=ft.Padding(left=Spacing.LG, right=Spacing.LG,
                               top=Spacing.XL, bottom=Spacing.XL),
            alignment=ft.Alignment(0, 0),
        )
