# ui/state/ui_state_store.py
"""
UIStateStore — 支持流式 token 更新。
"""
from __future__ import annotations

import threading
from typing import Callable, List, Dict, Optional
from control_state.models import MessageVM, StreamStatus


class UIStateStore:

    def __init__(self):
        self.messages:       List[MessageVM] = []
        self.stream_status:  StreamStatus    = StreamStatus.IDLE
        self.is_loading:     bool            = False
        self.error:          Optional[str]   = None
        self.current_model:  str             = "Flash"
        self.thinking_on:    bool            = False
        # 当前正在流式输出的消息 ID
        self._streaming_id:  Optional[str]   = None

        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    # ── 订阅 API ──────────────────────────────────

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

    # ── 写入 API（Controller 调用）────────────────

    def set_loading(self, loading: bool) -> None:
        self.is_loading   = loading
        self.stream_status = StreamStatus.LOADING if loading else StreamStatus.IDLE
        self._notify("loading")

    def set_messages(self, messages: List[MessageVM]) -> None:
        self.messages = messages
        self._notify("messages")

    def append_message(self, message: MessageVM) -> None:
        self.messages = self.messages + [message]
        # 记录流式消息的 ID
        if message.is_streaming:
            self._streaming_id = message.message_id
        self._notify("messages")

    def append_stream_token(self, token: str) -> None:
        """
        流式核心：找到正在流式的消息，追加 token，只通知 stream 事件。
        不重建整个列表，只更新目标消息的 content。
        """
        if not self._streaming_id:
            return
        for msg in self.messages:
            if msg.message_id == self._streaming_id:
                msg.content += token
                break
        self._notify("stream")

    def set_stream_complete(self, message_id: str, final_content: str) -> None:
        """流式结束，更新最终内容，关闭 loading"""
        for msg in self.messages:
            if msg.message_id == message_id:
                msg.content      = final_content
                msg.is_streaming = False
                break
        self._streaming_id = None
        self.is_loading    = False
        self.stream_status = StreamStatus.COMPLETE
        self._notify("stream")
        self._notify("loading")

    def remove_message(self, message_id: str) -> None:
        """移除指定消息（错误时移除空占位）"""
        self.messages = [m for m in self.messages if m.message_id != message_id]
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

    # ── 内部通知 ──────────────────────────────────

    def _notify(self, event: str) -> None:
        with self._lock:
            callbacks = list(self._listeners.get(event, []))
        for cb in callbacks:
            try:
                cb()
            except Exception:
                pass
