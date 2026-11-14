# The golden suite runs on the same harness as the assistant tests.
from tests.assistant.conftest import chat, chat_settings

__all__ = ["chat", "chat_settings"]
