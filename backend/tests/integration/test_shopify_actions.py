"""
The Shopify action layer: preview a storefront change, approve it, and only
then — if writing is deliberately enabled and the scope was granted — commit.

What matters here is what must NOT happen: a change reaching the live store
without an approval, without the kill-switch on, or without the OAuth scope the
action needs. Each of those is asserted directly.
"""
import asyncio

from app.config import settings
from app.core import shopify_write_service as sw
from app.exceptions import ValidationError

API = "/api/v1"


def _seed_product(company_id: str, *, title="RARE EARTH | Mineral Polish", inventory=0, price=29.0):
    from app.db.models.brand_brain import BrandBrain, BrandProduct
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        brain = BrandBrain(company_id=company_id, source="shopify", store_domain="x.myshopify.com")
        db.add(brain)
        db.commit()
        db.add(
            BrandProduct(
                brain_id=brain.id, company_id=company_id, shopify_id="gid://shopify/Product/1",
                title=title, handle="rare-earth-mineral-polish", status="ACTIVE",
                price_min=price, currency="USD", total_inventory=inventory,
            )
        )
        db.commit()
    finally:
        db.close()


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Preview --------------------------------------------------------------


def test_preview_shows_current_value_against_proposed(client):
    from app.db.session import SessionLocal

    headers = _login(client, "sw-preview@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    _seed_product(company, inventory=0)

    db = SessionLocal()
    try:
        preview = sw.build_preview(
            db, company_id=company, action_type="update_inventory",
            changes={"product": "RARE EARTH", "quantity": 120},
        )
    finally:
        db.close()

    assert preview["resolved"] is True
    assert preview["before"] == 0 and preview["after"] == 120
    assert "0" in sw.describe_preview(preview) and "120" in sw.describe_preview(preview)
    # The operator is told the store won't actually change yet.
    assert any("disabled" in w for w in preview["warnings"])


def test_preview_does_not_pretend_when_the_product_is_unknown(client):
    from app.db.session import SessionLocal

    headers = _login(client, "sw-unknown@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    _seed_product(company)

    db = SessionLocal()
    try:
        preview = sw.build_preview(
            db, company_id=company, action_type="update_price",
            changes={"product": "Copper Glow Serum", "price": "31.00"},
        )
    finally:
        db.close()

    assert preview["resolved"] is False
    assert preview["before"] is None
    assert any("No product matching" in w for w in preview["warnings"])
    assert "Could not resolve" in sw.describe_preview(preview)


def test_preview_flags_a_no_op(client):
    from app.db.session import SessionLocal

    headers = _login(client, "sw-noop@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    _seed_product(company, inventory=42)

    db = SessionLocal()
    try:
        preview = sw.build_preview(
            db, company_id=company, action_type="update_inventory",
            changes={"product": "RARE EARTH", "quantity": 42},
        )
    finally:
        db.close()
    assert any("change nothing" in w for w in preview["warnings"])


# --- The commit gates -----------------------------------------------------


def test_commit_refuses_while_writes_are_disabled(client):
    """The kill-switch is the outer gate: approving must not reach Shopify.

    It RAISES rather than returning, because capability_executors marks a
    request 'executed' whenever the executor returns — a refusal that returned
    quietly would leave the request claiming an execution that never happened.
    """
    import pytest

    assert settings.SHOPIFY_WRITE_ENABLED is False
    with pytest.raises(ValidationError) as exc:
        asyncio.get_event_loop().run_until_complete(
            sw.execute(None, owner_id="u", company_id="c", action_type="update_inventory",
                       payload={"product": "RARE EARTH", "quantity": 120})
        )
    assert "Nothing was sent to Shopify" in str(exc.value)


def test_commit_refuses_when_the_scope_was_never_granted(client, monkeypatch):
    """Even with the kill-switch off, an action whose OAuth scope the app
    doesn't hold can't be committed — this app is read-only in Shopify."""
    import pytest

    monkeypatch.setattr(settings, "SHOPIFY_WRITE_ENABLED", True)
    monkeypatch.setattr(settings, "SHOPIFY_SCOPES", "read_products,read_inventory")
    with pytest.raises(ValidationError) as exc:
        asyncio.get_event_loop().run_until_complete(
            sw.execute(None, owner_id="u", company_id="c", action_type="update_price",
                       payload={"product": "RARE EARTH", "price": "31.00"})
        )
    assert "write_products" in str(exc.value)
    assert "Nothing was sent to Shopify" not in str(exc.value)  # different refusal, different reason


def test_every_write_action_declares_the_scope_it_needs():
    """A write with no declared scope would slip past the scope gate."""
    from app.core.capabilities_registry import get_capability

    for action in get_capability("shopify").actions:
        if action.requires_approval:
            assert action.name in sw.REQUIRED_SCOPES, f"{action.name} has no required scope"


def test_the_executor_is_reachable_only_through_an_approval():
    """It's registered as the shopify executor, which capability_executors only
    invokes after approve_action — there is no other caller."""
    from app.core.capability_executors import _EXECUTORS

    assert _EXECUTORS.get("shopify") is sw.execute


# --- End to end through the tool ------------------------------------------


async def _run_tool(client, headers, **kwargs):
    from app.core.agent_tools import TOOL_REGISTRY
    from app.db.models.user import User
    from app.db.session import SessionLocal

    me = client.get(f"{API}/auth/me", headers=headers).json()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == me["id"]).first()
        return await TOOL_REGISTRY["propose_store_change"].handler(user, db, **kwargs)
    finally:
        db.close()


def test_proposing_a_change_attaches_the_preview_to_the_approval(client):
    headers = _login(client, "sw-e2e@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    _seed_product(company, inventory=0)
    client.put(
        f"{API}/capabilities/shopify/config",
        json={"enabled": True, "permissions": ["update_inventory"], "company_id": company},
        headers=headers,
    )

    out = asyncio.get_event_loop().run_until_complete(
        _run_tool(client, headers, company_id=company, change_type="inventory",
                  changes={"product": "RARE EARTH | Mineral Polish", "quantity": 120},
                  reason="Spring order landed")
    )
    assert "your approval" in out.lower()

    step = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["standalone"][0]
    assert step["status"] == "pending"
    # The preview travels with the request, so the reviewer sees before -> after.
    assert step["payload"]["_preview"]["before"] == 0
    assert step["payload"]["_preview"]["after"] == 120
    assert "0" in step["expected_outcome"] and "120" in step["expected_outcome"]
