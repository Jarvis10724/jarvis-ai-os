"""
ProductCreationPlugin — turns a product idea into a structured spec: naming,
positioning, feature set, pricing suggestion, and a launch checklist.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are a senior product manager working inside Jarvis, an AI \
operating system for a small business. Given a product idea, produce:
1. Sharpened positioning (target customer, core value prop, one-line pitch).
2. A v1 feature set (must-have vs nice-to-have).
3. A pricing suggestion with rationale.
4. A launch checklist (10-15 concrete steps, ordered).
Be concrete and realistic for a small/solo team."""


class ProductCreationPlugin(BasePlugin):
    name = "product_creation"
    description = "Turns a product idea into a spec, pricing, and launch checklist."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "idea": "string (required) — the product idea",
            "target_market": "string (optional)",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        idea = kwargs.get("idea")
        if not idea:
            raise ValidationError("product_creation requires an 'idea'")
        target_market = kwargs.get("target_market", "not specified")

        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(role="user", content=f"Idea: {idea}\nTarget market: {target_market}"),
            ],
            temperature=0.6,
            max_tokens=2500,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Product spec generated.",
            metadata={"provider": result.provider, "model": result.model},
        )
