"""
Structured workspace metadata: company_type + parent_company_id.

These drive module availability, AI behavior, and branding, so Jarvis
understands each workspace by data rather than by name. Verifies the fields
round-trip through create/read/update and that the parent relationship is
same-account only (never cross-workspace).
"""
API = "/api/v1"


def _login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_company_type_round_trips_on_create_and_read(client):
    headers = _login(client, "wm-type@example.com")
    resp = client.post(
        f"{API}/companies",
        json={"name": "SNP Group LLC", "industry": "Consumer Goods", "company_type": "consumer-brands"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["company_type"] == "consumer-brands"

    # Reads back the same on the collection endpoint.
    listed = client.get(f"{API}/companies", headers=headers).json()
    assert listed[0]["company_type"] == "consumer-brands"


def test_company_type_updatable(client):
    headers = _login(client, "wm-update@example.com")
    cid = client.post(f"{API}/companies", json={"name": "Acme"}, headers=headers).json()["id"]
    assert client.get(f"{API}/companies/{cid}", headers=headers).json()["company_type"] is None

    resp = client.put(f"{API}/companies/{cid}", json={"company_type": "innovation-hub"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["company_type"] == "innovation-hub"


def test_parent_company_links_within_account(client):
    headers = _login(client, "wm-parent@example.com")
    parent = client.post(
        f"{API}/companies", json={"name": "Greener Capitol", "company_type": "innovation-hub"}, headers=headers
    ).json()
    child = client.post(
        f"{API}/companies",
        json={"name": "Primal Penni", "company_type": "consumer-brands", "parent_company_id": parent["id"]},
        headers=headers,
    )
    assert child.status_code == 201, child.text
    body = child.json()
    assert body["parent_company_id"] == parent["id"]
    assert body["parent_company_name"] == "Greener Capitol"


def test_parent_must_be_same_account(client):
    owner = _login(client, "wm-owner@example.com")
    other = _login(client, "wm-other@example.com")
    foreign = client.post(f"{API}/companies", json={"name": "Foreign Co"}, headers=other).json()

    # Referencing another account's company as parent must fail (isolation).
    resp = client.post(
        f"{API}/companies",
        json={"name": "Mine", "parent_company_id": foreign["id"]},
        headers=owner,
    )
    assert resp.status_code == 404, resp.text


def test_company_cannot_be_its_own_parent(client):
    headers = _login(client, "wm-self@example.com")
    cid = client.post(f"{API}/companies", json={"name": "Loop Co"}, headers=headers).json()["id"]
    resp = client.put(f"{API}/companies/{cid}", json={"parent_company_id": cid}, headers=headers)
    assert resp.status_code == 422, resp.text
