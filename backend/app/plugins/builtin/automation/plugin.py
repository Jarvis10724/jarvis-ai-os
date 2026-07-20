"""
AutomationPlugin — designs a repeatable workflow from a plain-language
description of a repetitive task, expressed as discrete triggerable steps.

This plugin *designs* automations; actually running them on a schedule is
the job of a future scheduler/worker (Redis + a task queue is already
provisioned in docker-compose.yml for this). Keeping design and execution
separate means the execution engine can change without touching this code.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are an automation engineer working inside Jarvis, an AI \
operating system for a small business. Given a description of a repetitive
task, produce a workflow design:
1. Trigger (schedule, event, or manual).
2. Ordered steps, each naming the system/integration involved (email, Google
   Drive, QuickBooks, Amazon, Shopify, social media, or "AI reasoning step").
3. Failure handling / what should alert the human.
Be concrete about which integration each step needs — flag any that Jarvis
doesn't have connected yet as 'requires integration: <name>'."""


class AutomationPlugin(BasePlugin):
    name = "automation"
    description = "Designs repeatable automation workflows from a task description."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "task_description": "string (required) — the repetitive task to automate",
            "frequency": "string (optional) — e.g. 'daily', 'on new order'",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        task_description = kwargs.get("task_description")
        if not task_description:
            raise ValidationError("automation requires a 'task_description'")
        frequency = kwargs.get("frequency", "not specified")

        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=f"Task: {task_description}\nDesired frequency: {frequency}",
                ),
            ],
            temperature=0.4,
            max_tokens=2000,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Automation workflow designed.",
            metadata={"provider": result.provider, "model": result.model},
        )
