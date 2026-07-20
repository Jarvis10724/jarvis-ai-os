import google.generativeai as genai

from app.ai_providers.base import BaseAIProvider, CompletionResult, Message
from app.config import settings
from app.exceptions import AIProviderError


class GeminiProvider(BaseAIProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        api_key = api_key or settings.GEMINI_API_KEY
        if not api_key:
            raise AIProviderError("GEMINI_API_KEY is not set")
        genai.configure(api_key=api_key)
        self._default_model = default_model or settings.GEMINI_DEFAULT_MODEL

    def _build_model(self, messages: list[Message], model: str | None):
        system = next((m.content for m in messages if m.role == "system"), None)
        return genai.GenerativeModel(
            model_name=model or self._default_model,
            system_instruction=system,
        )

    def _to_gemini_turns(self, messages: list[Message]) -> list[dict]:
        role_map = {"user": "user", "assistant": "model"}
        return [
            {"role": role_map[m.role], "parts": [m.content]}
            for m in messages
            if m.role in role_map
        ]

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
        # Tool-calling isn't implemented for Gemini yet — see OpenAIProvider
        # for the same note.
        if tools:
            raise AIProviderError("Tool calling isn't implemented for the Gemini provider yet.")
        gemini_model = self._build_model(messages, model)
        try:
            response = await gemini_model.generate_content_async(
                self._to_gemini_turns(messages),
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature, max_output_tokens=max_tokens
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Gemini request failed: {exc}") from exc

        return CompletionResult(
            text=response.text,
            model=model or self._default_model,
            provider=self.name,
            raw={"candidates": [c.content.parts[0].text for c in response.candidates]},
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
        gemini_model = self._build_model(messages, model)
        try:
            response = await gemini_model.generate_content_async(
                self._to_gemini_turns(messages),
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature, max_output_tokens=max_tokens
                ),
                stream=True,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Gemini stream failed: {exc}") from exc
