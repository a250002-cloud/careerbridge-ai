"""
services/llm/base.py
Abstract base class for LLM provider adapters.
"""
from abc import ABC, abstractmethod


class LLMBase(ABC):
    """Provider-agnostic LLM interface."""

    @abstractmethod
    def chat(self, messages: list[dict], max_tokens: int = 512) -> dict:
        """
        Send messages and return {content, tokens_in, tokens_out, cost, model}.
        messages: [{"role": "system"|"user"|"assistant", "content": str}]
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is reachable."""
        ...
