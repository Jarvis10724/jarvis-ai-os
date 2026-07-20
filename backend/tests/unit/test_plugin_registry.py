from app.plugins.registry import PluginRegistry
from app.plugins.base import BasePlugin, PluginResult
from app.exceptions import PluginError

import pytest


class _EchoPlugin(BasePlugin):
    name = "echo"
    description = "test plugin"

    async def run(self, **kwargs) -> PluginResult:
        return PluginResult(success=True, output=kwargs)


@pytest.mark.asyncio
async def test_register_and_run():
    reg = PluginRegistry()
    reg.register(_EchoPlugin())
    assert reg.list() == [{"name": "echo", "description": "test plugin", "version": "0.1.0"}]

    plugin = reg.get("echo")
    result = await plugin.run(x=1)
    assert result.success
    assert result.output == {"x": 1}


def test_duplicate_registration_raises():
    reg = PluginRegistry()
    reg.register(_EchoPlugin())
    with pytest.raises(PluginError):
        reg.register(_EchoPlugin())


def test_unknown_plugin_raises():
    reg = PluginRegistry()
    with pytest.raises(PluginError):
        reg.get("does_not_exist")
