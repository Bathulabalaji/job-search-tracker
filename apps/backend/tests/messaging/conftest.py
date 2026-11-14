# These tests use the same harness as the assistant tests (fake models, signed-in user).
from tests.assistant.conftest import chat, chat_settings

__all__ = ["chat", "chat_settings"]
