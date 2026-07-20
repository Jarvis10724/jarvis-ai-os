"""
Automated coverage for the scoped memory system: classification into the
five scopes (global/organization/company/project/personal), scope-based
search filtering, tenant isolation between companies (and between users),
and the edit/move/delete controls + their audit trail.

These hit the real HTTP API against a real (test) SQLite database via
FastAPI's TestClient, the same pattern test_auth_flow.py already uses — no
mocking of the AI provider is needed because embeddings fall back to the
dependency-free local hashing method whenever OPENAI_API_KEY isn't set
(see app.core.embeddings), which is always true in this test environment.
"""
API = "/api/v1"


def _register_and_login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_company(client, headers: dict, name: str) -> str:
    resp = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_project(client, headers: dict, name: str) -> str:
    resp = client.post(f"{API}/projects", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_memory(client, headers: dict, **kwargs) -> dict:
    resp = client.post(f"{API}/memory", json=kwargs, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _search(client, headers: dict, **params) -> list[dict]:
    resp = client.get(f"{API}/memory", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Classification into the five scopes
# ---------------------------------------------------------------------------


def test_create_one_memory_in_each_scope(client):
    headers = _register_and_login(client, "scopes-all@example.com")
    company_id = _create_company(client, headers, "Primal Penni Collective")
    project_id = _create_project(client, headers, "Website rebuild")

    global_entry = _create_memory(
        client, headers, kind="fact", title="Global fact", content="applies everywhere", scope="global"
    )
    assert global_entry["scope"] == "global"
    assert global_entry["company_id"] is None
    assert global_entry["project_id"] is None

    personal_entry = _create_memory(
        client, headers, kind="fact", title="Personal fact", content="about the user", scope="personal"
    )
    assert personal_entry["scope"] == "personal"
    assert personal_entry["company_id"] is None

    org_entry = _create_memory(
        client, headers, kind="fact", title="Org fact", content="portfolio-wide practice", scope="organization"
    )
    assert org_entry["scope"] == "organization"
    assert org_entry["company_id"] is None

    company_entry = _create_memory(
        client,
        headers,
        kind="fact",
        title="Company fact",
        content="specific to one business",
        scope="company",
        company_id=company_id,
    )
    assert company_entry["scope"] == "company"
    assert company_entry["company_id"] == company_id
    assert company_entry["project_id"] is None

    project_entry = _create_memory(
        client,
        headers,
        kind="fact",
        title="Project fact",
        content="specific to one initiative",
        scope="project",
        project_id=project_id,
    )
    assert project_entry["scope"] == "project"
    assert project_entry["project_id"] == project_id


def test_company_scope_requires_company_id(client):
    headers = _register_and_login(client, "scope-needs-company@example.com")
    resp = client.post(
        f"{API}/memory",
        json={"kind": "fact", "title": "x", "content": "y", "scope": "company"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_project_scope_requires_project_id(client):
    headers = _register_and_login(client, "scope-needs-project@example.com")
    resp = client.post(
        f"{API}/memory",
        json={"kind": "fact", "title": "x", "content": "y", "scope": "project"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_scope_defaults_when_omitted(client):
    headers = _register_and_login(client, "scope-defaults@example.com")
    company_id = _create_company(client, headers, "DefaultCo")

    with_company = _create_memory(client, headers, kind="fact", title="x", content="y", company_id=company_id)
    assert with_company["scope"] == "company"

    without_company = _create_memory(client, headers, kind="fact", title="x2", content="y2")
    assert without_company["scope"] == "organization"


def test_global_scope_ignores_an_inapplicable_company_id(client):
    # Mirrors chat.py auto-filling a default company_id onto a tool call the
    # model separately classified as global — the extra field should be
    # dropped, not rejected.
    headers = _register_and_login(client, "scope-global-ignore@example.com")
    company_id = _create_company(client, headers, "IgnoredCo")

    entry = _create_memory(
        client, headers, kind="fact", title="x", content="y", scope="global", company_id=company_id
    )
    assert entry["scope"] == "global"
    assert entry["company_id"] is None


# ---------------------------------------------------------------------------
# Scope-based search filtering
# ---------------------------------------------------------------------------


def test_scope_filter_returns_only_that_scope(client):
    headers = _register_and_login(client, "scope-filter@example.com")
    _create_memory(client, headers, kind="fact", title="G1", content="...", scope="global")
    _create_memory(client, headers, kind="fact", title="P1", content="...", scope="personal")
    _create_memory(client, headers, kind="fact", title="O1", content="...", scope="organization")

    results = _search(client, headers, scope="personal")
    assert [r["title"] for r in results] == ["P1"]
    assert all(r["scope"] == "personal" for r in results)


def test_scope_filter_combines_with_kind_filter(client):
    headers = _register_and_login(client, "scope-kind-combo@example.com")
    _create_memory(client, headers, kind="decision", title="D1", content="...", scope="global")
    _create_memory(client, headers, kind="fact", title="F1", content="...", scope="global")

    results = _search(client, headers, scope="global", kind="decision")
    assert [r["title"] for r in results] == ["D1"]


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_company_memory_isolated_between_companies(client):
    headers = _register_and_login(client, "isolation-companies@example.com")
    primal = _create_company(client, headers, "Primal Penni Collective")
    greener = _create_company(client, headers, "Greener Capitol Solutions LLC")

    _create_memory(
        client, headers, kind="fact", title="Primal secret", content="only for primal",
        scope="company", company_id=primal,
    )
    _create_memory(
        client, headers, kind="fact", title="Greener secret", content="only for greener",
        scope="company", company_id=greener,
    )

    greener_view = [r["title"] for r in _search(client, headers, company_id=greener)]
    assert "Greener secret" in greener_view
    assert "Primal secret" not in greener_view

    primal_view = [r["title"] for r in _search(client, headers, company_id=primal)]
    assert "Primal secret" in primal_view
    assert "Greener secret" not in primal_view

    # Only the portfolio/"any" (all-companies) level shows both.
    portfolio_view = [r["title"] for r in _search(client, headers, company_id="any")]
    assert "Primal secret" in portfolio_view
    assert "Greener secret" in portfolio_view


def test_global_memory_visible_from_every_company(client):
    headers = _register_and_login(client, "isolation-global-visible@example.com")
    primal = _create_company(client, headers, "Primal Penni Collective")
    greener = _create_company(client, headers, "Greener Capitol Solutions LLC")
    _create_memory(client, headers, kind="fact", title="Cross-company fact", content="...", scope="global")

    for company_id in (primal, greener):
        view = [r["title"] for r in _search(client, headers, company_id=company_id)]
        assert "Cross-company fact" in view


def test_cross_user_isolation(client):
    headers_a = _register_and_login(client, "tenant-user-a@example.com")
    headers_b = _register_and_login(client, "tenant-user-b@example.com")

    _create_memory(client, headers_a, kind="fact", title="User A secret", content="...", scope="global")

    view_b = [r["title"] for r in _search(client, headers_b, company_id="any")]
    assert "User A secret" not in view_b


# ---------------------------------------------------------------------------
# Edit, move-scope, delete + audit trail
# ---------------------------------------------------------------------------


def test_update_edits_content_and_writes_audit(client):
    headers = _register_and_login(client, "controls-edit@example.com")
    entry = _create_memory(client, headers, kind="fact", title="Original", content="original content", scope="global")

    resp = client.put(f"{API}/memory/{entry['id']}", json={"title": "Updated title"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"

    audit = client.get(f"{API}/memory/{entry['id']}/audit", headers=headers).json()
    actions = [a["action"] for a in audit]
    assert "created" in actions
    assert "updated" in actions


def test_update_never_changes_scope(client):
    headers = _register_and_login(client, "controls-edit-no-scope-change@example.com")
    entry = _create_memory(client, headers, kind="fact", title="X", content="Y", scope="personal")

    # PUT /memory/{id} has no scope field at all — confirm it's simply not
    # accepted, so scope can only change through the dedicated move action.
    resp = client.put(f"{API}/memory/{entry['id']}", json={"title": "X2", "scope": "global"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["scope"] == "personal"


def test_move_scope_changes_company_and_writes_audit(client):
    headers = _register_and_login(client, "controls-move@example.com")
    company_id = _create_company(client, headers, "MoveCo")
    entry = _create_memory(client, headers, kind="fact", title="Movable", content="...", scope="organization")

    resp = client.post(
        f"{API}/memory/{entry['id']}/move",
        json={"scope": "company", "company_id": company_id, "note": "actually about MoveCo"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "company"
    assert body["company_id"] == company_id

    audit = client.get(f"{API}/memory/{entry['id']}/audit", headers=headers).json()
    move_rows = [a for a in audit if a["action"] == "scope_changed"]
    assert len(move_rows) == 1
    assert "MoveCo" in (move_rows[0]["note"] or "") or "organization" in (move_rows[0]["note"] or "")


def test_move_scope_validates_required_fields(client):
    headers = _register_and_login(client, "controls-move-invalid@example.com")
    entry = _create_memory(client, headers, kind="fact", title="X", content="...", scope="organization")
    resp = client.post(f"{API}/memory/{entry['id']}/move", json={"scope": "company"}, headers=headers)
    assert resp.status_code == 422


def test_delete_removes_entry_but_keeps_audit_trail(client):
    headers = _register_and_login(client, "controls-delete@example.com")
    entry = _create_memory(client, headers, kind="fact", title="Ephemeral", content="...", scope="global")

    resp = client.delete(f"{API}/memory/{entry['id']}", headers=headers)
    assert resp.status_code == 204

    remaining = [r["title"] for r in _search(client, headers, company_id="any")]
    assert "Ephemeral" not in remaining

    # The audit trail survives the entry itself being gone.
    audit = client.get(f"{API}/memory/{entry['id']}/audit", headers=headers).json()
    actions = [a["action"] for a in audit]
    assert "created" in actions
    assert "deleted" in actions


def test_confidence_round_trips(client):
    headers = _register_and_login(client, "controls-confidence@example.com")
    entry = _create_memory(
        client, headers, kind="fact", title="Low confidence guess", content="...", scope="organization",
        confidence=0.35,
    )
    assert entry["confidence"] == 0.35

    fetched = client.get(f"{API}/memory/{entry['id']}", headers=headers).json()
    assert fetched["confidence"] == 0.35
