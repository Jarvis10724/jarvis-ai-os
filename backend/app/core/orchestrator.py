"""
The orchestrator is Jarvis's single front door for "do something": given a
plugin name and arguments, it runs the plugin and returns a normalized
result. API endpoints and (eventually) a conversational agent loop both go
through here rather than importing plugins directly, so cross-cutting
concerns (logging, timing, error normalization) live in exactly one place.
"""
import time

from app.exceptions import PluginError
from app.logging_config import get_logger
from app.plugins.base import PluginResult
from app.plugins.registry import registry

logger = get_logger(__name__)


class Orchestrator:
    async def run_plugin(self, plugin_name: str, **kwargs) -> PluginResult:
        plugin = registry.get(plugin_name)
        started = time.perf_counter()
        logger.info("plugin_run_started", plugin=plugin_name, kwargs=list(kwargs.keys()))
        try:
            result = await plugin.run(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.error("plugin_run_failed", plugin=plugin_name, error=str(exc))
            if isinstance(exc, PluginError):
                raise
            raise PluginError(f"Plugin '{plugin_name}' failed: {exc}") from exc
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.info("plugin_run_finished", plugin=plugin_name, elapsed_ms=elapsed_ms)
        return result

    def list_plugins(self) -> list[dict]:
        return registry.list()


orchestrator = Orchestrator()
