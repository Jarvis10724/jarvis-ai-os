"""
Reusable Shopify GraphQL Admin API client.

Auth (Phase 1, read-only) supports both current and legacy methods:

  * Client credentials grant (current — Dev Dashboard apps). New custom apps
    no longer expose a static `shpat_` token; the app has a Client ID + Client
    Secret which are exchanged for a 24-hour access token at
    POST https://{shop}/admin/oauth/access_token (grant_type=client_credentials).
    The resulting token is cached in-process and re-fetched shortly before it
    expires. Only valid for an app your own org built, installed on a store you
    own — exactly this integration's case.
  * Legacy static token. If SHOPIFY_ADMIN_API_TOKEN is set it's used directly
    (no exchange) — kept so older admin-created apps keep working.

Read-only by construction: this module issues GraphQL *queries* only — there
is not a single `mutation` anywhere in it. Combined with read-only scopes on
the app, that's defense in depth: neither a coding mistake nor a client bug
can issue a write.

Secrets (client secret / access token) come from settings (env) and are never
logged, never returned to callers, and never placed in an exception message.
"""
import time

import httpx

from app.config import settings
from app.exceptions import IntegrationError

# In-process access-token cache for the client-credentials grant, keyed by
# store domain. Value: (token, monotonic_expiry). A single dict is fine — this
# integration targets one store; the key just future-proofs multi-store.
_token_cache: dict[str, tuple[str, float]] = {}
# Refresh this many seconds before the 24h token actually expires.
_EXPIRY_BUFFER_SECONDS = 120


class ShopifyAdminClient:
    """Thin wrapper over POST {store}/admin/api/{version}/graphql.json."""

    def __init__(self, store_domain: str | None = None, api_version: str | None = None):
        self.store_domain = store_domain or settings.SHOPIFY_STORE_DOMAIN
        self.api_version = api_version or settings.SHOPIFY_API_VERSION

    @staticmethod
    def is_configured() -> bool:
        has_domain = bool(settings.SHOPIFY_STORE_DOMAIN)
        has_static = bool(settings.SHOPIFY_ADMIN_API_TOKEN)
        has_client = bool(settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET)
        return has_domain and (has_static or has_client)

    @staticmethod
    def auth_method() -> str | None:
        if not settings.SHOPIFY_STORE_DOMAIN:
            return None
        if settings.SHOPIFY_ADMIN_API_TOKEN:
            return "admin_api_token"
        if settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET:
            return "client_credentials"
        return None

    def _endpoint(self) -> str:
        return f"https://{self.store_domain}/admin/api/{self.api_version}/graphql.json"

    async def _access_token(self) -> str:
        """Resolve a usable Admin API access token. Legacy static token wins;
        otherwise run (or reuse a cached) client-credentials grant."""
        if settings.SHOPIFY_ADMIN_API_TOKEN:
            return settings.SHOPIFY_ADMIN_API_TOKEN

        if not (settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET):
            raise IntegrationError("Shopify is not configured (no admin token or client credentials).")

        cached = _token_cache.get(self.store_domain or "")
        if cached and cached[1] > time.monotonic():
            return cached[0]

        token, expires_in = await self._fetch_client_credentials_token()
        _token_cache[self.store_domain or ""] = (
            token,
            time.monotonic() + max(60, expires_in - _EXPIRY_BUFFER_SECONDS),
        )
        return token

    async def _fetch_client_credentials_token(self) -> tuple[str, int]:
        """POST {shop}/admin/oauth/access_token, grant_type=client_credentials.
        Returns (access_token, expires_in_seconds). Never leaks the secret."""
        url = f"https://{self.store_domain}/admin/oauth/access_token"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url,
                    data={
                        "client_id": settings.SHOPIFY_CLIENT_ID,
                        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                        "grant_type": "client_credentials",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as exc:
            raise IntegrationError(f"Shopify token request failed: {exc}") from exc

        if resp.status_code in (401, 403):
            raise IntegrationError(
                "Shopify rejected the client credentials (401/403). Check the Client ID/Secret and that the "
                "app is installed on this store and owned by your organization."
            )
        if resp.status_code >= 400:
            raise IntegrationError(f"Shopify token endpoint returned HTTP {resp.status_code}.")

        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise IntegrationError("Shopify token endpoint did not return an access_token.")
        return token, int(body.get("expires_in") or 86399)

    async def execute(self, query: str, variables: dict | None = None) -> dict:
        """Run a GraphQL query and return its `data` object. Raises
        IntegrationError (never leaking a secret) on transport failure, HTTP
        error, GraphQL `errors`, or throttle exhaustion."""
        if not self.store_domain:
            raise IntegrationError("Shopify is not configured (missing store domain).")

        access_token = await self._access_token()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self._endpoint(),
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "X-Shopify-Access-Token": access_token,
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise IntegrationError(f"Shopify request failed: {exc}") from exc

        if resp.status_code in (401, 403):
            # A cached token can go stale (revoked/reinstalled) — drop it so the
            # next call re-runs the grant instead of failing forever.
            _token_cache.pop(self.store_domain or "", None)
            raise IntegrationError(
                "Shopify rejected the credentials (401/403). Check the app's read scopes and that it is "
                "installed on this store."
            )
        if resp.status_code == 429:
            raise IntegrationError("Shopify rate limit hit (429). Try again shortly.")
        if resp.status_code >= 400:
            raise IntegrationError(f"Shopify returned HTTP {resp.status_code}.")

        body = resp.json()
        if body.get("errors"):
            messages = "; ".join(str(e.get("message", e)) for e in body["errors"])
            raise IntegrationError(f"Shopify GraphQL error: {messages}")

        return body.get("data", {})
