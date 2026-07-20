"""
Amazon Selling Partner API (SP-API) integration — orders, inventory, listings.

STATUS: stub. SP-API uses LWA (Login with Amazon) refresh tokens rather than
a standard authorization-code redirect flow initiated by us; typically the
refresh token is generated once via Seller Central and stored directly
(AMAZON_SP_API_REFRESH_TOKEN), then this class exchanges it for short-lived
access tokens as needed.
"""
from app.config import settings
from app.exceptions import IntegrationError
from app.integrations.base import BaseIntegration, IntegrationActionResult


class AmazonIntegration(BaseIntegration):
    name = "amazon"
    description = "Read orders/inventory and manage listings via Amazon SP-API."

    async def is_connected(self) -> bool:
        return bool(settings.AMAZON_SP_API_REFRESH_TOKEN)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        # SP-API's "Authorize" flow for a self-authorized app is done once in
        # Seller Central, not via a standard redirect. Documented here for
        # interface consistency; not used in practice.
        raise IntegrationError(
            "Amazon SP-API uses Seller Central self-authorization, not an "
            "authorization-code redirect. See AMAZON_SP_API_REFRESH_TOKEN in .env."
        )

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("Not applicable — see get_authorization_url note")

    async def _refresh_access_token(self) -> str:
        # TODO: POST to https://api.amazon.com/auth/o2/token with
        # grant_type=refresh_token using AMAZON_SP_API_REFRESH_TOKEN,
        # AMAZON_SP_API_CLIENT_ID/SECRET.
        raise NotImplementedError("SP-API token refresh not yet implemented")

    async def list_orders(self, created_after: str | None = None) -> IntegrationActionResult:
        # TODO: call SP-API Orders v0 /orders.
        raise NotImplementedError("list_orders not yet implemented")

    async def get_inventory_summary(self) -> IntegrationActionResult:
        # TODO: call SP-API FBA Inventory /summaries.
        raise NotImplementedError("get_inventory_summary not yet implemented")
