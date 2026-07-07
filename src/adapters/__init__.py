"""LLM provider adapters.

Vendor neutrality is a positioning claim only if the code embodies it. This
package defines a thin provider interface with token accounting built in —
Anthropic by default, any OpenAI-compatible endpoint as a fallback, and local
models for data that can't leave the building — so a portfolio company is never
one pricing change away from a rewrite.
"""

from .base import CompletionResult, LLMProvider, Message, Usage
from .registry import get_provider

__all__ = ["CompletionResult", "LLMProvider", "Message", "Usage", "get_provider"]
