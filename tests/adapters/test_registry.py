import pytest

from adapters import get_provider
from adapters.local import OllamaProvider
from adapters.openai_compat import OpenAICompatProvider


def test_get_provider_local_returns_ollama_provider() -> None:
    provider = get_provider("local", base_url="http://localhost:11434")
    assert isinstance(provider, OllamaProvider)


def test_get_provider_openai_compatible_returns_that_provider() -> None:
    provider = get_provider("openai_compatible", base_url="https://example.test/v1")
    assert isinstance(provider, OpenAICompatProvider)


def test_get_provider_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("carrier-pigeon")
