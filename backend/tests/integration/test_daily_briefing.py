"""
Daily Brief must be company-scoped: switching workspaces shows that business's
own brief, never another company's. Covers app.api.v1.endpoints.dashboard's
save/get daily-briefing.
"""
API = "/api/v1"


def _login(client, email: str) -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    tok = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _company(client, headers, name: str) -> str:
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def test_daily_briefing_is_company_scoped(client):
    h = _login(client, "brief-scope@example.com")
    a = _company(client, h, "Alpha Co")
    b = _company(client, h, "Beta Co")

    client.post(f"{API}/dashboard/daily-briefing", json={"content": "ALPHA brief", "company_id": a}, headers=h)
    client.post(f"{API}/dashboard/daily-briefing", json={"content": "BETA brief", "company_id": b}, headers=h)

    got_a = client.get(f"{API}/dashboard/daily-briefing/latest?company_id={a}", headers=h).json()
    got_b = client.get(f"{API}/dashboard/daily-briefing/latest?company_id={b}", headers=h).json()
    assert got_a["content"] == "ALPHA brief"
    assert got_b["content"] == "BETA brief"

    # A company with no brief yet doesn't inherit another company's.
    c = _company(client, h, "Gamma Co")
    assert client.get(f"{API}/dashboard/daily-briefing/latest?company_id={c}", headers=h).json() is None


def test_daily_briefing_account_wide_when_no_company(client):
    h = _login(client, "brief-nocompany@example.com")
    client.post(f"{API}/dashboard/daily-briefing", json={"content": "org-wide brief"}, headers=h)
    got = client.get(f"{API}/dashboard/daily-briefing/latest", headers=h).json()
    assert got["content"] == "org-wide brief"

    # And a company-scoped query doesn't return the account-wide brief.
    co = _company(client, h, "Solo Co")
    assert client.get(f"{API}/dashboard/daily-briefing/latest?company_id={co}", headers=h).json() is None
