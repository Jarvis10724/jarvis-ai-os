# Writing a Jarvis Plugin

A plugin is any self-contained capability: "build a website," "design a
logo," "research a topic." Jarvis calls plugins only through the orchestrator,
so a new plugin never requires touching existing code.

## 1. Create the folder

```
backend/app/plugins/builtin/<your_plugin_name>/
  __init__.py
  plugin.py
```

## 2. Implement `BasePlugin`

```python
from app.plugins.base import BasePlugin, PluginResult
from app.ai_providers.factory import get_ai_provider
from app.ai_providers.base import Message
from app.exceptions import ValidationError

class YourPlugin(BasePlugin):
    name = "your_plugin_name"          # unique, snake_case, stable
    description = "One line describing what this does."
    version = "0.1.0"

    def input_schema(self) -> dict:
        return {"some_arg": "string (required) — what it's for"}

    async def run(self, **kwargs) -> PluginResult:
        value = kwargs.get("some_arg")
        if not value:
            raise ValidationError("your_plugin_name requires 'some_arg'")

        provider = get_ai_provider(kwargs.get("provider"))  # honors override, else DEFAULT_AI_PROVIDER
        result = await provider.complete(
            messages=[
                Message(role="system", content="Your system prompt..."),
                Message(role="user", content=value),
            ],
        )
        return PluginResult(success=True, output=result.text, message="Done.")
```

Rules of thumb:

- Validate required kwargs yourself and raise `ValidationError` (or another
  `JarvisError` subclass) rather than letting a `KeyError`/`TypeError` bubble up.
- Never import a vendor AI SDK directly — always go through
  `get_ai_provider()`. That's what keeps plugins swappable across
  Anthropic/OpenAI/Gemini.
- If the plugin needs an external service (email, Shopify, etc.), get it via
  `app.integrations.registry.get_integration(name, credentials=...)`, not by
  importing the integration class directly.
- Keep `run()` idempotent-ish and side-effect-aware — it may be retried.

## 3. Register it

In `backend/app/plugins/registry.py`, add the import and instance to
`_load_builtin_plugins()`:

```python
from app.plugins.builtin.your_plugin_name.plugin import YourPlugin
...
return [
    ...,
    YourPlugin(),
]
```

## 4. Call it

- API: `POST /api/v1/plugins/{plugin_name}/run` with `{"args": {...}}`.
- Dashboard: add an entry to `ACTIONS` in
  `frontend/src/components/QuickActions.tsx` so it shows up as a one-click
  action.

## 5. Test it

Add a test under `backend/tests/unit/` following the pattern in
`test_plugin_registry.py` — at minimum, assert `run()` raises `ValidationError`
on missing args and returns a `PluginResult` with `success=True` on valid ones
(mock `get_ai_provider` so tests don't call a real API).

## Writing an integration instead

Same idea, different base class (`app.integrations.base.BaseIntegration`) and
folder (`app/integrations/`). See `shopify_integration.py` for a fully working
example (simple token auth) and `email_integration.py` for the OAuth-flow
pattern (authorization URL → code exchange → stored credentials).
