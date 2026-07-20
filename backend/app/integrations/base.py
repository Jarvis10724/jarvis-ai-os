"""
Contract every external service connection implements.

Each integration owns its own auth flow (OAuth or API key), stores its
credentials via IntegrationCredential, and exposes a small set of actions.
The orchestrator and plugins call integrations only through this interface,
so a plugin like `automation` can say "send an email" without knowing
whether that's Gmail, Outlook, or SES underneath.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntegrationActionResult:
    success: bool
    data: Any = None
    message: str = ""
    metadata: dict = field(default_factory=dict)


class BaseIntegration(ABC):
    #: unique identifier, matches IntegrationCredential.provider values
    name: str = "base_integration"
    description: str = ""

    def __init__(self, credentials: dict | None = None):
        """`credentials` is whatever was stored in IntegrationCredential for
        this provider (access/refresh tokens, extra_json, etc.), loaded by
        the caller. Integrations never read from settings/env directly for
        per-user secrets — only for the app's own client id/secret."""
        self.credentials = credentials or {}

    @abstractmethod
    async def is_connected(self) -> bool:
        """Whether usable credentials are present (does not guarantee they're
        still valid — call a cheap API method to verify if that matters)."""
        raise NotImplementedError

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Return the URL to send the user to begin the OAuth flow."""
        raise NotImplementedError

    @abstractmethod
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        """Exchange an OAuth callback code for tokens. Returns the dict to
        persist into IntegrationCredential."""
        raise NotImplementedError
