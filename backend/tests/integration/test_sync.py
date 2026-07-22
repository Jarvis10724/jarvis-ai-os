"""
ONE Jarvis — every client is a window onto the same backend state.

These tests are about the GUARANTEE, not the plumbing: that a write cannot
reach the database without every connected client being told, including writes
made by code that predates the sync layer and by features that don't exist yet.
That is why the listener lives on the Session rather than in each service — a
hand-wired call is one someone can forget, and a forgotten one fails silently.
"""
import asyncio

from app.core import sync_service

API = "/api/v1"


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _events(owner_id):
    """Subscribe the way a connected client does, and drain what it received."""
    queue = sync_service.subscribe(owner_id)
    return queue


def _drain(queue):
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


def test_a_write_announces_itself_without_any_service_wiring(client):
    """A project is created through an endpoint that contains no sync code at
    all. It must still reach every connected client."""
    headers = _login(client, "sync-project@example.com")
    me = client.get(f"{API}/auth/me", headers=headers).json()
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]

    queue = _events(me["id"])
    try:
        client.post(
            f"{API}/projects", json={"name": "Spring launch", "company_id": company}, headers=headers
        )
        events = _drain(queue)
    finally:
        sync_service.unsubscribe(me["id"], queue)

    kinds = {e["kind"] for e in events}
    assert "projects" in kinds, f"a new project told nobody; got {kinds}"
    assert all(e["type"] == "changed" for e in events)


def test_approvals_announce_on_every_transition(client):
    headers = _login(client, "sync-approvals@example.com")
    me = client.get(f"{API}/auth/me", headers=headers).json()
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    client.put(
        f"{API}/capabilities/email/config",
        json={"enabled": True, "permissions": ["send"], "company_id": company}, headers=headers,
    )

    queue = _events(me["id"])
    try:
        req = client.post(
            f"{API}/approvals",
            json={"capability_name": "email", "action_type": "send",
                  "payload": {"to": "a@b.com"}, "company_id": company},
            headers=headers,
        ).json()
        proposed = _drain(queue)
        client.post(f"{API}/approvals/{req['id']}/reject", json={}, headers=headers)
        decided = _drain(queue)
    finally:
        sync_service.unsubscribe(me["id"], queue)

    assert any(e["kind"] == "approvals" for e in proposed), "proposing told nobody"
    assert any(e["kind"] == "approvals" for e in decided), "deciding told nobody"


def test_events_never_cross_accounts(client):
    """A fan-out bug here would leak one business's activity into another's
    client. Scoped by owner, always."""
    a = _login(client, "sync-a@example.com")
    b = _login(client, "sync-b@example.com")
    me_b = client.get(f"{API}/auth/me", headers=b).json()

    queue_b = _events(me_b["id"])
    try:
        client.post(f"{API}/companies", json={"name": "A's company"}, headers=a)
        leaked = _drain(queue_b)
    finally:
        sync_service.unsubscribe(me_b["id"], queue_b)

    assert leaked == [], f"another account's writes reached this client: {leaked}"


def test_a_rolled_back_transaction_announces_nothing():
    """Announcing a change that was rolled back would send every client to
    re-read something that never happened."""
    from app.db.models.company import Company
    from app.db.session import SessionLocal

    db = SessionLocal()
    queue = sync_service.subscribe("rollback-owner")
    try:
        db.add(Company(name="Never committed", owner_id="rollback-owner"))
        db.flush()          # collected...
        db.rollback()       # ...but never committed
        assert _drain(queue) == []
    finally:
        sync_service.unsubscribe("rollback-owner", queue)
        db.close()


def test_versions_advance_so_a_slept_device_can_tell_it_fell_behind():
    """The mechanism a phone uses after being backgrounded: compare stamps
    rather than trusting that no events were missed."""
    before = sync_service.versions_for("v-owner", "v-company")["versions"]
    sync_service.mark_changed(company_id="v-company", kind="products", owner_id="v-owner")
    after = sync_service.versions_for("v-owner", "v-company")["versions"]
    assert after["v-company"] == before.get("v-company", 0) + 1


def test_the_epoch_forces_a_resync_after_a_backend_restart():
    """Versions are per-process. Without an epoch a client holding version 12
    would look ahead of a restarted server at 0 and never re-read."""
    assert sync_service.EPOCH
    assert sync_service.versions_for("any")["epoch"] == sync_service.EPOCH


def test_the_stream_requires_authentication(client):
    """The feed carries which workspaces are active and when — it is not public."""
    assert client.get(f"{API}/sync/versions").status_code in (401, 403)


def test_the_stream_opens_and_states_where_the_client_stands(client):
    headers = _login(client, "sync-stream@example.com")
    body = client.get(f"{API}/sync/versions", headers=headers).json()
    assert "epoch" in body and "versions" in body
