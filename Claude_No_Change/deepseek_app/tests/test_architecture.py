# tests/test_architecture.py
"""
架构验证测试（不需要真实 API Key）
适配流式版本的 ConversationService。
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch
from control_state.models import (
    ControlState, SessionState, ModelConfig,
    ModelType, ThinkingType, ReasoningEffort, MessageVM,
)
from core.services.conversation_service import ConversationService
from ui.state.ui_state_store import UIStateStore
from controllers.app_controller import AppController


# ─────────────────────────────────────────
# Test 1: ControlState 结构验证
# ─────────────────────────────────────────

class TestControlState(unittest.TestCase):

    def test_default_model_is_flash(self):
        config = ModelConfig()
        self.assertEqual(config.model, ModelType.FLASH)
        self.assertEqual(config.thinking, ThinkingType.DISABLED)

    def test_api_payload_structure(self):
        config  = ModelConfig(model=ModelType.PRO, thinking=ThinkingType.ENABLED)
        payload = config.to_api_payload()
        self.assertIn("model",            payload)
        self.assertIn("thinking",         payload)
        self.assertIn("reasoning_effort", payload)
        self.assertIsInstance(payload["thinking"], dict)
        self.assertEqual(payload["thinking"]["type"], "enabled")

    def test_pro_model_value(self):
        payload = ModelConfig(model=ModelType.PRO).to_api_payload()
        self.assertEqual(payload["model"], "deepseek-reasoner")

    def test_flash_model_value(self):
        payload = ModelConfig(model=ModelType.FLASH).to_api_payload()
        self.assertEqual(payload["model"], "deepseek-chat")

    def test_flash_has_no_thinking_field(self):
        """Flash 模式不能携带 thinking / reasoning_effort，否则 API 报 400"""
        payload = ModelConfig(model=ModelType.FLASH).to_api_payload()
        self.assertNotIn("thinking",         payload)
        self.assertNotIn("reasoning_effort", payload)

    def test_active_session_property(self):
        state   = ControlState()
        session = SessionState(session_id="s1")
        state.sessions["s1"]    = session
        state.active_session_id = "s1"
        self.assertEqual(state.active_session.session_id, "s1")

    def test_no_active_session_returns_none(self):
        self.assertIsNone(ControlState().active_session)


# ─────────────────────────────────────────
# Test 2: ConversationService 无状态验证
# 新版 ConversationService 不接受 client 参数，
# 直接 mock send_message_stream 方法测试。
# ─────────────────────────────────────────

class TestConversationServiceStateless(unittest.TestCase):

    def setUp(self):
        self.service = ConversationService(timeout=10.0)

    def test_service_only_has_timeout_attribute(self):
        """Service 不应持有任何状态字段，只有 _timeout"""
        attrs = [k for k in vars(self.service) if not k.startswith('__')]
        self.assertEqual(attrs, ['_timeout'],
                         f"Service 持有了不应存在的状态: {attrs}")

    def test_service_has_send_message_stream_method(self):
        """Service 必须有流式发送方法"""
        self.assertTrue(hasattr(self.service, 'send_message_stream'))
        self.assertTrue(callable(self.service.send_message_stream))

    def test_stream_is_true_in_payload(self):
        """流式版本的 stream 字段必须为 True"""
        captured = {}

        def fake_urlopen(req, timeout=None):
            import json
            captured['payload'] = json.loads(req.data.decode())
            # 返回一个能迭代的假响应
            lines = [b'data: {"choices":[{"delta":{"content":"hi"}}]}\n',
                     b'data: [DONE]\n']
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: iter(lines)
            mock_resp.__exit__  = MagicMock(return_value=False)
            return mock_resp

        with patch('urllib.request.urlopen', fake_urlopen):
            self.service.send_message_stream(
                api_key      = "fake",
                messages     = [{"role": "user", "content": "hi"}],
                model_config = ModelConfig().to_api_payload(),
                on_token     = lambda t: None,
            )

        self.assertTrue(captured.get('payload', {}).get('stream', False))

    def test_on_token_called_for_each_token(self):
        """每个 token 都应触发 on_token 回调"""
        tokens = []

        lines = [
            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n',
            b'data: [DONE]\n',
        ]

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: iter(lines)
        mock_resp.__exit__  = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_resp):
            result = self.service.send_message_stream(
                api_key      = "fake",
                messages     = [],
                model_config = ModelConfig().to_api_payload(),
                on_token     = lambda t: tokens.append(t),
            )

        self.assertEqual(tokens, ["hello", " world"])
        self.assertEqual(result, "hello world")


# ─────────────────────────────────────────
# Test 3: UIStateStore 验证
# ─────────────────────────────────────────

class TestUIStateStore(unittest.TestCase):

    def setUp(self):
        self.store = UIStateStore()

    def test_subscribe_callback_fires(self):
        fired = []
        self.store.subscribe("messages", lambda: fired.append(1))
        msg = MessageVM(message_id="1", role="user", content="hi", model_label="Flash")
        self.store.append_message(msg)
        self.assertEqual(len(fired), 1)

    def test_unsubscribe_stops_callback(self):
        fired = []
        cb = lambda: fired.append(1)
        self.store.subscribe("messages", cb)
        self.store.unsubscribe("messages", cb)
        msg = MessageVM(message_id="1", role="user", content="hi", model_label="Flash")
        self.store.append_message(msg)
        self.assertEqual(len(fired), 0)

    def test_set_error_disables_loading(self):
        self.store.set_loading(True)
        self.store.set_error("oops")
        self.assertFalse(self.store.is_loading)
        self.assertEqual(self.store.error, "oops")

    def test_clear_error(self):
        self.store.set_error("err")
        self.store.clear_error()
        self.assertIsNone(self.store.error)

    def test_messages_append(self):
        m1 = MessageVM(message_id="1", role="user",      content="a", model_label="Flash")
        m2 = MessageVM(message_id="2", role="assistant", content="b", model_label="Flash")
        self.store.append_message(m1)
        self.store.append_message(m2)
        self.assertEqual(len(self.store.messages), 2)

    def test_append_stream_token(self):
        """流式 token 应该追加到正在流式的消息"""
        msg = MessageVM(
            message_id="s1", role="assistant",
            content="", model_label="Flash", is_streaming=True,
        )
        self.store.append_message(msg)
        self.store.append_stream_token("hello")
        self.store.append_stream_token(" world")
        streaming_msg = next(m for m in self.store.messages if m.message_id == "s1")
        self.assertEqual(streaming_msg.content, "hello world")

    def test_remove_message(self):
        m = MessageVM(message_id="del1", role="user", content="x", model_label="Flash")
        self.store.append_message(m)
        self.store.remove_message("del1")
        self.assertEqual(len(self.store.messages), 0)


# ─────────────────────────────────────────
# Test 4: AppController 调用链验证
# mock send_message_stream，不发真实请求
# ─────────────────────────────────────────

class TestAppControllerFlow(unittest.TestCase):

    def _make(self, response="mock answer"):
        """构建带 mock service 的 Controller"""
        svc   = ConversationService(timeout=10.0)
        store = UIStateStore()
        ctrl  = AppController(store=store, conv_service=svc, api_key="fake")

        # mock 掉实际的 HTTP 调用
        def fake_stream(api_key, messages, model_config, on_token):
            on_token(response)   # 模拟一个 token
            return response

        svc.send_message_stream = fake_stream
        return ctrl, store, svc

    def test_send_message_produces_two_messages(self):
        import time
        ctrl, store, _ = self._make("hello!")
        ctrl.send_message("hi")
        time.sleep(0.5)
        self.assertEqual(len(store.messages), 2)
        self.assertEqual(store.messages[0].role, "user")
        self.assertEqual(store.messages[1].role, "assistant")
        self.assertEqual(store.messages[1].content, "hello!")

    def test_switch_to_pro_updates_store_and_state(self):
        ctrl, store, _ = self._make()
        ctrl.switch_model("Pro")
        self.assertEqual(store.current_model, "Pro")
        self.assertTrue(store.thinking_on)
        self.assertEqual(ctrl._state.active_session.model_config.model, ModelType.PRO)

    def test_pro_model_reaches_api(self):
        import time
        captured = {}
        ctrl, store, svc = self._make()

        def fake_stream(api_key, messages, model_config, on_token):
            captured['model_config'] = model_config
            on_token("ok")
            return "ok"

        svc.send_message_stream = fake_stream
        ctrl.switch_model("Pro")
        ctrl.send_message("test")
        time.sleep(0.5)
        self.assertEqual(captured.get('model_config', {}).get('model'), "deepseek-reasoner")

    def test_flash_model_config_has_no_thinking(self):
        """Flash 模式的 API payload 不含 thinking 字段"""
        import time
        captured = {}
        ctrl, store, svc = self._make()

        def fake_stream(api_key, messages, model_config, on_token):
            captured['model_config'] = model_config
            on_token("ok")
            return "ok"

        svc.send_message_stream = fake_stream
        ctrl.switch_model("Flash")
        ctrl.send_message("test")
        time.sleep(0.5)
        self.assertNotIn("thinking",         captured.get('model_config', {}))
        self.assertNotIn("reasoning_effort", captured.get('model_config', {}))

    def test_api_error_sets_store_error(self):
        import time
        from core.services.deepseek_client import DeepSeekAPIError
        ctrl, store, svc = self._make()

        def fake_stream(api_key, messages, model_config, on_token):
            raise DeepSeekAPIError(401, "Unauthorized")

        svc.send_message_stream = fake_stream
        ctrl.send_message("hi")
        time.sleep(0.5)
        self.assertIsNotNone(store.error)
        self.assertIn("401", store.error)

    def test_empty_message_not_sent(self):
        import time
        called = []
        ctrl, store, svc = self._make()

        def fake_stream(api_key, messages, model_config, on_token):
            called.append(1)
            return ""

        svc.send_message_stream = fake_stream
        ctrl.send_message("   ")
        time.sleep(0.2)
        self.assertEqual(len(called), 0)

    def test_new_conversation_clears_messages(self):
        import time
        ctrl, store, _ = self._make()
        ctrl.send_message("hello")
        time.sleep(0.5)
        self.assertGreater(len(store.messages), 0)
        ctrl.new_conversation()
        self.assertEqual(len(store.messages), 0)


# ─────────────────────────────────────────
# Test 5: 分层边界验证
# ─────────────────────────────────────────

class TestLayerBoundaries(unittest.TestCase):

    def test_deepseek_client_does_not_store_api_key(self):
        from core.services.deepseek_client import DeepSeekClient
        client = DeepSeekClient()
        self.assertNotIn("api_key",  vars(client))
        self.assertNotIn("_api_key", vars(client))

    def test_conversation_service_has_no_db_code(self):
        import pathlib
        path   = pathlib.Path(__file__).parent.parent / "core" / "services" / "conversation_service.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ["sqlite3", "Repository", ".db", "database"]:
            self.assertNotIn(forbidden, source,
                             f"conversation_service.py 不应包含 '{forbidden}'")

    def test_ui_views_do_not_import_core_services(self):
        import pathlib
        ui_dir = pathlib.Path(__file__).parent.parent / "ui"
        bad    = ["deepseek_client", "conversation_service", "from core"]
        violations = []
        for f in ui_dir.rglob("*.py"):
            src = f.read_text(encoding="utf-8")
            for b in bad:
                if b in src:
                    violations.append(f"{f.name}: '{b}'")
        self.assertEqual(violations, [],
                         "UI 层不允许直接引用 Core:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main(verbosity=2)
