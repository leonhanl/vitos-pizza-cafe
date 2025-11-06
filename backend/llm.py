"""LLM initialization for Vito's Pizza Cafe application."""

import logging
from functools import lru_cache
from langchain_openai import ChatOpenAI

from .config import Config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm():
    """Get cached LLM instance for the application.

    Returns:
        ChatOpenAI: Configured LLM instance
    """
    llm = ChatOpenAI(
        model=Config.LLM_MODEL,
        base_url=Config.OPENAI_BASE_URL,
        temperature=Config.LLM_TEMPERATURE,
        max_tokens=None,
        timeout=None,
        max_retries=Config.LLM_MAX_RETRIES,
    )

    logger.info(f"LLM initialized: {Config.LLM_MODEL} at {Config.OPENAI_BASE_URL}")
    return llm
