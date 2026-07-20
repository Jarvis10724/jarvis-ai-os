"""
CodeWriterPlugin — generates code from a natural-language spec, optionally
constrained to a language/framework, with brief usage notes.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.exceptions import ValidationError
from app.plugins.base import BasePlugin, PluginResult

SYSTEM_PROMPT = """You are a senior software engineer working inside Jarvis, an AI \
operating system for a small business. Given a spec, produce clean, correct,
well-organized code following the target language/framework's conventions.
Include: the code itself (in fenced blocks with filenames as comments where
multiple files are needed), then a short 'How to run' note, then any
notable assumptions or edge cases. Do not pad with unnecessary explanation."""


class CodeWriterPlugin(BasePlugin):
    name = "code_writer"
    description = "Generates code from a natural-language spec."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {
            "spec": "string (required) — what to build",
            "language": "string (optional) — e.g. 'python', 'typescript'",
            "framework": "string (optional) — e.g. 'fastapi', 'react'",
            "provider": "string (optional) — AI provider override",
        }

    async def run(self, **kwargs) -> PluginResult:
        spec = kwargs.get("spec")
        if not spec:
            raise ValidationError("code_writer requires a 'spec'")
        language = kwargs.get("language", "best judgment for the task")
        framework = kwargs.get("framework", "none specified")

        provider = get_ai_provider(kwargs.get("provider"))
        result = await provider.complete(
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=f"Spec: {spec}\nLanguage: {language}\nFramework: {framework}",
                ),
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        return PluginResult(
            success=True,
            output=result.text,
            message="Code generated.",
            metadata={"provider": result.provider, "model": result.model},
        )
