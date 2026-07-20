"""
Contract every Jarvis capability (website builder, logo design, deep
research, ...) must implement. The orchestrator only ever talks to plugins
through this interface, so adding a new capability never requires touching
the orchestrator or API layer — just drop a new plugin in builtin/ (or an
external package) and register it.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginResult:
    success: bool
    output: Any = None
    message: str = ""
    metadata: dict = field(default_factory=dict)


class BasePlugin(ABC):
    """Subclass this to add a new Jarvis capability."""

    #: unique, stable identifier — used in the registry, DB, and API
    name: str = "base_plugin"
    #: short human-readable description shown in the UI / plugin list
    description: str = ""
    #: semantic version of this plugin, independent of the app version
    version: str = "0.1.0"

    async def setup(self) -> None:
        """Optional one-time initialization (open connections, load models).
        Called once when the plugin is registered."""
        return None

    @abstractmethod
    async def run(self, **kwargs) -> PluginResult:
        """Execute the plugin's capability. kwargs are plugin-specific and
        should be validated by the plugin itself (or a pydantic schema)."""
        raise NotImplementedError

    def input_schema(self) -> dict:
        """Optional JSON-schema-like description of expected kwargs, used to
        auto-generate API docs / a UI form. Override in subclasses."""
        return {}
