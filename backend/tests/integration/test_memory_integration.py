"""
Broader integration coverage for the scoped memory system, complementing
tests/unit/test_memory_scope.py's classification tests with: cross-user
ownership enforcement on every write/read endpoint (not just search),
full audit-trail lifecycle ordering, and CRUD correctness (linking,
partial updates, 404s after delete).

Same pattern as the rest of the suite — real HTTP calls via TestClient
against a real (test) SQLite database, no mocking needed since embeddings
fall back to a dependency-free local method without OPENAI_API_KEY.
"""
API = "/api/v1"


def _register_and_login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


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


def _audit(client, headers: dict, entry_id: str) -> list[dict]:
    resp = client.get(f"{API}/memory/{entry_id}/audit", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Scope filtering — edge cases beyond the basic single-scope filter
# ---------------------------------------------------------------------------


def test_scope_filter_within_a_specific_company_bucket(client):
    headers = _register_and_login(client, "int-scope-company-bucket@example.com")
    company = _create_company(client, headers, "FilterCo")
    _create_memory(client, headers, kind="fact", title="Company note", content="...", scope="company", company_id=company)
    _create_memory(client, headers, kind="fact", title="Global note", content="...", scope="global")

    # company_id=<company> bucket includes global too (by design) — scope
    # filter should still narrow it down to just the company-scoped one.
    results = _search(client, headers, company_id=company, scope="company")
    assert [r["title"] for r in results] == ["Company note"]


def test_scope_filter_with_empty_query_returns_all_matching_entries(client):
    # Not asserting exact ordering here — SQLite's CURRENT_TIMESTAMP is
    # second-granularity, so two entries created in the same test can tie
    # on created_at and their relative order isn't meaningful to assert on.
    headers = _register_and_login(client, "int-scope-recency@example.com")
    first = _create_memory(client, headers, kind="fact", title="First", content="...", scope="personal")
    second = _create_memory(client, headers, kind="fact", title="Second", content="...", scope="personal")

    results = _search(client, headers, scope="personal")
    ids = {r["id"] for r in results}
    assert {first["id"], second["id"]} <= ids


# ---------------------------------------------------------------------------
# Company/project ownership enforcement (the bug this test file caught:
# company_id previously had no ownership check at all, unlike project_id)
# ---------------------------------------------------------------------------


def test_cannot_create_company_scoped_memory_with_someone_elses_company(client):
    owner_headers = _register_and_login(client, "int-owner-company@example.com")
    other_headers = _register_and_login(client, "int-other-company@example.com")
    owners_company = _create_company(client, owner_headers, "NotYours Inc")

    resp = client.post(
        f"{API}/memory",
        json={
            "kind": "fact", "title": "Sneaky", "content": "...",
            "scope": "company", "company_id": owners_company,
        },
        headers=other_headers,
    )
    assert resp.status_code == 404


def test_cannot_move_memory_to_someone_elses_company(client):
    owner_headers = _register_and_login(client, "int-owner-move@example.com")
    other_headers = _register_and_login(client, "int-other-move@example.com")
    owners_company = _create_company(client, owner_headers, "StillNotYours Inc")

    entry = _create_memory(client, other_headers, kind="fact", title="Movable", content="...", scope="organization")
    resp = client.post(
        f"{API}/memory/{entry['id']}/move",
        json={"scope": "company", "company_id": owners_company},
        headers=other_headers,
    )
    assert resp.status_code == 404
    # And the entry's scope must be unchanged after the rejected move.
    unchanged = client.get(f"{API}/memory/{entry['id']}", headers=other_headers).json()
    assert unchanged["scope"] == "organization"


def test_cannot_create_project_scoped_memory_with_someone_elses_project(client):
    owner_headers = _register_and_login(client, "int-owner-project@example.com")
    other_headers = _register_and_login(client, "int-other-project@example.com")
    owners_project = _create_project(client, owner_headers, "NotYours Project")

    resp = client.post(
        f"{API}/memory",
        json={
            "kind": "fact", "title": "Sneaky project note", "content": "...",
            "scope": "project", "project_id": owners_project,
        },
        headers=other_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cross-user isolation on every direct-access endpoint, not just search
# ---------------------------------------------------------------------------


def test_get_single_entry_isolated_across_users(client):
    a = _register_and_login(client, "int-crud-get-a@example.com")
    b = _register_and_login(client, "int-crud-get-b@example.com")
    entry = _create_memory(client, a, kind="fact", title="A's memory", content="...", scope="global")

    resp = client.get(f"{API}/memory/{entry['id']}", headers=b)
    assert resp.status_code == 404


def test_update_isolated_across_users(client):
    a = _register_and_login(client, "int-crud-update-a@example.com")
    b = _register_and_login(client, "int-crud-update-b@example.com")
    entry = _create_memory(client, a, kind="fact", title="A's memory", content="...", scope="global")

    resp = client.put(f"{API}/memory/{entry['id']}", json={"title": "Hijacked"}, headers=b)
    assert resp.status_code == 404

    still_a = client.get(f"{API}/memory/{entry['id']}", headers=a).json()
    assert still_a["title"] == "A's memory"


def test_delete_isolated_across_users(client):
    a = _register_and_login(client, "int-crud-delete-a@example.com")
    b = _register_and_login(client, "int-crud-delete-b@example.com")
    entry = _create_memory(client, a, kind="fact", title="A's memory", content="...", scope="global")

    resp = client.delete(f"{API}/memory/{entry['id']}", headers=b)
    assert resp.status_code == 404

    still_there = client.get(f"{API}/memory/{entry['id']}", headers=a)
    assert still_there.status_code == 200


def test_audit_log_isolated_across_users(client):
    a = _register_and_login(client, "int-crud-audit-a@example.com")
    b = _register_and_login(client, "int-crud-audit-b@example.com")
    entry = _create_memory(client, a, kind="fact", title="A's memory", content="...", scope="global")

    # Not a 404 by design (audit rows are matched on owner_id + entry_id
    # together, same as everything else) — B simply sees nothing of A's.
    resp = client.get(f"{API}/memory/{entry['id']}/audit", headers=b)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Audit trail / history — full lifecycle ordering and snapshot correctness
# ---------------------------------------------------------------------------


def test_audit_trail_records_full_lifecycle(client):
    # Deliberately checks the causal chain via before/after content rather
    # than asserting a strict row order from created_at — SQLite's
    # CURRENT_TIMESTAMP is only second-precision, so several audit rows
    # written within the same test can tie, making raw timestamp order
    # unreliable to assert on even though the data itself is still correct.
    headers = _register_and_login(client, "int-history-lifecycle@example.com")
    company = _create_company(client, headers, "LifecycleCo")
    entry = _create_memory(client, headers, kind="fact", title="v1", content="...", scope="organization")

    client.put(f"{API}/memory/{entry['id']}", json={"title": "v2"}, headers=headers)
    client.put(f"{API}/memory/{entry['id']}", json={"title": "v3"}, headers=headers)
    client.post(
        f"{API}/memory/{entry['id']}/move",
        json={"scope": "company", "company_id": company},
        headers=headers,
    )
    client.delete(f"{API}/memory/{entry['id']}", headers=headers)

    audit = _audit(client, headers, entry["id"])
    actions = [a["action"] for a in audit]
    assert sorted(actions) == sorted(["created", "updated", "updated", "scope_changed", "deleted"])

    deleted_row = next(a for a in audit if a["action"] == "deleted")
    scope_changed_row = next(a for a in audit if a["action"] == "scope_changed")
    updated_rows = [a for a in audit if a["action"] == "updated"]

    # The chain has to hold together regardless of row order: whatever the
    # move recorded as the new scope is what the delete must have captured
    # as the final state, and both edits' titles must show up somewhere.
    assert scope_changed_row["before"]["scope"] == "organization"
    assert scope_changed_row["after"]["scope"] == "company"
    assert deleted_row["before"]["scope"] == "company"
    assert {r["after"]["title"] for r in updated_rows} == {"v2", "v3"}


def test_audit_before_after_snapshots_reflect_real_change(client):
    headers = _register_and_login(client, "int-history-snapshots@example.com")
    entry = _create_memory(client, headers, kind="fact", title="Before title", content="...", scope="global")

    client.put(f"{API}/memory/{entry['id']}", json={"title": "After title"}, headers=headers)

    audit = _audit(client, headers, entry["id"])
    updated_row = next(a for a in audit if a["action"] == "updated")
    assert updated_row["before"]["title"] == "Before title"
    assert updated_row["after"]["title"] == "After title"


def test_move_audit_note_is_recorded(client):
    headers = _register_and_login(client, "int-history-move-note@example.com")
    entry = _create_memory(client, headers, kind="fact", title="X", content="...", scope="organization")

    client.post(
        f"{API}/memory/{entry['id']}/move",
        json={"scope": "personal", "note": "actually just about me"},
        headers=headers,
    )

    audit = _audit(client, headers, entry["id"])
    move_row = next(a for a in audit if a["action"] == "scope_changed")
    assert "actually just about me" in move_row["note"]
    assert move_row["before"]["scope"] == "organization"
    assert move_row["after"]["scope"] == "personal"


# ---------------------------------------------------------------------------
# CRUD correctness
# ---------------------------------------------------------------------------


def test_linking_two_entries_is_bidirectional(client):
    headers = _register_and_login(client, "int-crud-links@example.com")
    quote = _create_memory(client, headers, kind="quote", title="Supplier quote", content="$4.20/unit", scope="global")
    decision = _create_memory(client, headers, kind="decision", title="Went with supplier", content="...", scope="global")

    resp = client.post(
        f"{API}/memory/{decision['id']}/links",
        json={"to_id": quote["id"], "relation": "based_on"},
        headers=headers,
    )
    assert resp.status_code == 201

    decision_detail = client.get(f"{API}/memory/{decision['id']}", headers=headers).json()
    assert any(link["entry"]["id"] == quote["id"] and link["direction"] == "to" for link in decision_detail["links"])

    quote_detail = client.get(f"{API}/memory/{quote['id']}", headers=headers).json()
    assert any(link["entry"]["id"] == decision["id"] and link["direction"] == "from" for link in quote_detail["links"])


def test_update_only_changes_provided_fields(client):
    headers = _register_and_login(client, "int-crud-partial-update@example.com")
    entry = _create_memory(
        client, headers, kind="fact", title="Original title", content="Original content", scope="global",
        confidence=0.9,
    )

    resp = client.put(f"{API}/memory/{entry['id']}", json={"confidence": 0.4}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == 0.4
    assert body["title"] == "Original title"
    assert body["content"] == "Original content"


def test_update_unknown_kind_falls_back_to_other(client):
    headers = _register_and_login(client, "int-crud-unknown-kind@example.com")
    entry = _create_memory(client, headers, kind="fact", title="X", content="Y", scope="global")

    resp = client.put(f"{API}/memory/{entry['id']}", json={"kind": "not_a_real_kind"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["kind"] == "other"


def test_get_after_delete_returns_404(client):
    headers = _register_and_login(client, "int-crud-get-after-delete@example.com")
    entry = _create_memory(client, headers, kind="fact", title="Ephemeral", content="...", scope="global")

    client.delete(f"{API}/memory/{entry['id']}", headers=headers)
    resp = client.get(f"{API}/memory/{entry['id']}", headers=headers)
    assert resp.status_code == 404
