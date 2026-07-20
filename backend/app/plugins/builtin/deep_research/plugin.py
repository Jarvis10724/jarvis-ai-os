"""
DeepResearchPlugin — structured multi-angle research on a topic or question.

Current version reasons from the model's own knowledge and clearly flags
that as a limitation. The `web_search` hook is where a real search
tool/integration plugs in later (Brave/SerpAPI/etc.) — once wired up, this
plugin should call it before drafting the synthesis, with no change to the
plugin's public `run()` contract.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are a rigorous research analyst working inside Jarvis, an AI \
operating system for a small business. Given a research question, produce:
1. A short framing of the question and why it matters.
2. Key findings, organized by sub-topic, with explicit confidence levels.
3. Notable disagreements or uncertainty in the space.
4. Concrete next steps or sources the user should verify directly.
If you are not calling a live web search tool, say so plainly and flag that
findings should be verified against current sources before being relied on."""


class DeepResearchPlugin(BasePlugin):
    name = "deep_research"
    description = "Structured multi-angle research synthesis on a topic or question."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "question": "string (required) — the research question",
            "depth": "string (optional) — 'quick' | 'standard' | 'deep' (default standard)",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        question = kwargs.get("question")
        if not question:
            raise ValidationError("deep_research requires a 'question'")
        depth = kwargs.get("depth", "standard")

        # TODO: once a web-search integration exists, fetch and inject
        # real sources here before calling the model.
        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(role="user", content=f"Research question: {question}\nDepth: {depth}"),
            ],
            temperature=0.4,
            max_tokens=3000,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Research synthesis generated (model knowledge only — verify sources).",
            metadata={"provider": result.provider, "model": result.model, "used_web_search": False},
        )
