"""
llm.py — LLM initialization for the AI Business Copilot.
Provides a single get_llm() function that returns a ChatOpenAI instance.
"""

from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
import requests

from config import OLLAMA_MODEL, OLLAMA_BASE_URL, TEMPERATURE, MAX_TOKENS
from logger import get_logger

log = get_logger("llm")

_llm_instance = None

class FallbackLLM(BaseChatModel):
    """A fallback LLM that returns a specific error message if Ollama is unreachable."""
    @property
    def _llm_type(self) -> str:
        return "fallback"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatResult, ChatGeneration
        message = AIMessage(content="Local AI model is not running. Start Ollama using ollama serve and ollama run qwen2.5:7b")
        return ChatResult(generations=[ChatGeneration(message=message)])

def get_llm() -> BaseChatModel:
    """Return a configured ChatOllama instance (singleton)."""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    # Check if Ollama is running
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code != 200:
            log.error("Ollama server responded with status %s", response.status_code)
            return FallbackLLM()
    except Exception as e:
        log.error("Ollama server is unreachable: %s", e)
        return FallbackLLM()

    _llm_instance = ChatOllama(
        model=OLLAMA_MODEL,
        temperature=TEMPERATURE,
        num_predict=MAX_TOKENS,
        top_p=0.9,
        repeat_penalty=1.05,
        base_url=OLLAMA_BASE_URL,
    )
    log.info("LLM initialized: model=%s, temperature=%s", OLLAMA_MODEL, TEMPERATURE)
    return _llm_instance
