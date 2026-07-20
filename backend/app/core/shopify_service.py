"""
Orchestration layer between Shopify's HTTP endpoints and the GraphQL Admin
client. Mirrors gmail_service: endpoints never touch the client or settings
directly, and every read funnels through here so the workspace-isolation
guard and the capability audit trail are applied in exactly one place.

Read-only, Phase 1: every function issues a GraphQL *query* only, and each
goes through capability_service.authorize_direct_action() (which raises for
any approval-gated action) before running. No write path exists.

Workspace isolation: the store's credentials live in env (settings) and are
bound to exactly one Jarvis company via SHOPIFY_WORKSPACE_ID. Any request
scoped to a different company is refused, so Shopify data can never surface
in another workspace.
"""
from sqlalchemy.orm import Session

from app.config import settings
from app.core import capability_service
from app.exceptions import IntegrationError, ValidationError
from app.integrations.shopify_admin_client import ShopifyAdminClient

CAPABILITY_NAME = "shopify"


def is_configured() -> bool:
    """Credentials present AND bound to a workspace — all three env values
    required. Without the binding we can't guarantee isolation, so we treat
    it as not-configured rather than serving data account-wide."""
    return ShopifyAdminClient.is_configured() and bool(settings.SHOPIFY_WORKSPACE_ID)


def _assert_workspace(company_id: str | None) -> None:
    """Refuse any request whose active workspace isn't the one bound to the
    Shopify credentials. `company_id=None` (account-wide) is also refused —
    Shopify data is always workspace-scoped here."""
    if not is_configured():
        raise ValidationError(
            "Shopify is not configured. Set SHOPIFY_STORE_DOMAIN, SHOPIFY_ADMIN_API_TOKEN, and "
            "SHOPIFY_WORKSPACE_ID in the backend .env."
        )
    if company_id != settings.SHOPIFY_WORKSPACE_ID:
        raise ValidationError(
            "Shopify is only connected to the Primal Penni workspace. Switch to that workspace to view its store data."
        )


def status(owner_id: str, company_id: str | None) -> dict:
    """Non-secret connection status for the Settings card. Returns booleans
    and the (non-secret) store domain only — never the token."""
    configured = is_configured()
    bound_to_active = configured and company_id == settings.SHOPIFY_WORKSPACE_ID
    return {
        "configured": configured,
        "store_domain": settings.SHOPIFY_STORE_DOMAIN if configured else None,
        "api_version": settings.SHOPIFY_API_VERSION if configured else None,
        # "client_credentials" (Dev Dashboard) or "admin_api_token" (legacy).
        "auth_method": ShopifyAdminClient.auth_method() if configured else None,
        "bound_workspace_id": settings.SHOPIFY_WORKSPACE_ID if configured else None,
        "active_workspace_is_bound": bound_to_active,
        "read_only": True,
    }


async def _run(db: Session, *, owner_id: str, company_id: str | None, action_type: str, query: str, variables: dict | None = None) -> dict:
    """Gate → query → audit. Every read below is one call to this."""
    _assert_workspace(company_id)
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type=action_type, company_id=company_id
    )
    client = ShopifyAdminClient()
    try:
        data = await client.execute(query, variables)
    except IntegrationError:
        raise
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type=action_type, company_id=company_id
    )
    return data


# ---------------------------------------------------------------------------
# Read queries. Kept small and explicit — each returns Shopify's raw `data`
# subtree for that resource. Deliberately no fragments/mutations.
# ---------------------------------------------------------------------------

_PRODUCTS_Q = """
query Products($first: Int!) {
  products(first: $first) {
    edges { node {
      id title handle status totalInventory
      variants(first: 20) { edges { node { id title sku price inventoryQuantity } } }
    } }
  }
}
"""

_COLLECTIONS_Q = """
query Collections($first: Int!) {
  collections(first: $first) { edges { node { id title handle productsCount { count } } } }
}
"""

_INVENTORY_Q = """
query Inventory($first: Int!) {
  inventoryItems(first: $first) {
    edges { node {
      id sku tracked
      inventoryLevels(first: 10) { edges { node { location { name } quantities(names: ["available"]) { name quantity } } } }
    } }
  }
}
"""

_ORDERS_Q = """
query Orders($first: Int!) {
  orders(first: $first, sortKey: CREATED_AT, reverse: true) {
    edges { node {
      id name createdAt displayFinancialStatus displayFulfillmentStatus
      totalPriceSet { shopMoney { amount currencyCode } }
      customer { displayName }
    } }
  }
}
"""

_CUSTOMERS_Q = """
query Customers($first: Int!) {
  customers(first: $first) {
    edges { node { id displayName email numberOfOrders amountSpent { amount currencyCode } } }
  }
}
"""

_DISCOUNTS_Q = """
query Discounts($first: Int!) {
  discountNodes(first: $first) {
    edges { node { id discount { __typename ... on DiscountCodeBasic { title status } ... on DiscountAutomaticBasic { title status } } } }
  }
}
"""

_THEMES_Q = """
query Themes($first: Int!) {
  themes(first: $first) { edges { node { id name role } } }
}
"""

_SETTINGS_Q = """
query Shop {
  shop {
    name email myshopifyDomain
    primaryDomain { url }
    currencyCode
    billingAddress { country city }
    plan { displayName }
  }
}
"""

_METAFIELDS_Q = """
query ProductMetafields($first: Int!) {
  products(first: $first) {
    edges { node { id title metafields(first: 10) { edges { node { namespace key value type } } } } }
  }
}
"""

_METAOBJECTS_Q = """
query Metaobjects($type: String!, $first: Int!) {
  metaobjects(type: $type, first: $first) {
    edges { node { id handle type fields { key value } } }
  }
}
"""


async def list_products(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_products", query=_PRODUCTS_Q, variables={"first": first})


async def list_collections(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_collections", query=_COLLECTIONS_Q, variables={"first": first})


async def list_inventory(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_inventory", query=_INVENTORY_Q, variables={"first": first})


async def list_orders(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_orders", query=_ORDERS_Q, variables={"first": first})


async def list_customers(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_customers", query=_CUSTOMERS_Q, variables={"first": first})


async def list_discounts(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_discounts", query=_DISCOUNTS_Q, variables={"first": first})


async def list_themes(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_themes", query=_THEMES_Q, variables={"first": first})


async def get_settings(db, *, owner_id, company_id):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="get_settings", query=_SETTINGS_Q)


async def list_metafields(db, *, owner_id, company_id, first=20):
    return await _run(db, owner_id=owner_id, company_id=company_id, action_type="list_metafields", query=_METAFIELDS_Q, variables={"first": first})


async def list_metaobjects(db, *, owner_id, company_id, metaobject_type, first=20):
    return await _run(
        db, owner_id=owner_id, company_id=company_id, action_type="list_metaobjects",
        query=_METAOBJECTS_Q, variables={"type": metaobject_type, "first": first},
    )
