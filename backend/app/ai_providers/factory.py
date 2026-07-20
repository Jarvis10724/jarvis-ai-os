"""
Single entry point for getting an AI provider instance.

Usage:
    from app.ai_providers.factory import get_ai_provider
    provider = get_ai_provider()              # uses DEFAULT_AI_PROVIDER
    provider = get_ai_provider("openai")       # explicit override

Providers are constructed lazily (only when first requested) so a missing
API key for a provider you don't use never breaks app startup.
"""
from functools import lru_cache

from app.ai_providers.base import BaseAIProvider
from app.config import settings
from app.exceptions import AIProviderError

_PROVIDER_REGISTRY = {
    "anthropic": "app.ai_providers.anthropic_provider.AnthropicProvider",
    "openai": "app.ai_providers.openai_provider.OpenAIProvider",
    "gemini": "app.ai_providers.gemini_provider.GeminiProvider",
}


def _import_class(dotted_path: str):
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@lru_cache
def get_ai_provider(name: str | None = None) -> BaseAIProvider:
    provider_name = name or settings.DEFAULT_AI_PROVIDER
    if provider_name not in _PROVIDER_REGISTRY:
        raise AIProviderError(
            f"Unknown AI provider '{provider_name}'. "
            f"Available: {list(_PROVIDER_REGISTRY)}"
        )
    provider_cls = _import_class(_PROVIDER_REGISTRY[provider_name])
    return provider_cls()


def get_image_provider() -> BaseAIProvider | None:
    """The first configured provider that can generate images, or None if none
    is set up. Callers use this to degrade gracefully (record the concept spec)
    rather than fabricate an image when no image API is available."""
    # Prefer the default if it happens to be image-capable, then any provider
    # whose key is present. Construction raises if the key is missing, which is
    # exactly our "not configured" signal — swallow it and try the next.
    order = [settings.DEFAULT_AI_PROVIDER] + [p for p in _PROVIDER_REGISTRY if p != settings.DEFAULT_AI_PROVIDER]
    for name in order:
        try:
            provider = get_ai_provider(name)
        except AIProviderError:
            continue
        if getattr(provider, "supports_images", False):
            return provider
    return None
