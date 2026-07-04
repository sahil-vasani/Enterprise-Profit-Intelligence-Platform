"""
memory.py — Conversation memory for the AI Business Copilot.
Uses LangChain's ConversationBufferWindowMemory to keep recent turns.
"""

from langchain.memory import ConversationBufferWindowMemory

from config import MEMORY_WINDOW_SIZE
from logger import get_logger

log = get_logger("memory")

_memory: ConversationBufferWindowMemory | None = None


def get_memory() -> ConversationBufferWindowMemory:
    """Return the conversation memory instance (created once)."""
    global _memory
    if _memory is None:
        _memory = ConversationBufferWindowMemory(
            k=MEMORY_WINDOW_SIZE,
            return_messages=True,
            memory_key="chat_history",
        )
        log.info("Conversation memory initialized (window=%d).", MEMORY_WINDOW_SIZE)
    return _memory


def clear_memory() -> None:
    """Clear conversation history."""
    global _memory
    if _memory is not None:
        _memory.clear()
        log.info("Conversation memory cleared.")
