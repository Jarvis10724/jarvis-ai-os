"""
Workspace Intelligence: an AI reading of what's happening in a workspace,
built only from that workspace's own signals.

The AI provider is monkeypatched, so these tests verify the contract offline:
  * signals are gathered from real workspace data,
  * the analysis carries the reading AND the evidence behind it,
  * one workspace's analysis never contains another's data,
  * a provider failure degrades to raw signals instead of a fabricated reading.
"""
API = "/api/v1"


class _FakeResult:
    def __init__(self, text):
        self.text = text
        self.tool_calls = []
        self.content_blocks = None


class _FakeProvider:
    #: echoes the signals it was given so tests can assert on grounding
    async def complete(self, messages, **kwargs):
        return _FakeResult(
            '{"headline":"Two projects moving, one approval waiting.",'
            '"state_of_play":"Steady.","signals":[{"label":"Approvals","detail":"1 pending"}],'
            '"risks":[{"title":"Stalled reorder","detail":"waiting on approval"}],'
            '"recommendations":[{"title":"Clear the pending approval","why":"it blocks the reorder",'
            '"real_world":false}]}'
        )


class _BrokenProvider:
    async def complete(self, messages, **kwargs):
        raise RuntimeError("provider down")


def _patch(monkeypatch, provider):
    monkeypatch.setattr("app.core.workspace_intelligence_service.get_ai_provider", lambda: provider)
    # Analyses are cached per company; start each test from a clean slate.
    monkeypatch.setattr("app.core.workspace_intelligence_service._cache", {})


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name):
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def _pending_approval(company_id):
    """A real pending approval, so the signals exercise that branch."""
    from app.db.models.capability import ApprovalRequest
    from app.db.models.company import Company
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        owner_id = db.query(Company).filter(Company.id == company_id).first().owner_id
        db.add(
            ApprovalRequest(
                owner_id=owner_id,
                company_id=company_id,
                capability_name="gmail",
                action_type="send_email",
                payload_json='{"to": "supplier@example.com", "subject": "Reorder"}',
                status="pending",
            )
        )
        db.commit()
    finally:
        db.close()


def test_signals_come_from_real_workspace_data(client, monkeypatch):
    _patch(monkeypatch, _FakeProvider())
    headers = _login(client, "wi-signals@example.com")
    company = _company(client, headers, "Primal Penni")
    client.post(
        f"{API}/projects",
        json={"name": "Spring Launch", "company_id": company},
        headers=headers,
    )
    _pending_approval(company)

    resp = client.get(f"{API}/workspace-intelligence/signals?company_id={company}", headers=headers)
    assert resp.status_code == 200, resp.text
    signals = resp.json()
    assert signals["workspace"]["name"] == "Primal Penni"
    assert "Spring Launch" in signals["projects"]["names"]
    assert signals["brand_brain"]["connected"] is False
    # Pending approvals are surfaced with enough detail to be acted on.
    assert len(signals["pending_approvals"]) == 1
    approval = signals["pending_approvals"][0]
    assert approval["capability"] == "gmail" and approval["action"] == "send_email"
    assert "supplier@example.com" in approval["details"]


def test_analysis_carries_reading_and_its_evidence(client, monkeypatch):
    _patch(monkeypatch, _FakeProvider())
    headers = _login(client, "wi-analyze@example.com")
    company = _company(client, headers, "Primal Penni")

    body = client.get(f"{API}/workspace-intelligence?company_id={company}", headers=headers).json()
    assert body["headline"].startswith("Two projects")
    assert body["recommendations"][0]["title"] == "Clear the pending approval"
    assert body["recommendations"][0]["real_world"] is False
    # The evidence the reading was built from travels with it.
    assert body["evidence"]["workspace"]["name"] == "Primal Penni"


def test_analysis_is_scoped_to_its_own_workspace(client, monkeypatch):
    _patch(monkeypatch, _FakeProvider())
    headers = _login(client, "wi-scope@example.com")
    penni = _company(client, headers, "Primal Penni")
    greener = _company(client, headers, "Greener Capitol")
    client.post(f"{API}/projects", json={"name": "Penni Only", "company_id": penni}, headers=headers)

    other = client.get(f"{API}/workspace-intelligence/signals?company_id={greener}", headers=headers).json()
    assert other["projects"]["names"] == [] or "Penni Only" not in other["projects"]["names"]

    # And another account can't read this workspace at all.
    stranger = _login(client, "wi-stranger@example.com")
    assert (
        client.get(f"{API}/workspace-intelligence?company_id={penni}", headers=stranger).status_code
        == 404
    )


def test_provider_failure_degrades_to_raw_signals(client, monkeypatch):
    _patch(monkeypatch, _BrokenProvider())
    headers = _login(client, "wi-broken@example.com")
    company = _company(client, headers, "Primal Penni")

    body = client.get(f"{API}/workspace-intelligence?company_id={company}", headers=headers).json()
    assert "unavailable" in body["headline"].lower()
    assert body["recommendations"] == []
    # No fabricated reading — but the real signals are still there.
    assert body["evidence"]["workspace"]["name"] == "Primal Penni"
