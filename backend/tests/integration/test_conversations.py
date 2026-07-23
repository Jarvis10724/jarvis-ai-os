"""
One conversation history, owned by the backend.

The Ask Jarvis thread used to live in each browser's localStorage, so a Mac and
an iPhone held genuinely different histories for the same workspace. It is now a
WorkspaceSession like any other: stored once, scoped by owner and company, and
broadcast as the "conversations" kind by the existing sync hooks.

These tests cover what the migration must not get wrong — losing a message,
duplicating one, reordering them, or letting one company's conversation surface
in another.
"""
API = "/api/v1"


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _thread(client, headers, company_id):
    return client.post(
        f"{API}/workspaces", json={"action": "chat", "company_id": company_id}, headers=headers
    ).json()


def test_a_conversation_is_a_real_backend_session(client):
    headers = _login(client, "conv-basic@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    thread = _thread(client, headers, company)
    assert thread["action"] == "chat"

    client.post(
        f"{API}/workspaces/{thread['id']}/turns",
        json={"turns": [
            {"role": "user", "content": "how much RARE EARTH is left?", "ts": "2026-07-22T10:00:00"},
            {"role": "assistant", "content": "42 units.", "ts": "2026-07-22T10:00:05"},
        ]},
        headers=headers,
    )
    # A different device reads the same thread back.
    got = client.get(f"{API}/workspaces/{thread['id']}", headers=headers).json()
    assert [m["content"] for m in got["messages"]] == ["how much RARE EARTH is left?", "42 units."]


def test_the_same_turn_sent_twice_is_stored_once(client):
    """Both devices upload overlapping history during migration, and a retry
    after a dropped response repeats a turn. Neither may duplicate a message."""
    headers = _login(client, "conv-dupes@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    thread = _thread(client, headers, company)
    turn = {"turns": [{"role": "user", "content": "restock the polish", "ts": "2026-07-22T11:00:00"}]}

    first = client.post(f"{API}/workspaces/{thread['id']}/turns", json=turn, headers=headers).json()
    second = client.post(f"{API}/workspaces/{thread['id']}/turns", json=turn, headers=headers).json()

    assert first["added"] == 1
    assert second["added"] == 0
    assert len(second["messages"]) == 1


def test_a_merged_history_keeps_original_order(client):
    """Two devices' histories interleave by timestamp, not by upload order."""
    headers = _login(client, "conv-merge@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    thread = _thread(client, headers, company)

    # The phone uploads its history second, but some of it happened first.
    client.post(f"{API}/workspaces/{thread['id']}/turns", headers=headers, json={"turns": [
        {"role": "user", "content": "from the mac", "ts": "2026-07-22T12:00:00"},
    ]})
    client.post(f"{API}/workspaces/{thread['id']}/turns", headers=headers, json={"turns": [
        {"role": "user", "content": "from the phone, earlier", "ts": "2026-07-22T09:00:00"},
    ]})

    messages = client.get(f"{API}/workspaces/{thread['id']}", headers=headers).json()["messages"]
    assert [m["content"] for m in messages] == ["from the phone, earlier", "from the mac"]


def test_conversations_stay_inside_their_own_company(client):
    """Primal Penni conversations must never surface in Greener Capitol."""
    headers = _login(client, "conv-sep@example.com")
    spn = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    gcs = client.post(f"{API}/companies", json={"name": "Greener Capitol Solutions LLC"}, headers=headers).json()["id"]

    spn_thread = _thread(client, headers, spn)
    client.post(f"{API}/workspaces/{spn_thread['id']}/turns", headers=headers,
                json={"turns": [{"role": "user", "content": "primal penni inventory"}]})

    listed = client.get(f"{API}/workspaces?company_id={gcs}", headers=headers).json()
    ids = {s["id"] for s in (listed if isinstance(listed, list) else listed.get("sessions", []))}
    assert spn_thread["id"] not in ids


def test_another_account_cannot_read_the_thread(client):
    headers = _login(client, "conv-owner@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    thread = _thread(client, headers, company)
    stranger = _login(client, "conv-stranger@example.com")
    assert client.get(f"{API}/workspaces/{thread['id']}", headers=stranger).status_code in (403, 404)


def test_appending_broadcasts_conversations_to_every_client(client):
    """It must reach other devices through the EXISTING sync architecture —
    committing is what broadcasts; there is no conversation-specific path."""
    from app.core import sync_service

    headers = _login(client, "conv-sync@example.com")
    me = client.get(f"{API}/auth/me", headers=headers).json()
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    thread = _thread(client, headers, company)

    queue = sync_service.subscribe(me["id"])
    try:
        client.post(f"{API}/workspaces/{thread['id']}/turns", headers=headers,
                    json={"turns": [{"role": "user", "content": "sent from the phone"}]})
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
    finally:
        sync_service.unsubscribe(me["id"], queue)

    assert any(e["kind"] == "conversations" for e in events), f"no broadcast; got {[e['kind'] for e in events]}"
