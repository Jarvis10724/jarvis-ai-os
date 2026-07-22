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


# --- Preparing storefront changes (approval-gated) -------------------------


def _grant_shopify_writes(client, headers, company_id, actions):
    return client.put(
        f"{API}/capabilities/shopify/config",
        json={"enabled": True, "permissions": actions, "company_id": company_id},
        headers=headers,
    )


async def test_preparing_a_store_change_creates_an_approval_and_changes_nothing(client):
    headers = _login(client, "store-write@example.com")
    company = _company(client, headers)
    _seed_store(company)
    _grant_shopify_writes(client, headers, company, ["update_inventory"])

    out = await _run(
        "propose_store_change",
        client,
        headers,
        company_id=company,
        change_type="inventory",
        changes={"product": "RARE EARTH | Mineral Polish", "quantity": 120},
        reason="Restocking after the spring order landed.",
    )
    assert "your approval" in out.lower()
    assert "nothing has changed" in out.lower()

    queue = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()
    step = queue["standalone"][0]
    assert step["capability_name"] == "shopify" and step["action_type"] == "update_inventory"
    assert step["status"] == "pending"
    assert "120" in step["summary"]
    assert "Restocking" in (step["reason"] or "")
    # The brief must not imply the store is about to change.
    outcome = step["expected_outcome"].lower()
    assert "nothing is pushed to shopify" in outcome   # the standing guarantee
    assert "→" in step["expected_outcome"] or "->" in outcome  # plus the before→after preview

    # The catalog is untouched — the proposal is a request, not a write.
    assert "inventory=42" in await _run("store_catalog", client, headers, company_id=company)


async def test_every_storefront_change_type_is_approval_gated(client):
    """No storefront write may bypass the gate, and none may execute itself."""
    from app.core.capabilities_registry import get_capability
    from app.core.capability_executors import _EXECUTORS
    from app.core.agent_tools import _STORE_CHANGES

    shopify = get_capability("shopify")
    for action in _STORE_CHANGES.values():
        assert shopify.action(action).requires_approval, f"{action} is not approval-gated"
    # There IS a shopify executor now (the action layer), but it cannot publish
    # by itself: with the kill-switch off it refuses instead of writing, and the
    # request is left 'approved' rather than marked executed.
    assert "shopify" in _EXECUTORS
    from app.config import settings
    assert settings.SHOPIFY_WRITE_ENABLED is False


async def test_a_write_the_workspace_hasnt_been_granted_is_refused(client):
    headers = _login(client, "store-nogrant@example.com")
    company = _company(client, headers)
    _seed_store(company)
    # No permission granted for update_price.
    out = await _run(
        "propose_store_change",
        client,
        headers,
        company_id=company,
        change_type="price",
        changes={"product": "RARE EARTH | Mineral Polish", "price": "31.00"},
    )
    assert "couldn't prepare" in out.lower()
    assert client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["pending_count"] == 0


async def test_unknown_change_type_is_refused_not_guessed(client):
    headers = _login(client, "store-badtype@example.com")
    company = _company(client, headers)
    out = await _run(
        "propose_store_change", client, headers, company_id=company, change_type="teleport", changes={"x": 1}
    )
    assert "Unknown change type" in out
