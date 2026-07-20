from anthropic import AsyncAnthropic

from app.ai_providers.base import BaseAIProvider, CompletionResult, Message, ToolCall, ToolDefinition
from app.config import settings
from app.exceptions import AIProviderError


class AnthropicProvider(BaseAIProvider):
    name = "anthropic"
    supports_tools = True

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        api_key = api_key or settings.ANTHROPIC_API_KEY
        if not api_key:
            raise AIProviderError("ANTHROPIC_API_KEY is not set")
        self._client = AsyncAnthropic(api_key=api_key)
        self._default_model = default_model or settings.ANTHROPIC_DEFAULT_MODEL

    def _split_system(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        system = next((m.content for m in messages if m.role == "system"), None)
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        return system, turns

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
        system, turns = self._split_system(messages)
        anthropic_tools = (
            [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]
            if tools
            else None
        )
        try:
            response = await self._client.messages.create(
                model=model or self._default_model,
                system=system,
                messages=turns,
                max_tokens=max_tokens,
                **({"tools": anthropic_tools} if anthropic_tools else {}),
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Anthropic request failed: {exc}") from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        tool_calls = [
            ToolCall(id=block.id, name=block.name, input=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
        dumped = response.model_dump()
        # Only text/tool_use blocks are needed (and safe) to replay back into
        # the conversation on the next turn. Thinking/redacted_thinking blocks
        # round-trip with extra provider-internal fields that the API's input
        # validator rejects if resubmitted verbatim, so drop them here rather
        # than trying to reconstruct their exact accepted shape.
        replay_blocks = [b for b in dumped["content"] if b.get("type") in ("text", "tool_use")]
        return CompletionResult(
            text=text,
            model=response.model,
            provider=self.name,
            raw=dumped,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            content_blocks=replay_blocks,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ):
        system, turns = self._split_system(messages)
        try:
            async with self._client.messages.stream(
                model=model or self._default_model,
                system=system,
                messages=turns,
                max_tokens=max_tokens,
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Anthropic stream failed: {exc}") from exc
