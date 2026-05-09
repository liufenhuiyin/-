# controllers/app_controller.py
"""
AppController — MVP 最简版本。

职责：
  - 对 UI 暴露所有可调用的公开方法
  - 编排子 Controller + Service 的调用顺序
  - 持有并更新 UIStateStore
  - 管理 ControlState（运行时配置唯一来源）

禁止：
  - 包含任何业务计算逻辑
  - 持有任何 Flet 组件引用
  - 直接调用 Core Service（MVP 阶段因为没有子 Controller，暂时直接调用 service）
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
    """
    MVP 版 AppController。

    MVP 简化说明：
      - 没有 ConversationController / SettingsController 子 Controller
      - 直接持有 ConversationService（完整版本会通过子 Controller 调用）
      - api_key 从构造函数传入（完整版本会在 SettingsController 管理）
      - messages 存在 ControlState 中（完整版本会有 Repository 持久化）
    """

    def __init__(
        self,
        store:       UIStateStore,
        conv_service: ConversationService,
        api_key:     str,
    ):
        self._store       = store
        self._conv        = conv_service
        self._api_key     = api_key
        self._state       = ControlState()
        self._lock        = threading.Lock()

        # 初始化默认会话
        self._init_default_session()

    # ──────────────────────────────────────────────
    # 初始化
    # ──────────────────────────────────────────────

    def _init_default_session(self) -> None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session    = SessionState(session_id=session_id)

        self._state.sessions[session_id]  = session
        self._state.messages[session_id]  = []
        self._state.active_session_id     = session_id

        # 同步初始 UI 状态
        self._store.set_model_config(
            model    = "Flash",
            thinking = False,
        )

    # ──────────────────────────────────────────────
    # 公开动作接口（UI 调用的全部入口）
    # ──────────────────────────────────────────────

    def send_message(self, text: str) -> None:
        """
        发送用户消息。在后台线程执行，不阻塞 UI。

        调用链：
          UI → AppController.send_message()
            → ControlState 读取 model_config
            → ConversationService.send_message()
              → DeepSeekClient.chat_completion()
            → ControlState 更新 messages
            → UIStateStore 通知 UI
        """
        text = text.strip()
        if not text:
            return

        # 在后台线程执行，避免阻塞 Flet UI 线程
        thread = threading.Thread(
            target=self._send_message_worker,
            args=(text,),
            daemon=True,
        )
        thread.start()

    def switch_model(self, model_name: str) -> None:
        """
        切换模型（Flash / Pro）。
        纯状态变更，不触发 API 调用。
        """
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
        """新建会话，清空消息列表"""
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session    = SessionState(session_id=session_id)

        with self._lock:
            self._state.sessions[session_id] = session
            self._state.messages[session_id] = []
            self._state.active_session_id    = session_id

        self._store.set_messages([])
        self._store.set_model_config(
            model    = "Flash",
            thinking = False,
        )
        self._store.clear_error()

    def get_current_model(self) -> str:
        session = self._state.active_session
        if not session:
            return "Flash"
        return "Pro" if session.model_config.model == ModelType.PRO else "Flash"

    # ──────────────────────────────────────────────
    # 内部工作方法（不暴露给 UI）
    # ──────────────────────────────────────────────

    def _send_message_worker(self, text: str) -> None:
        """
        后台线程执行的发送逻辑。
        所有状态读写通过 ControlState，所有 UI 更新通过 UIStateStore。
        """
        session_id = self._state.active_session_id
        session    = self._state.active_session

        if not session or not session_id:
            return

        # ── Step 1：立刻把用户消息写入状态并推送 UI ──
        user_msg = MessageVM(
            message_id  = f"user_{uuid.uuid4().hex[:8]}",
            role        = "user",
            content     = text,
            model_label = self._store.current_model,
        )
        with self._lock:
            self._state.messages[session_id].append(user_msg)

        self._store.append_message(user_msg)
        self._store.set_loading(True)
        self._store.clear_error()

        try:
            # ── Step 2：从 ControlState 读取配置（唯一来源）──
            model_config = session.model_config.to_api_payload()

            # ── Step 3：构建 messages（MVP：全量历史，不裁剪）──
            with self._lock:
                history = list(self._state.messages[session_id])

            api_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in history
            ]

            # ── Step 4：调用 Service（不含任何业务判断）──
            response_text = self._conv.send_message(
                api_key      = self._api_key,
                messages     = api_messages,
                model_config = model_config,
            )

            # ── Step 5：把 assistant 回复写入状态并推送 UI ──
            assistant_msg = MessageVM(
                message_id  = f"asst_{uuid.uuid4().hex[:8]}",
                role        = "assistant",
                content     = response_text,
                model_label = self._store.current_model,
            )
            with self._lock:
                self._state.messages[session_id].append(assistant_msg)

            self._store.append_message(assistant_msg)
            self._store.set_loading(False)

        except DeepSeekAPIError as e:
            self._store.set_error(f"API 错误 {e.status_code}：{e.message}")

        except Exception as e:
            self._store.set_error(f"未知错误：{str(e)}")
