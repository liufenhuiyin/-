# app/container.py
from core.services.conversation_service import ConversationService
from ui.state.ui_state_store import UIStateStore
from controllers.app_controller import AppController


def build_container(api_key: str) -> tuple:
    conv_service = ConversationService(timeout=120.0)
    store        = UIStateStore()
    controller   = AppController(
        store        = store,
        conv_service = conv_service,
        api_key      = api_key,
    )
    return controller, store
