# ui/state/ui_state_store.py
"""
UIStateStore — Controller 与 UI 之间的唯一数据桥梁。

规则：
  - Controller 只调用 set_xxx() 方法写入状态
  - UI 只读取属性，订阅事件
  - 这个类不含任何业务逻辑
  - Controller 永远不持有任何 Flet 组件引用
"""
from __future__ import annotations

import threading
from typing import Callable, List, Dict, Optional
from control_state.models import MessageVM, StreamStatus


class UIStateStore:
    """
    可观察状态容器。
    Controller 写，UI 读+订阅。
    """

    def __init__(self):
        # ── 状态字段 ──────────────────────────────
        self.messages:      List[MessageVM] = []
        self.stream_status: StreamStatus    = StreamStatus.IDLE
        self.is_loading:    bool            = False
        self.error:         Optional[str]   = None
        self.current_model: str             = "Flash"
        self.thinking_on:   bool            = False

        # ── 订阅者注册表 ───────────────────────────
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    # ──────────────────────────────────────────────
    # 订阅 API（UI 调用）
    # ──────────────────────────────────────────────

    def subscribe(self, event: str, callback: Callable) -> None:
        with self._lock:
            self._listeners.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        with self._lock:
            if event in self._listeners:
                try:
                    self._listeners[event].remove(callback)
                except ValueError:
                    pass

    # ──────────────────────────────────────────────
    # 写入 API（Controller 调用）
    # ──────────────────────────────────────────────

    def set_loading(self, loading: bool) -> None:
        self.is_loading    = loading
        self.stream_status = StreamStatus.LOADING if loading else StreamStatus.IDLE
        self._notify("loading")

    def set_messages(self, messages: List[MessageVM]) -> None:
        self.messages = messages
        self._notify("messages")

    def append_message(self, message: MessageVM) -> None:
        self.messages = self.messages + [message]   # 新列表，触发 UI 重绘
        self._notify("messages")

    def set_error(self, message: Optional[str]) -> None:
        self.error         = message
        self.is_loading    = False
        self.stream_status = StreamStatus.ERROR if message else StreamStatus.IDLE
        self._notify("error")
        self._notify("loading")

    def set_model_config(self, model: str, thinking: bool) -> None:
        self.current_model = model
        self.thinking_on   = thinking
        self._notify("model_config")

    def clear_error(self) -> None:
        self.error = None
        self._notify("error")

    # ──────────────────────────────────────────────
    # 内部通知
    # ──────────────────────────────────────────────

    def _notify(self, event: str) -> None:
        with self._lock:
            callbacks = list(self._listeners.get(event, []))
        for cb in callbacks:
            try:
                cb()
            except Exception:
                pass   # UI 回调异常不应崩溃整个应用
