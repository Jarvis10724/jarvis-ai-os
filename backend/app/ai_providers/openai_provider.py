from openai import AsyncOpenAI

from app.ai_providers.base import BaseAIProvider, CompletionResult, ImageResult, Message
from app.config import settings
from app.exceptions import AIProviderError


class OpenAIProvider(BaseAIProvider):
    name = "openai"
    supports_images = True

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        api_key = api_key or settings.OPENAI_API_KEY
        if not api_key:
            raise AIProviderError("OPENAI_API_KEY is not set")
        self._client = AsyncOpenAI(api_key=api_key)
        self._default_model = default_model or settings.OPENAI_DEFAULT_MODEL
        self._image_model = settings.OPENAI_IMAGE_MODEL

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools=None,
        **kwargs,
    ) -> CompletionResult:
        # Tool-calling isn't implemented for OpenAI yet — supports_tools is
        # False so the chat endpoint's tool loop never routes here with
        # tools set, but guard anyway rather than silently ignoring it.
        if tools:
            raise AIProviderError("Tool calling isn't implemented for the OpenAI provider yet.")
        try:
            response = await self._client.chat.completions.create(
                model=model or self._default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        choice = response.choices[0]
        return CompletionResult(
            text=choice.message.content or "",
            model=response.model,
            provider=self.name,
            raw=response.model_dump(),
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
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
        try:
            stream = await self._client.chat.completions.create(
                model=model or self._default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"OpenAI stream failed: {exc}") from exc

    async def generate_image(
        self, prompt: str, *, size: str = "1024x1024", model: str | None = None
    ) -> ImageResult:
        try:
            response = await self._client.images.generate(
                model=model or self._image_model,
                prompt=prompt,
                size=size,
                n=1,
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"OpenAI image generation failed: {exc}") from exc

        datum = response.data[0]
        b64 = getattr(datum, "b64_json", None)
        if not b64:
            # Some models return a URL instead of inline base64; we ask for
            # base64 by default but guard so the caller always gets bytes.
            raise AIProviderError("OpenAI returned no inline image data.")
        return ImageResult(
            b64_png=b64, model=model or self._image_model, provider=self.name, prompt=prompt
        )
