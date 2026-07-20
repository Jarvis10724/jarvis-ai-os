"""
Shopify integration — products, orders, inventory via the Admin API.

STATUS: stub. Simplest path for a single-store owner is a custom app access
token (SHOPIFY_ACCESS_TOKEN) generated in the Shopify admin, rather than a
full public-app OAuth flow — hence is_connected just checks for that token.
"""
import httpx

from app.config import settings
from app.exceptions import IntegrationError
from app.integrations.base import BaseIntegration, IntegrationActionResult


class ShopifyIntegration(BaseIntegration):
    name = "shopify"
    description = "Read/write products, orders, and inventory in Shopify."

    def _base_url(self) -> str:
        if not settings.SHOPIFY_SHOP_URL:
            raise IntegrationError("SHOPIFY_SHOP_URL is not configured")
        return f"https://{settings.SHOPIFY_SHOP_URL}/admin/api/2024-10"

    async def is_connected(self) -> bool:
        # Phase 1 read-only path uses the dedicated custom-app credentials
        # (SHOPIFY_STORE_DOMAIN + SHOPIFY_ADMIN_API_TOKEN), read via
        # app.core.shopify_service. The legacy SHOPIFY_SHOP_URL/ACCESS_TOKEN
        # pair is still honored so an older .env keeps reporting connected.
        return bool(
            (settings.SHOPIFY_STORE_DOMAIN and settings.SHOPIFY_ADMIN_API_TOKEN)
            or (settings.SHOPIFY_SHOP_URL and settings.SHOPIFY_ACCESS_TOKEN)
        )

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        raise IntegrationError(
            "This build uses a custom-app access token (SHOPIFY_ACCESS_TOKEN), "
            "not OAuth. Generate one from Shopify Admin > Settings > Apps > "
            "Develop apps."
        )

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("Not applicable in custom-app token mode")

    async def list_products(self, limit: int = 20) -> IntegrationActionResult:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url()}/products.json",
                    params={"limit": limit},
                    headers={"X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN or ""},
                )
                resp.raise_for_status()
                return IntegrationActionResult(success=True, data=resp.json().get("products", []))
        except httpx.HTTPError as exc:
            raise IntegrationError(f"Shopify request failed: {exc}") from exc

    async def list_orders(self, limit: int = 20) -> IntegrationActionResult:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url()}/orders.json",
                    params={"limit": limit, "status": "any"},
                    headers={"X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN or ""},
                )
                resp.raise_for_status()
                return IntegrationActionResult(success=True, data=resp.json().get("orders", []))
        except httpx.HTTPError as exc:
            raise IntegrationError(f"Shopify request failed: {exc}") from exc
