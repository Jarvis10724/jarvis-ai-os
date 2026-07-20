"""
Plugin discovery and lookup.

Built-in plugins register themselves in BUILTIN_PLUGINS below. Third-party /
custom plugins can be added the same way without editing this file's logic —
just import the class and append it (or in a future version, discover via
Python entry_points for true out-of-tree plugins).
"""
from app.exceptions import PluginError
from app.logging_config import get_logger
from app.plugins.base import BasePlugin

logger = get_logger(__name__)


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        if plugin.name in self._plugins:
            raise PluginError(f"Plugin '{plugin.name}' is already registered")
        self._plugins[plugin.name] = plugin
        logger.info("plugin_registered", plugin=plugin.name, version=plugin.version)

    def get(self, name: str) -> BasePlugin:
        if name not in self._plugins:
            raise PluginError(f"No plugin named '{name}' is registered")
        return self._plugins[name]

    def list(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.description, "version": p.version}
            for p in self._plugins.values()
        ]

    async def setup_all(self) -> None:
        for plugin in self._plugins.values():
            await plugin.setup()


def _load_builtin_plugins() -> list[BasePlugin]:
    from app.plugins.builtin.automation.plugin import AutomationPlugin
    from app.plugins.builtin.code_writer.plugin import CodeWriterPlugin
    from app.plugins.builtin.deep_research.plugin import DeepResearchPlugin
    from app.plugins.builtin.logo_design.plugin import LogoDesignPlugin
    from app.plugins.builtin.product_creation.plugin import ProductCreationPlugin
    from app.plugins.builtin.project_management.plugin import ProjectManagementPlugin
    from app.plugins.builtin.web_builder.plugin import WebBuilderPlugin

    return [
        WebBuilderPlugin(),
        LogoDesignPlugin(),
        ProductCreationPlugin(),
        DeepResearchPlugin(),
        CodeWriterPlugin(),
        ProjectManagementPlugin(),
        AutomationPlugin(),
    ]


registry = PluginRegistry()


def bootstrap_registry() -> PluginRegistry:
    """Called once at app startup (see app.main lifespan)."""
    for plugin in _load_builtin_plugins():
        registry.register(plugin)
    return registry
