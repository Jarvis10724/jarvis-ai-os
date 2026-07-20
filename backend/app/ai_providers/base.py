"""
Provider-agnostic interface for talking to an LLM.

Every provider (OpenAI, Anthropic, Gemini, ...) implements this same
interface, so plugins and the orchestrator never import a vendor SDK
directly — they depend only on `BaseAIProvider`. Swapping or adding a
provider never touches plugin code.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    # Plain string for ordinary turns. A list of provider-native content
    # blocks (dicts) is also accepted, used only when replaying tool_use /
    # tool_result turns back into a tool-calling conversation.
    content: "str | list[dict]"


@dataclass
class ToolDefinition:
    """A tool the model may choose to call, described as JSON schema."""

    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCall:
    """A single tool invocation the model requested."""

    id: str
    name: str
    input: dict


@dataclass
class ImageResult:
    """A generated image, returned as base64 PNG so the caller can store it as
    a data URL / file without a second network round-trip."""

    b64_png: str
    model: str
    provider: str
    prompt: str


@dataclass
class CompletionResult:
    text: str
    model: str
    provider: str
    raw: dict = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    # Provider-native representation of the assistant turn's content
    # (e.g. Anthropic's content block list) — needed to replay this turn
    # back into history verbatim when continuing a tool-calling loop.
    content_blocks: Any = None


class BaseAIProvider(ABC):
    """Subclass this for each vendor. Keep the public surface small and
    stable — that's what makes providers swappable."""

    name: str = "base"
    # Whether this provider's `complete()` honors the `tools` kwarg. Only
    # Anthropic does today (it's the configured default); other providers
    # will keep working for plain chat but the agentic tool-calling loop
    # in the chat endpoint only runs against a provider that supports it.
    supports_tools: bool = False
    # Whether this provider can generate images (see generate_image). The
    # Logo Studio uses this; when no image-capable provider is configured the
    # workspace records the concept spec instead of fabricating an image.
    supports_images: bool = False

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: "list[ToolDefinition] | None" = None,
        **kwargs,
    ) -> CompletionResult:
        """Send messages, return a single completed response."""
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ):
        """Yield response text chunks as they arrive."""
        raise NotImplementedError
        yield  # pragma: no cover - makes this an async generator

    async def generate_image(
        self, prompt: str, *, size: str = "1024x1024", model: str | None = None
    ) -> "ImageResult":
        """Generate an image from a text prompt. Optional capability — the
        default raises so callers can detect (and gracefully degrade) when the
        configured provider can't make images. Guarded by `supports_images`."""
        from app.exceptions import AIProviderError

        raise AIProviderError(f"The '{self.name}' provider does not support image generation.")
