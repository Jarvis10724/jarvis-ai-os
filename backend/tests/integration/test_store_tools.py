"""
Store tools — running the Shopify store by voice or chat from a phone.

The AI's prompt only ever carried a one-line summary per product, which can't
answer "how much RARE EARTH is left" or "what's in the POLISH collection".
These tools read the synced Brand Brain directly, so the same question works
typed or spoken, on a phone, through the one routing pipeline.

Read-only by construction: nothing here can change the store.
"""
import json

from app.core.agent_tools import TOOL_REGISTRY

API = "/api/v1"


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name="Primal Penni"):
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def _seed_store(company_id):
    """A synced store: two products, one collection, real-shaped variants."""
    from app.db.session import SessionLocal
    from app.db.models.brand_brain import BrandBrain, BrandCollection, BrandProduct

    db = SessionLocal()
    try:
        brain = BrandBrain(
            company_id=company_id,
            source="shopify",
            store_name="PRIMAL PENNI",
            store_domain="0a0pc0-sj.myshopify.com",
            currency="USD",
            product_count=2,
            collection_count=1,
        )
        db.add(brain)
        db.commit()
        db.add_all(
            [
                BrandProduct(
                    brain_id=brain.id,
                    company_id=company_id,
                    shopify_id="gid://shopify/Product/1",
                    title="RARE EARTH | Mineral Polish",
                    handle="rare-earth-mineral-polish",
                    status="ACTIVE",
                    product_type="Polish",
                    price_min=29.0,
                    price_max=29.0,
                    currency="USD",
                    total_inventory=42,
                    tags_json=json.dumps(["polish", "mineral"]),
                    variants_json=json.dumps(
                        [{"title": "4 oz", "sku": "RE-4OZ", "price": "29.00", "inventoryQuantity": 42}]
                    ),
                    description="A mineral polish.",
                ),
                BrandProduct(
                    brain_id=brain.id,
                    company_id=company_id,
                    shopify_id="gid://shopify/Product/2",
                    title="BARE RITUAL | Cleansing Oil",
                    handle="bare-ritual-cleansing-oil",
                    status="ACTIVE",
                    price_min=38.0,
                    currency="USD",
                    total_inventory=7,
                    tags_json=json.dumps(["cleanse"]),
                ),
                BrandCollection(
                    brain_id=brain.id,
                    company_id=company_id,
                    shopify_id="gid://shopify/Collection/1",
                    title="POLISH",
                    handle="polish",
                    products_count=1,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


async def _run(tool_name, client, headers, **kwargs):
    """Invoke a tool the way the chat pipeline does."""
    from app.db.session import SessionLocal
    from app.db.models.user import User

    me = client.get(f"{API}/auth/me", headers=headers).json()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == me["id"]).first()
        return await TOOL_REGISTRY[tool_name].handler(user, db, **kwargs)
    finally:
        db.close()


async def test_catalog_reports_real_stock_and_prices(client):
    headers = _login(client, "store-catalog@example.com")
    company = _company(client, headers)
    _seed_store(company)

    out = await _run("store_catalog", client, headers, company_id=company)
    assert "RARE EARTH | Mineral Polish" in out
    assert "29.00" in out and "inventory=42" in out
    assert "BARE RITUAL" in out and "inventory=7" in out


async def test_catalog_can_be_filtered(client):
    headers = _login(client, "store-filter@example.com")
    company = _company(client, headers)
    _seed_store(company)

    out = await _run("store_catalog", client, headers, company_id=company, query="polish")
    assert "RARE EARTH" in out
    assert "BARE RITUAL" not in out

    missing = await _run("store_catalog", client, headers, company_id=company, query="copper glow")
    assert "No products" in missing


async def test_product_detail_includes_variants_and_stock(client):
    headers = _login(client, "store-product@example.com")
    company = _company(client, headers)
    _seed_store(company)

    out = await _run("store_product", client, headers, company_id=company, name="RARE EARTH")
    assert "rare-earth-mineral-polish" in out
    assert "RE-4OZ" in out and "inventoryQuantity" not in out  # rendered, not raw JSON
    assert "42" in out

    missing = await _run("store_product", client, headers, company_id=company, name="Copper Glow Serum")
    assert "No product named" in missing


async def test_collections_are_listed(client):
    headers = _login(client, "store-collections@example.com")
    company = _company(client, headers)
    _seed_store(company)
    out = await _run("store_collections", client, headers, company_id=company)
    assert "POLISH" in out and "1 products" in out


async def test_unsynced_workspace_says_so_instead_of_guessing(client):
    headers = _login(client, "store-empty@example.com")
    company = _company(client, headers)
    out = await _run("store_catalog", client, headers, company_id=company)
    assert "no synced store catalog" in out.lower()


async def test_store_tools_are_workspace_scoped(client):
    """A store belongs to one workspace; another account can't read it."""
    headers = _login(client, "store-owner@example.com")
    company = _company(client, headers)
    _seed_store(company)

    stranger = _login(client, "store-stranger@example.com")
    from app.exceptions import NotFoundError

    try:
        await _run("store_catalog", client, stranger, company_id=company)
        raise AssertionError("another account read this workspace's store")
    except NotFoundError:
        pass


def test_store_tools_are_registered_as_company_scoped(client):
    """The active workspace decides which store — never the model."""
    from app.api.v1.endpoints.chat import _COMPANY_SCOPED_TOOLS

    assert {"store_catalog", "store_product", "store_collections", "sync_store"} <= _COMPANY_SCOPED_TOOLS
