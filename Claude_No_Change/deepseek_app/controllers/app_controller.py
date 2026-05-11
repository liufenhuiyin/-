# controllers/app_controller.py
"""
AppController — 支持流式输出版本。
"""
from __future__ import annotations

import uuid
import threading
from datetime import datetime
from typing import Optional

from control_state.models import (
    ControlState, SessionState, ModelConfig,
    ModelType, ThinkingType, MessageVM, StreamStatus,
)
from core.services.conversation_service import ConversationService
from core.services.deepseek_client import DeepSeekAPIError
from ui.state.ui_state_store import UIStateStore


class AppController:

    def __init__(
        self,
        store:        UIStateStore,
        conv_service: ConversationService,
        api_key:      str,
    ):
        self._store  = store
        self._conv   = conv_service
        self._api_key = api_key
        self._state  = ControlState()
        self._lock   = threading.Lock()
        self._init_default_session()

    def _init_default_session(self) -> None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session    = SessionState(session_id=session_id)
        self._state.sessions[session_id] = session
        self._state.messages[session_id] = []
        self._state.active_session_id    = session_id
        self._store.set_model_config(model="Flash", thinking=False)

    # ── 公开动作接口 ──────────────────────────────

    def send_message(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        thread = threading.Thread(
            target=self._send_worker,
            args=(text,),
            daemon=True,
        )
        thread.start()

    def switch_model(self, model_name: str) -> None:
        session = self._state.active_session
        if not session:
            return
        with self._lock:
            if model_name == "Pro":
                session.model_config = ModelConfig(
                    model    = ModelType.PRO,
                    thinking = ThinkingType.ENABLED,
                )
            else:
                session.model_config = ModelConfig(
                    model    = ModelType.FLASH,
                    thinking = ThinkingType.DISABLED,
                )
        self._store.set_model_config(
            model    = model_name,
            thinking = session.model_config.thinking == ThinkingType.ENABLED,
        )

    def new_conversation(self) -> None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session    = SessionState(session_id=session_id)
        with self._lock:
            self._state.sessions[session_id] = session
            self._state.messages[session_id] = []
            self._state.active_session_id    = session_id
        self._store.set_messages([])
        self._store.set_model_config(model="Flash", thinking=False)
        self._store.clear_error()

    def get_current_model(self) -> str:
        session = self._state.active_session
        if not session:
            return "Flash"
        return "Pro" if session.model_config.model == ModelType.PRO else "Flash"

    # ── 内部流式发送 ──────────────────────────────

    def _send_worker(self, text: str) -> None:
        session_id = self._state.active_session_id
        session    = self._state.active_session
        if not session or not session_id:
            return

        # 1. 用户消息立刻显示
        user_msg = MessageVM(
            message_id  = f"user_{uuid.uuid4().hex[:8]}",
            role        = "user",
            content     = text,
            model_label = self._store.current_model,
        )
        with self._lock:
            self._state.messages[session_id].append(user_msg)
        self._store.append_message(user_msg)

        # 2. 占位 assistant 消息（内容为空，流式填入）
        asst_id  = f"asst_{uuid.uuid4().hex[:8]}"
        asst_msg = MessageVM(
            message_id  = asst_id,
            role        = "assistant",
            content     = "",
            model_label = self._store.current_model,
            is_streaming = True,
        )
        with self._lock:
            self._state.messages[session_id].append(asst_msg)
        self._store.append_message(asst_msg)
        self._store.set_loading(True)
        self._store.clear_error()

        try:
            # 3. 从 ControlState 读取配置（唯一来源）
            model_config = session.model_config.to_api_payload()

            # 4. 构建消息历史（去掉最后那条空的占位 assistant 消息）
            with self._lock:
                history = list(self._state.messages[session_id])
            api_messages = [
                {"role": m.role, "content": m.content}
                for m in history
                if not (m.message_id == asst_id and m.content == "")
            ]

            # 5. 流式调用，每个 token 通过回调推送
            final_content = self._conv.send_message_stream(
                api_key      = self._api_key,
                messages     = api_messages,
                model_config = model_config,
                on_token     = self._on_token,
            )

            # 6. 更新 ControlState 中的完整内容
            with self._lock:
                for m in self._state.messages[session_id]:
                    if m.message_id == asst_id:
                        m.content     = final_content
                        m.is_streaming = False
                        break

            self._store.set_stream_complete(asst_id, final_content)

        except DeepSeekAPIError as e:
            # 移除空占位消息
            with self._lock:
                self._state.messages[session_id] = [
                    m for m in self._state.messages[session_id]
                    if m.message_id != asst_id
                ]
            self._store.remove_message(asst_id)
            self._store.set_error(f"API 错误 {e.status_code}：{e.message}")

        except Exception as e:
            with self._lock:
                self._state.messages[session_id] = [
                    m for m in self._state.messages[session_id]
                    if m.message_id != asst_id
                ]
            self._store.remove_message(asst_id)
            self._store.set_error(f"未知错误：{str(e)}")

    def _on_token(self, token: str) -> None:
        """每收到一个 token，写入 store，store 通知 UI 渲染"""
        self._store.append_stream_token(token)
