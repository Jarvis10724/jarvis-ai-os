"""
Brand Brain: read-only import from Shopify into Jarvis's structured source of
truth, and the reads other features consume.

No live Shopify calls — the GraphQL client is monkeypatched, so tests run
offline and deterministically. What's verified:
  * a sync walks products/collections/shop and populates the brain,
  * every imported field (tags, variants, images, pricing, SEO) round-trips,
  * reads are served from Jarvis's DB and scoped to the owning workspace,
  * the sync issues QUERIES ONLY (never a mutation) — the store is never written,
  * writes stay disabled (write_enabled False),
  * a re-sync mirrors the store (prunes removed products),
  * the admin token never appears in any response.
"""
import pytest

from app.config import settings

API = "/api/v1"
FAKE_TOKEN = "shpat_brandbrain_never_serialized"

_AUTH_FIELDS = (
    "SHOPIFY_STORE_DOMAIN",
    "SHOPIFY_CLIENT_ID",
    "SHOPIFY_CLIENT_SECRET",
    "SHOPIFY_ADMIN_API_TOKEN",
    "SHOPIFY_WORKSPACE_ID",
    "SHOPIFY_WRITE_ENABLED",
)


@pytest.fixture
def shopify_env():
    saved = {f: getattr(settings, f) for f in _AUTH_FIELDS}
    for f in _AUTH_FIELDS:
        setattr(settings, f, None)
    settings.SHOPIFY_WRITE_ENABLED = False
    yield
    for f, v in saved.items():
        setattr(settings, f, v)


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name):
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def _bind(company_id):
    settings.SHOPIFY_STORE_DOMAIN = "primal-penni.myshopify.com"
    settings.SHOPIFY_ADMIN_API_TOKEN = FAKE_TOKEN
    settings.SHOPIFY_WORKSPACE_ID = company_id


def _product_node(pid, title, sku, price, tags):
    return {
        "node": {
            "id": f"gid://shopify/Product/{pid}",
            "title": title,
            "handle": title.lower().replace(" ", "-"),
            "status": "ACTIVE",
            "description": f"{title} description.",
            "productType": "Serum",
            "vendor": "Primal Penni",
            "tags": tags,
            "totalInventory": 100,
            "onlineStoreUrl": f"https://primalpennicollective.com/products/{pid}",
            "priceRangeV2": {
                "minVariantPrice": {"amount": price, "currencyCode": "USD"},
                "maxVariantPrice": {"amount": price, "currencyCode": "USD"},
            },
            "featuredImage": {"url": f"https://cdn/{pid}.jpg", "altText": title},
            "images": {"edges": [{"node": {"url": f"https://cdn/{pid}.jpg", "altText": title}}]},
            "seo": {"title": title, "description": f"{title} SEO"},
            "variants": {"edges": [{"node": {
                "id": f"gid://shopify/ProductVariant/{pid}",
                "title": "30ml", "sku": sku, "price": price, "compareAtPrice": None,
                "inventoryQuantity": 100, "availableForSale": True,
                "selectedOptions": [{"name": "Size", "value": "30ml"}],
                "image": {"url": f"https://cdn/{pid}v.jpg", "altText": None},
            }}]},
        }
    }


def _make_fake_execute(products):
    """A fake ShopifyAdminClient.execute that serves the given product list,
    plus one collection and the shop record — and asserts read-only."""
    async def fake_execute(self, query, variables=None):
        assert "mutation" not in query.lower(), "Brand Brain sync must be read-only"
        if "ProductsFull" in query:
            return {"products": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": products}}
        if "CollectionsFull" in query:
            return {"collections": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": [
                {"node": {"id": "gid://shopify/Collection/1", "title": "Serums", "handle": "serums",
                          "description": "All serums", "productsCount": {"count": 3},
                          "image": {"url": "https://cdn/col.jpg", "altText": None}}}
            ]}}
        if "shop {" in query or "query Shop" in query:
            return {"shop": {
                "name": "Primal Penni", "email": "hello@primalpennicollective.com",
                "myshopifyDomain": "primal-penni.myshopify.com",
                "primaryDomain": {"url": "https://primalpennicollective.com"},
                "currencyCode": "USD", "billingAddress": {"country": "US", "city": "Austin"},
                "plan": {"displayName": "Shopify"},
            }}
        return {}
    return fake_execute


def test_sync_populates_brand_brain(client, shopify_env, monkeypatch):
    headers = _login(client, "bb-sync@example.com")
    company = _company(client, headers, "Primal Penni")
    _bind(company)
    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute",
        _make_fake_execute([
            _product_node(1, "Copper Glow Serum", "PP-CGS-30", "48.00", ["bestseller", "copper"]),
            _product_node(2, "Renewal Night Cream", "PP-RNC-50", "54.00", ["night"]),
        ]),
    )

    resp = client.post(f"{API}/brand-brain/sync?company_id={company}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["product_count"] == 2
    assert body["collection_count"] == 1
    assert body["store_name"] == "Primal Penni"
    assert body["read_only"] is True and body["write_enabled"] is False
    assert FAKE_TOKEN not in resp.text


def test_reads_return_imported_data(client, shopify_env, monkeypatch):
    headers = _login(client, "bb-read@example.com")
    company = _company(client, headers, "Primal Penni")
    _bind(company)
    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute",
        _make_fake_execute([_product_node(1, "Copper Glow Serum", "PP-CGS-30", "48.00", ["bestseller", "copper"])]),
    )
    client.post(f"{API}/brand-brain/sync?company_id={company}", headers=headers)

    summary = client.get(f"{API}/brand-brain?company_id={company}", headers=headers).json()
    assert summary["exists"] is True
    assert summary["store_name"] == "Primal Penni"
    assert summary["product_count"] == 1

    products = client.get(f"{API}/brand-brain/products?company_id={company}", headers=headers).json()
    assert len(products) == 1
    p = products[0]
    assert p["title"] == "Copper Glow Serum"
    assert p["price_min"] == 48.0 and p["currency"] == "USD"
    assert p["tags"] == ["bestseller", "copper"]
    assert p["variants"][0]["sku"] == "PP-CGS-30"
    assert p["images"][0]["url"].startswith("https://cdn/")

    collections = client.get(f"{API}/brand-brain/collections?company_id={company}", headers=headers).json()
    assert collections[0]["title"] == "Serums" and collections[0]["products_count"] == 3


def test_brand_context_is_source_of_truth(client, shopify_env, monkeypatch):
    headers = _login(client, "bb-ctx@example.com")
    company = _company(client, headers, "Primal Penni")
    _bind(company)
    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute",
        _make_fake_execute([_product_node(1, "Copper Glow Serum", "PP-CGS-30", "48.00", ["bestseller"])]),
    )
    client.post(f"{API}/brand-brain/sync?company_id={company}", headers=headers)

    ctx = client.get(f"{API}/brand-brain/context?company_id={company}", headers=headers).json()
    assert ctx["exists"] is True
    assert ctx["source_of_truth"] == "brand_brain"
    assert ctx["store"]["name"] == "Primal Penni"
    assert "Copper Glow Serum" in ctx["brand_brief"]
    assert "bestseller" in ctx["tags"]


def test_context_absent_before_sync_does_not_error(client, shopify_env):
    headers = _login(client, "bb-empty@example.com")
    company = _company(client, headers, "Primal Penni")
    ctx = client.get(f"{API}/brand-brain/context?company_id={company}", headers=headers).json()
    assert ctx["exists"] is False  # graceful — callers fall back


def test_sync_refused_for_non_bound_workspace(client, shopify_env, monkeypatch):
    headers = _login(client, "bb-iso@example.com")
    bound = _company(client, headers, "Primal Penni")
    other = _company(client, headers, "OtherCo")
    _bind(bound)
    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute",
        _make_fake_execute([_product_node(1, "X", "X", "1.00", [])]),
    )
    # Owned company, but not the Shopify-bound workspace → refused (isolation).
    resp = client.post(f"{API}/brand-brain/sync?company_id={other}", headers=headers)
    assert resp.status_code == 422, resp.text
    assert "primal penni workspace" in resp.text.lower()


def test_cannot_read_another_users_brain(client, shopify_env):
    a = _login(client, "bb-owner@example.com")
    b = _login(client, "bb-intruder@example.com")
    company = _company(client, a, "Primal Penni")
    resp = client.get(f"{API}/brand-brain?company_id={company}", headers=b)
    assert resp.status_code == 404, resp.text


def test_resync_mirrors_store_and_prunes(client, shopify_env, monkeypatch):
    headers = _login(client, "bb-prune@example.com")
    company = _company(client, headers, "Primal Penni")
    _bind(company)
    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute",
        _make_fake_execute([
            _product_node(1, "Copper Glow Serum", "PP-CGS-30", "48.00", []),
            _product_node(2, "Renewal Night Cream", "PP-RNC-50", "54.00", []),
        ]),
    )
    client.post(f"{API}/brand-brain/sync?company_id={company}", headers=headers)
    assert len(client.get(f"{API}/brand-brain/products?company_id={company}", headers=headers).json()) == 2

    # Store now has only one product — a re-sync should drop the other.
    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute",
        _make_fake_execute([_product_node(1, "Copper Glow Serum", "PP-CGS-30", "50.00", [])]),
    )
    client.post(f"{API}/brand-brain/sync?company_id={company}", headers=headers)
    products = client.get(f"{API}/brand-brain/products?company_id={company}", headers=headers).json()
    assert len(products) == 1
    assert products[0]["price_min"] == 50.0  # updated price, upserted in place


def test_no_write_routes_on_brand_brain(client, shopify_env):
    headers = _login(client, "bb-verbs@example.com")
    company = _company(client, headers, "Primal Penni")
    # Only GET + POST /sync exist; PUT/PATCH/DELETE must not be routable.
    for verb in ("put", "patch", "delete"):
        r = getattr(client, verb)(f"{API}/brand-brain?company_id={company}", headers=headers)
        assert r.status_code == 405, f"{verb} should be 405, got {r.status_code}"
