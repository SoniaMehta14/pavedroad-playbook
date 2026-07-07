"""Provider factory.

The orchestration routing table and the interoperability layer's
LLM-assisted resolution both need to go from a config string to a live
provider without hardcoding which vendor they're calling — that hardcoding
is exactly what vendor neutrality is supposed to prevent.
"""

from typing import Any

from .base import LLMProvider

_PROVIDER_NAMES = ("anthropic", "openai_compatible", "local")


def get_provider(name: str, **kwargs: Any) -> LLMProvider:
    """Construct a provider by name: "anthropic" | "openai_compatible" | "local"."""
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(**kwargs)
    if name == "openai_compatible":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(**kwargs)
    if name == "local":
        from .local import OllamaProvider

        return OllamaProvider(**kwargs)
    raise ValueError(f"unknown provider {name!r} — expected one of {_PROVIDER_NAMES}")
