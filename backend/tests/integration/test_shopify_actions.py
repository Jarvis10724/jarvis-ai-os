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


# --- The live commit sequence ---------------------------------------------
#
# Shopify is mocked at shopify_service's two doors (run_approved_query for
# reads, run_approved_mutation for writes) so the SEQUENCE can be asserted:
# read live -> refuse if stale -> mutate -> read back -> refuse unless the
# read-back matches. None of these tests touch a real store.


class _FakeStore:
    """A stand-in Shopify that only changes when a mutation tells it to."""

    def __init__(self, **product):
        self.product = {
            "id": "gid://shopify/Product/1",
            "title": "TEST | Draft Product",
            "status": "DRAFT",
            "description": "Old copy",
            "descriptionHtml": "<p>Old copy</p>",
            "totalInventory": 5,
            "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/1", "price": "10.00",
                                    "inventoryItem": {"id": "gid://shopify/InventoryItem/1"}}]},
            **product,
        }
        self.mutations: list[dict] = []
        self.applies = True  # flip to False to simulate a write that doesn't stick

    async def query(self, _db, **kwargs):
        if "locations" in kwargs["query"]:
            return {"locations": {"nodes": [{"id": "gid://shopify/Location/1", "name": "Main"}]}}
        return {"product": self.product}

    async def mutate(self, _db, **kwargs):
        self.mutations.append(kwargs)
        variables = kwargs["variables"]
        if self.applies:
            if "input" in variables and "quantities" in variables["input"]:
                self.product["totalInventory"] = variables["input"]["quantities"][0]["quantity"]
            elif "variants" in variables:
                self.product["variants"]["nodes"][0]["price"] = variables["variants"][0]["price"]
            else:
                item = variables["input"]
                for key, target in (("title", "title"), ("status", "status"), ("descriptionHtml", "descriptionHtml")):
                    if key in item:
                        self.product[target] = item[key]
        return {"productUpdate": {"userErrors": []}, "productVariantsBulkUpdate": {"userErrors": []},
                "inventorySetQuantities": {"userErrors": []}}


def _open_the_gates(monkeypatch):
    monkeypatch.setattr(settings, "SHOPIFY_WRITE_ENABLED", True)
    monkeypatch.setattr(settings, "SHOPIFY_SCOPES", "read_products,read_inventory,write_products,write_inventory")


def _wire(monkeypatch, store):
    monkeypatch.setattr(sw.shopify_service, "run_approved_query", store.query)
    monkeypatch.setattr(sw.shopify_service, "run_approved_mutation", store.mutate)


def _commit(company, action, payload):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return asyncio.get_event_loop().run_until_complete(
            sw.execute(db, owner_id="u", company_id=company, action_type=action, payload=payload)
        )
    finally:
        db.close()


def _setup(client, email, monkeypatch, **product):
    headers = _login(client, email)
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    store = _FakeStore(**product)
    # The synced mirror reflects what the store currently holds — that's what a
    # real sync produces, and the stale check exists to catch it when it doesn't.
    _seed_product(company, title="TEST | Draft Product", inventory=5, price=10.0)
    _mirror(company, store)
    _open_the_gates(monkeypatch)
    _wire(monkeypatch, store)
    return company, store


def _mirror(company_id, store):
    from app.db.models.brand_brain import BrandProduct
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(BrandProduct).filter(BrandProduct.company_id == company_id).first()
        row.status = store.product["status"]
        row.description = store.product["descriptionHtml"]
        db.commit()
    finally:
        db.close()


def _preview_of(company, action, changes):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return sw.build_preview(db, company_id=company, action_type=action, changes=changes)
    finally:
        db.close()


def test_a_committed_change_is_verified_by_reading_it_back(client, monkeypatch):
    company, store = _setup(client, "sw-live-inv@example.com", monkeypatch)
    preview = _preview_of(company, "update_inventory", {"product": "TEST", "quantity": 120})

    result = _commit(company, "update_inventory", {"product": "TEST", "quantity": 120, "_preview": preview})

    assert result["committed"] is True and result["changed"] is True
    assert result["verified"] is True
    assert result["before"] == {"quantity": 5} and result["after"] == {"quantity": 120}
    assert len(store.mutations) == 1  # one approval, one mutation


def test_title_description_and_status_all_commit(client, monkeypatch):
    company, store = _setup(client, "sw-live-product@example.com", monkeypatch)
    preview = _preview_of(
        company, "update_product",
        {"product": "TEST", "title": "TEST | Renamed", "description": "New copy", "status": "active"},
    )
    result = _commit(company, "update_product", {
        "product": "TEST", "title": "TEST | Renamed", "description": "New copy",
        "status": "active", "_preview": preview,
    })
    assert result["verified"] is True
    assert store.product["title"] == "TEST | Renamed"
    assert store.product["status"] == "ACTIVE"


def test_price_commits_through_the_variant(client, monkeypatch):
    company, store = _setup(client, "sw-live-price@example.com", monkeypatch)
    preview = _preview_of(company, "update_price", {"product": "TEST", "price": "42.00"})
    result = _commit(company, "update_price", {"product": "TEST", "price": "42.00", "_preview": preview})
    assert result["verified"] is True
    assert store.product["variants"]["nodes"][0]["price"] == "42.00"


def test_a_write_that_does_not_stick_is_not_marked_completed(client, monkeypatch):
    """The read-back is the proof. Shopify accepting the call is not enough."""
    import pytest

    company, store = _setup(client, "sw-live-nostick@example.com", monkeypatch)
    store.applies = False  # mutation returns success but nothing changes
    preview = _preview_of(company, "update_inventory", {"product": "TEST", "quantity": 120})

    with pytest.raises(ValidationError) as exc:
        _commit(company, "update_inventory", {"product": "TEST", "quantity": 120, "_preview": preview})
    assert "does NOT show the new value" in str(exc.value)
    assert "Not marking this as completed" in str(exc.value)


def test_shopify_user_errors_stop_the_commit(client, monkeypatch):
    import pytest

    company, store = _setup(client, "sw-live-errors@example.com", monkeypatch)

    async def rejecting(_db, **_k):
        return {"productUpdate": {"userErrors": [{"field": "title", "message": "Title is too long"}]}}

    monkeypatch.setattr(sw.shopify_service, "run_approved_mutation", rejecting)
    preview = _preview_of(company, "update_product", {"product": "TEST", "title": "X" * 300})
    with pytest.raises(ValidationError) as exc:
        _commit(company, "update_product", {"product": "TEST", "title": "X" * 300, "_preview": preview})
    assert "Title is too long" in str(exc.value)


def test_a_stale_approval_is_refused(client, monkeypatch):
    """Someone edited the product in Shopify Admin after the preview was built.
    The operator approved a diff that no longer describes reality, so
    committing would silently overwrite a change they never saw."""
    import pytest

    company, store = _setup(client, "sw-live-stale@example.com", monkeypatch)
    preview = _preview_of(company, "update_price", {"product": "TEST", "price": "42.00"})
    assert preview["before"] == 10.0
    store.product["variants"]["nodes"][0]["price"] = "19.99"  # changed in Shopify meanwhile

    with pytest.raises(ValidationError) as exc:
        _commit(company, "update_price", {"product": "TEST", "price": "42.00", "_preview": preview})
    assert "Stale approval" in str(exc.value)
    assert "Nothing was sent to Shopify" in str(exc.value)
    assert store.mutations == []


def test_a_value_that_is_already_correct_sends_no_mutation(client, monkeypatch):
    company, store = _setup(client, "sw-live-noop@example.com", monkeypatch)
    preview = _preview_of(company, "update_inventory", {"product": "TEST", "quantity": 5})
    result = _commit(company, "update_inventory", {"product": "TEST", "quantity": 5, "_preview": preview})
    assert result["changed"] is False and result["verified"] is True
    assert store.mutations == []


def test_an_invalid_status_never_reaches_shopify(client, monkeypatch):
    import pytest

    company, store = _setup(client, "sw-live-badstatus@example.com", monkeypatch)
    preview = _preview_of(company, "update_product", {"product": "TEST", "status": "published"})
    with pytest.raises(ValidationError) as exc:
        _commit(company, "update_product", {"product": "TEST", "status": "published", "_preview": preview})
    assert "isn't a Shopify product status" in str(exc.value)
    assert store.mutations == []


def test_the_commit_is_audited_with_before_after_and_verification(client, monkeypatch):
    from app.db.models.capability import CapabilityAuditLog
    from app.db.session import SessionLocal

    company, _ = _setup(client, "sw-live-audit@example.com", monkeypatch)
    preview = _preview_of(company, "update_inventory", {"product": "TEST", "quantity": 120})
    _commit(company, "update_inventory", {
        "product": "TEST", "quantity": 120, "_preview": preview, "_approval_id": "req-123",
    })

    db = SessionLocal()
    try:
        row = (
            db.query(CapabilityAuditLog)
            .filter(
                CapabilityAuditLog.action == "committed:update_inventory",
                CapabilityAuditLog.company_id == company,
            )
            .first()
        )
    finally:
        db.close()
    assert row is not None
    assert row.approval_request_id == "req-123"
    assert "5" in row.before_json
    assert "120" in row.after_json and "verified" in row.after_json


def test_the_local_catalog_matches_shopify_after_a_commit(client, monkeypatch):
    """Both devices read the mirror, so it has to reflect the verified value —
    otherwise the phone and the desktop would disagree with the store."""
    from app.db.models.brand_brain import BrandProduct
    from app.db.session import SessionLocal

    company, _ = _setup(client, "sw-live-mirror@example.com", monkeypatch)
    preview = _preview_of(company, "update_inventory", {"product": "TEST", "quantity": 120})
    _commit(company, "update_inventory", {"product": "TEST", "quantity": 120, "_preview": preview})

    db = SessionLocal()
    try:
        row = db.query(BrandProduct).filter(BrandProduct.company_id == company).first()
        assert row.total_inventory == 120
    finally:
        db.close()


def test_an_unimplemented_action_still_refuses(client, monkeypatch):
    """Opening the gates must not make every declared action suddenly live."""
    import pytest

    _open_the_gates(monkeypatch)
    with pytest.raises(ValidationError) as exc:
        # write_products IS granted here, so this reaches the implementation
        # gate rather than being stopped earlier by the scope gate.
        _commit(None, "update_seo", {"product": "TEST", "seo_title": "New title"})
    assert "hasn't been implemented yet" in str(exc.value)
