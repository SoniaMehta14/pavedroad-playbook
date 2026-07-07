"""Provider-agnostic types for the LLM adapter layer.

Vendor neutrality only means something if the code enforces it: every
provider returns the same CompletionResult shape with token counts and a
computed cost, so the orchestration layer's routing table and cost
guardrails never need to know which provider actually ran the call.
"""

from typing import Literal, Protocol

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CompletionResult(BaseModel):
    text: str
    model: str
    stop_reason: str
    usage: Usage


class LLMProvider(Protocol):
    """A vendor-neutral chat completion call.

    Every adapter (Anthropic, OpenAI-compatible, local) implements this one
    method. Callers depend on the protocol, never on a concrete provider
    class, so swapping providers — or routing different workflow steps to
    different providers as a mixture of experts — is a config change, not
    a rewrite.
    """

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult: ...
