"""
ProjectManagementPlugin — breaks a goal down into a structured task list
with rough sequencing/dependencies. Returns plain data; persisting it as
real Project/Task rows is the API layer's job (see
app/api/v1/endpoints/projects.py), keeping the plugin storage-agnostic.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are a sharp operations/project manager working inside Jarvis, \
an AI operating system for a small business. Given a goal, break it into a
task list. For each task give: title, one-line description, rough effort
(S/M/L), and any dependency on another task. Output as a numbered list, most
foundational tasks first. Keep it realistic for a solo founder or small team."""


class ProjectManagementPlugin(BasePlugin):
    name = "project_management"
    description = "Breaks a goal into a structured, sequenced task list."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "goal": "string (required) — the project/goal to break down",
            "constraints": "string (optional) — timeline, budget, team size, etc.",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        goal = kwargs.get("goal")
        if not goal:
            raise ValidationError("project_management requires a 'goal'")
        constraints = kwargs.get("constraints", "none specified")

        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(role="user", content=f"Goal: {goal}\nConstraints: {constraints}"),
            ],
            temperature=0.4,
            max_tokens=2000,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Task breakdown generated.",
            metadata={"provider": result.provider, "model": result.model},
        )
