# app/container.py
"""
依赖注入容器 — 唯一的组装入口。

组装顺序（严格从底层到上层）：
  1. DeepSeekClient（无依赖）
  2. ConversationService（依赖 Client）
  3. UIStateStore（无依赖）
  4. AppController（依赖 Service + Store + api_key）

所有依赖关系在这里声明，各层不自行 import 其他层的具体实现类。
"""
from __future__ import annotations

from core.services.deepseek_client import DeepSeekClient
from core.services.conversation_service import ConversationService
from ui.state.ui_state_store import UIStateStore
from controllers.app_controller import AppController


def build_container(api_key: str) -> tuple[AppController, UIStateStore]:
    """
    构建并返回 (AppController, UIStateStore)。

    main.py 拿到这两个对象后：
      - AppController 传给 ChatView（用于动作委托）
      - UIStateStore  传给 ChatView（用于状态订阅）
    """

    # ── 第一层：无状态客户端 ──────────────────────
    client = DeepSeekClient(timeout=60.0)

    # ── 第二层：无状态 Service ────────────────────
    conv_service = ConversationService(client=client)

    # ── 第三层：UI 状态容器 ───────────────────────
    store = UIStateStore()

    # ── 第四层：AppController ─────────────────────
    controller = AppController(
        store        = store,
        conv_service = conv_service,
        api_key      = api_key,
    )

    return controller, store
