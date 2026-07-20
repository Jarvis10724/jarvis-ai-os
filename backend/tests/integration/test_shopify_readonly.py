"""
Coverage for the Phase 1 read-only Shopify integration
(app.core.shopify_service + app.integrations.shopify_admin_client +
api/v1/endpoints/shopify.py).

No live Shopify calls: the GraphQL client is monkeypatched so the tests run
offline and deterministically. What matters here is the framework contract,
not Shopify's data — specifically:
  * not-configured degrades cleanly (no 500),
  * workspace isolation is enforced (a non-bound workspace is refused),
  * when configured+bound, a read runs the query and returns Shopify's data,
  * the admin token never appears in any response body,
  * every route is read-only (GET only).
"""
import pytest

from app.config import settings

API = "/api/v1"

FAKE_TOKEN = "shpat_this_should_never_be_serialized"


def _register_and_login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_company(client, headers: dict, name: str) -> str:
    resp = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


_AUTH_FIELDS = (
    "SHOPIFY_STORE_DOMAIN",
    "SHOPIFY_CLIENT_ID",
    "SHOPIFY_CLIENT_SECRET",
    "SHOPIFY_ADMIN_API_TOKEN",
    "SHOPIFY_WORKSPACE_ID",
)


@pytest.fixture
def unconfigured():
    """Ensure every Shopify auth var is blank (the default), restoring after."""
    saved = {f: getattr(settings, f) for f in _AUTH_FIELDS}
    for f in _AUTH_FIELDS:
        setattr(settings, f, None)
    yield
    for f, v in saved.items():
        setattr(settings, f, v)


def _configure_for(company_id: str):
    """Legacy static-token configuration."""
    settings.SHOPIFY_STORE_DOMAIN = "primal-penni.myshopify.com"
    settings.SHOPIFY_ADMIN_API_TOKEN = FAKE_TOKEN
    settings.SHOPIFY_WORKSPACE_ID = company_id


def _configure_client_credentials(company_id: str):
    """Current Dev-Dashboard configuration (client credentials grant)."""
    settings.SHOPIFY_STORE_DOMAIN = "primal-penni.myshopify.com"
    settings.SHOPIFY_CLIENT_ID = "test-client-id"
    settings.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    settings.SHOPIFY_WORKSPACE_ID = company_id


# --- Not configured -------------------------------------------------------


def test_status_reports_not_configured(client, unconfigured):
    headers = _register_and_login(client, "shopify-status-off@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    resp = client.get(f"{API}/shopify/status?company_id={company}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["configured"] is False
    assert body["store_domain"] is None
    assert body["read_only"] is True


def test_data_endpoint_not_configured_is_clean_error_not_500(client, unconfigured):
    headers = _register_and_login(client, "shopify-data-off@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    resp = client.get(f"{API}/shopify/products?company_id={company}", headers=headers)
    # ValidationError -> 422, never a 500
    assert resp.status_code == 422, resp.text
    assert "not configured" in resp.text.lower()


# --- Configured + workspace isolation ------------------------------------


def test_wrong_workspace_is_refused(client, unconfigured, monkeypatch):
    headers = _register_and_login(client, "shopify-iso@example.com")
    bound = _create_company(client, headers, "PrimalPenni")
    other = _create_company(client, headers, "OtherCo")
    _configure_for(bound)

    # Even though creds are present, a request scoped to a DIFFERENT company
    # must be refused — Shopify data can't leak across workspaces.
    resp = client.get(f"{API}/shopify/products?company_id={other}", headers=headers)
    assert resp.status_code == 422, resp.text
    assert "primal penni workspace" in resp.text.lower()


def test_bound_workspace_runs_query_and_hides_token(client, unconfigured, monkeypatch):
    headers = _register_and_login(client, "shopify-bound@example.com")
    bound = _create_company(client, headers, "PrimalPenni")
    _configure_for(bound)

    captured = {}

    async def fake_execute(self, query, variables=None):
        # Prove the real token would have been used, and that the query is a
        # read (no "mutation" keyword anywhere).
        captured["token"] = await self._access_token()
        captured["query"] = query
        assert "mutation" not in query.lower()
        return {"products": {"edges": [{"node": {"id": "gid://shopify/Product/1", "title": "Flagship Blend"}}]}}

    monkeypatch.setattr(
        "app.integrations.shopify_admin_client.ShopifyAdminClient.execute", fake_execute
    )

    resp = client.get(f"{API}/shopify/products?company_id={bound}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.text
    # Real data came through...
    assert "Flagship Blend" in body
    # ...but the token never appears in the response.
    assert FAKE_TOKEN not in body
    assert captured["token"] == FAKE_TOKEN  # it WAS used server-side


def test_status_bound_flag_tracks_active_workspace(client, unconfigured):
    headers = _register_and_login(client, "shopify-boundflag@example.com")
    bound = _create_company(client, headers, "PrimalPenni")
    other = _create_company(client, headers, "OtherCo")
    _configure_for(bound)

    on = client.get(f"{API}/shopify/status?company_id={bound}", headers=headers).json()
    off = client.get(f"{API}/shopify/status?company_id={other}", headers=headers).json()
    assert on["configured"] is True and on["active_workspace_is_bound"] is True
    assert on["store_domain"] == "primal-penni.myshopify.com"
    assert off["active_workspace_is_bound"] is False
    # Non-secret only — never the token.
    assert FAKE_TOKEN not in str(on) and FAKE_TOKEN not in str(off)


# --- Client credentials grant (current Dev Dashboard method) --------------


def test_client_credentials_configured_status(client, unconfigured):
    headers = _register_and_login(client, "shopify-cc-status@example.com")
    bound = _create_company(client, headers, "PrimalPenni")
    _configure_client_credentials(bound)
    body = client.get(f"{API}/shopify/status?company_id={bound}", headers=headers).json()
    assert body["configured"] is True
    assert body["auth_method"] == "client_credentials"
    # The client secret must never surface in the status payload.
    assert "test-client-secret" not in str(body)


async def test_client_credentials_grant_exchanges_and_caches(unconfigured, monkeypatch):
    """The client resolves a token via the grant, caches it, and reuses it."""
    from app.integrations import shopify_admin_client as mod

    _configure_client_credentials("company-x")
    mod._token_cache.clear()

    calls = {"n": 0}

    async def fake_fetch(self):
        calls["n"] += 1
        return "shpat_exchanged_token", 86399

    monkeypatch.setattr(mod.ShopifyAdminClient, "_fetch_client_credentials_token", fake_fetch)

    c = mod.ShopifyAdminClient()
    t1 = await c._access_token()
    t2 = await c._access_token()
    assert t1 == "shpat_exchanged_token" and t2 == t1
    assert calls["n"] == 1  # cached — the grant ran once, not twice


async def test_static_token_takes_priority_over_client_credentials(unconfigured):
    """A legacy shpat_ token, if present, is used directly (no exchange)."""
    from app.integrations import shopify_admin_client as mod

    _configure_client_credentials("company-y")
    settings.SHOPIFY_ADMIN_API_TOKEN = "shpat_legacy_static"
    assert mod.ShopifyAdminClient.auth_method() == "admin_api_token"
    assert await mod.ShopifyAdminClient()._access_token() == "shpat_legacy_static"


# --- Read-only surface ----------------------------------------------------


def test_all_shopify_routes_are_get_only(client, unconfigured):
    headers = _register_and_login(client, "shopify-readonly@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    # A write verb against any shopify path must not be routable.
    for verb in ("post", "put", "patch", "delete"):
        resp = getattr(client, verb)(f"{API}/shopify/products?company_id={company}", headers=headers)
        assert resp.status_code == 405, f"{verb} on /shopify/products should be 405, got {resp.status_code}"
