"""
WebBuilderPlugin — turns a plain-language brief into a website plan: page
list, copy, and a basic HTML/CSS starting point. Later this can grow into
full static-site generation or a builder-API integration (Webflow, etc.)
without changing its public contract.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are a senior web designer and copywriter working inside Jarvis, \
an AI operating system for a small business. Given a brief, produce:
1. A recommended page list (with purpose of each page).
2. Homepage copy (headline, subheadline, 3 key sections).
3. A minimal, semantic single-file HTML/CSS starting point for the homepage.
Be concrete and business-appropriate. No filler."""


class WebBuilderPlugin(BasePlugin):
    name = "web_builder"
    description = "Plans and scaffolds websites from a plain-language brief."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "brief": "string (required) — what the site/business is and who it's for",
            "style": "string (optional) — visual/tone direction, e.g. 'minimal, modern, blue palette'",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        brief = kwargs.get("brief")
        if not brief:
            raise ValidationError("web_builder requires a 'brief'")
        style = kwargs.get("style", "clean and modern")

        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(role="user", content=f"Brief: {brief}\nStyle direction: {style}"),
            ],
            temperature=0.6,
            max_tokens=3000,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Website plan generated.",
            metadata={"provider": result.provider, "model": result.model},
        )
