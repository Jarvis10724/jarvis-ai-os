"""
LogoDesignPlugin — generates logo concept directions and a simple starter
SVG mark from a brand brief. Text-model based for now; swap in an image-gen
provider later (the `run` contract stays the same, callers won't notice).
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are a senior brand designer working inside Jarvis, an AI \
operating system for a small business. Given a brand brief, produce:
1. Three distinct logo concept directions (name, rationale, style: wordmark/
   icon+wordmark/abstract mark, suggested color palette with hex codes).
2. For the strongest concept, a simple, valid inline SVG (under 40 lines,
   using basic shapes/text, no external fonts or images) as a rough starting mark.
Be concrete."""


class LogoDesignPlugin(BasePlugin):
    name = "logo_design"
    description = "Generates logo concepts and a starter SVG mark from a brand brief."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "brand_name": "string (required)",
            "brief": "string (required) — industry, audience, tone/personality",
            "colors": "string (optional) — preferred color direction",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        brand_name = kwargs.get("brand_name")
        brief = kwargs.get("brief")
        if not brand_name or not brief:
            raise ValidationError("logo_design requires 'brand_name' and 'brief'")
        colors = kwargs.get("colors", "no strong preference")

        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=f"Brand: {brand_name}\nBrief: {brief}\nColor preference: {colors}",
                ),
            ],
            temperature=0.8,
            max_tokens=2000,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Logo concepts generated.",
            metadata={"provider": result.provider, "model": result.model},
        )
