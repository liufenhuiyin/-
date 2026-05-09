# control_state/models.py
"""
Control State — MVP 最小版本（使用标准库，无第三方依赖）
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json


class ModelType(str, Enum):
    FLASH = "deepseek-chat"
    PRO   = "deepseek-reasoner"


class ThinkingType(str, Enum):
    ENABLED  = "enabled"
    DISABLED = "disabled"


class ReasoningEffort(str, Enum):
    HIGH = "high"
    MAX  = "max"


class StreamStatus(str, Enum):
    IDLE    = "idle"
    LOADING = "loading"
    COMPLETE = "complete"
    ERROR   = "error"


@dataclass
class ModelConfig:
    """API payload 的唯一来源。Service 不得修改任何字段。"""
    model:            ModelType       = ModelType.FLASH
    thinking:         ThinkingType    = ThinkingType.DISABLED
    reasoning_effort: ReasoningEffort = ReasoningEffort.HIGH

    def to_api_payload(self) -> Dict[str, Any]:
        return {
            "model":            self.model.value,
            "thinking":         {"type": self.thinking.value},
            "reasoning_effort": self.reasoning_effort.value,
        }


@dataclass
class MessageVM:
    """UI 层使用的消息视图对象"""
    message_id:  str
    role:        str
    content:     str
    model_label: str
    created_at:  datetime = field(default_factory=datetime.now)
    is_error:    bool = False


@dataclass
class SessionState:
    """单个会话的完整运行时状态"""
    session_id:    str
    created_at:    datetime      = field(default_factory=datetime.now)
    model_config:  ModelConfig   = field(default_factory=ModelConfig)
    stream_status: StreamStatus  = StreamStatus.IDLE
    error_message: Optional[str] = None


@dataclass
class ControlState:
    """AppController 持有的完整状态聚合。唯一合法配置来源。"""
    active_session_id: Optional[str]               = None
    sessions:          Dict[str, SessionState]      = field(default_factory=dict)
    messages:          Dict[str, List[MessageVM]]   = field(default_factory=dict)

    @property
    def active_session(self) -> Optional[SessionState]:
        if not self.active_session_id:
            return None
        return self.sessions.get(self.active_session_id)

    @property
    def active_messages(self) -> List[MessageVM]:
        if not self.active_session_id:
            return []
        return self.messages.get(self.active_session_id, [])

    def get_model_label(self, session_id: str) -> str:
        s = self.sessions.get(session_id)
        if not s:
            return "Flash"
        return "Pro" if s.model_config.model == ModelType.PRO else "Flash"
