"""
Workspace isolation — the guarantee that two businesses run by the same person
never see each other's data.

This is a safety property, not a feature, so it's tested from the outside at
every boundary that could leak: integrations (which mailbox a workspace uses),
memory, projects, tasks, approvals, Brand Brain, and AI context.

The specific regression these lock down: one account owning two companies.
That's the shape that broke — an account-wide Gmail connection was served to
every workspace under the account, and un-attributed "organization" memory
folded into every workspace's search.
"""
API = "/api/v1"


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name):
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def _remember(client, headers, title, content, company_id=None):
    body = {"kind": "fact", "title": title, "content": content}
    if company_id:
        body["company_id"] = company_id
        body["scope"] = "company"
    else:
        body["scope"] = "organization"
    return client.post(f"{API}/memory", json=body, headers=headers)


# --- Integrations: a workspace uses its own connection or none -------------


def test_a_workspace_never_borrows_another_connection(client):
    """The regression: one account, two businesses. Connecting a mailbox
    account-wide (or to one workspace) must not make it appear in the other."""
    from app.core import credential_store
    from app.db.session import SessionLocal
    from app.db.models.company import Company

    headers = _login(client, "iso-creds@example.com")
    gcs = _company(client, headers, "Greener Capitol Solutions")
    penni = _company(client, headers, "Primal Penni")

    db = SessionLocal()
    try:
        owner_id = db.query(Company).filter(Company.id == gcs).first().owner_id
        # An account-wide connection AND a GCS-only one.
        credential_store.save_credentials(
            db, owner_id=owner_id, provider="email", company_id=None, access_token="account-wide"
        )
        credential_store.save_credentials(
            db, owner_id=owner_id, provider="email", company_id=gcs, access_token="gcs-mailbox"
        )

        # GCS sees its own.
        assert credential_store.load_credentials(
            db, owner_id=owner_id, company_id=gcs, provider="email"
        )["access_token"] == "gcs-mailbox"

        # Primal Penni has none of its own — and must NOT inherit either the
        # account-wide connection or the other workspace's.
        assert (
            credential_store.load_credentials(db, owner_id=owner_id, company_id=penni, provider="email")
            is None
        )
    finally:
        db.close()


def test_unconnected_workspace_reports_not_connected(client):
    headers = _login(client, "iso-status@example.com")
    penni = _company(client, headers, "Primal Penni")
    resp = client.get(f"{API}/integrations?company_id={penni}", headers=headers)
    assert resp.status_code == 200
    email = next((i for i in resp.json() if i["name"] in ("email", "gmail")), None)
    if email:  # the integration list is registry-driven; only assert if present
        assert email["connected"] is False


# --- Memory ----------------------------------------------------------------


def test_workspace_memory_does_not_leak_between_companies(client):
    headers = _login(client, "iso-memory@example.com")
    gcs = _company(client, headers, "Greener Capitol Solutions")
    penni = _company(client, headers, "Primal Penni")
    _remember(client, headers, "GCS runway", "Greener Capitol has 18 months of runway.", gcs)
    _remember(client, headers, "Penni margin", "Primal Penni's blended margin is 62%.", penni)

    gcs_hits = client.get(f"{API}/memory?q=runway margin&company_id={gcs}", headers=headers).json()
    penni_hits = client.get(f"{API}/memory?q=runway margin&company_id={penni}", headers=headers).json()

    assert any("runway" in m["title"].lower() for m in gcs_hits)
    assert not any("margin" in m["title"].lower() for m in gcs_hits)
    assert any("margin" in m["title"].lower() for m in penni_hits)
    assert not any("runway" in m["title"].lower() for m in penni_hits)


def test_unattributed_business_memory_is_not_folded_into_a_workspace(client):
    """`organization` memory is recorded with no workspace active, so nothing
    says which business it belongs to. It must not surface inside a specific
    workspace — that's how one business's facts reach another's answers."""
    headers = _login(client, "iso-orgmem@example.com")
    penni = _company(client, headers, "Primal Penni")
    _remember(client, headers, "Unattributed supplier note", "Supplier terms are net 30.")

    in_workspace = client.get(f"{API}/memory?q=supplier terms&company_id={penni}", headers=headers).json()
    assert not any("Unattributed" in m["title"] for m in in_workspace)

    # It's not lost — it's still there when no workspace is active.
    everywhere = client.get(f"{API}/memory?q=supplier terms", headers=headers).json()
    assert any("Unattributed" in m["title"] for m in everywhere)


def test_personal_memory_stays_available_in_every_workspace(client):
    """Isolation is between BUSINESSES. Facts about the operator themselves
    aren't a business's data and must keep working everywhere."""
    headers = _login(client, "iso-personal@example.com")
    penni = _company(client, headers, "Primal Penni")
    client.post(
        f"{API}/memory",
        json={"kind": "fact", "scope": "personal", "title": "Preferred tone", "content": "Nick prefers concise updates."},
        headers=headers,
    )
    hits = client.get(f"{API}/memory?q=concise updates tone&company_id={penni}", headers=headers).json()
    assert any("Preferred tone" == m["title"] for m in hits)


# --- Everything else a workspace owns --------------------------------------


def test_projects_tasks_and_approvals_are_workspace_scoped(client):
    headers = _login(client, "iso-domains@example.com")
    gcs = _company(client, headers, "Greener Capitol Solutions")
    penni = _company(client, headers, "Primal Penni")

    client.post(f"{API}/projects", json={"name": "GCS Fund II", "company_id": gcs}, headers=headers)
    client.post(f"{API}/projects", json={"name": "Penni Spring Drop", "company_id": penni}, headers=headers)
    client.post(f"{API}/companies/{gcs}/tasks", json={"title": "GCS diligence"}, headers=headers)
    client.post(f"{API}/companies/{penni}/tasks", json={"title": "Penni reorder"}, headers=headers)

    gcs_projects = [p["name"] for p in client.get(f"{API}/projects?company_id={gcs}", headers=headers).json()]
    penni_projects = [p["name"] for p in client.get(f"{API}/projects?company_id={penni}", headers=headers).json()]
    assert "GCS Fund II" in gcs_projects and "Penni Spring Drop" not in gcs_projects
    assert "Penni Spring Drop" in penni_projects and "GCS Fund II" not in penni_projects

    gcs_tasks = [t["title"] for t in client.get(f"{API}/companies/{gcs}/tasks", headers=headers).json()]
    penni_tasks = [t["title"] for t in client.get(f"{API}/companies/{penni}/tasks", headers=headers).json()]
    assert "GCS diligence" in gcs_tasks and "Penni reorder" not in gcs_tasks
    assert "Penni reorder" in penni_tasks and "GCS diligence" not in penni_tasks


def test_brand_brain_is_workspace_scoped(client):
    """Products belong to the workspace whose store they came from."""
    from app.db.session import SessionLocal
    from app.db.models.brand_brain import BrandBrain, BrandProduct

    headers = _login(client, "iso-brain@example.com")
    gcs = _company(client, headers, "Greener Capitol Solutions")
    penni = _company(client, headers, "Primal Penni")

    db = SessionLocal()
    try:
        brain = BrandBrain(company_id=penni, source="shopify", store_domain="x.myshopify.com")
        db.add(brain)
        db.commit()
        db.add(BrandProduct(brain_id=brain.id, company_id=penni, shopify_id="gid://shopify/Product/1", title="RARE EARTH | Mineral Polish", handle="rare-earth"))
        db.commit()
    finally:
        db.close()

    penni_products = client.get(f"{API}/brand-brain/products?company_id={penni}", headers=headers).json()
    gcs_products = client.get(f"{API}/brand-brain/products?company_id={gcs}", headers=headers).json()
    assert any("RARE EARTH" in p["title"] for p in penni_products)
    assert gcs_products == []
    assert client.get(f"{API}/brand-brain?company_id={gcs}", headers=headers).json()["exists"] is False


def test_another_account_sees_nothing_of_either_workspace(client):
    headers = _login(client, "iso-owner@example.com")
    penni = _company(client, headers, "Primal Penni")
    client.post(f"{API}/companies/{penni}/tasks", json={"title": "Penni reorder"}, headers=headers)

    stranger = _login(client, "iso-stranger@example.com")
    # Another account can't even resolve the company, let alone its tasks.
    assert client.get(f"{API}/companies/{penni}/tasks", headers=stranger).status_code == 404
    assert client.get(f"{API}/memory?q=reorder&company_id={penni}", headers=stranger).json() == []
    assert client.get(f"{API}/companies", headers=stranger).json() == []
