"""
Coverage for the three Website Builder modes: New, Improve Existing, Client
(clients endpoint + mode-aware workspace create + the improve-mode analyze
stage). AI provider + the website crawler are monkeypatched so tests run
offline and deterministically.
"""
import json

import pytest

API = "/api/v1"


def _login(client, email, password="supersecret123"):
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name):
    r = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


_PLAN = {
    "sitemap": [{"path": "/", "title": "Home", "purpose": "Landing", "sections": ["Hero"]}],
    "layouts": {"/": {"sections": [{"name": "Hero", "type": "hero", "description": "d"}]}},
    "copy": {"/": {"heading": "H", "sections": [{"title": "t", "body": "b"}]}},
    "design": {"palette": [{"name": "P", "hex": "#0f766e"}], "typography": {"heading": "Inter", "body": "Inter"}, "style_notes": "s"},
}
_COMPONENTS = {"files": [
    {"path": "src/App.jsx", "language": "jsx", "content": "import React from 'react';\nexport default function App(){return <div/>;}"},
    {"path": "src/styles.css", "language": "css", "content": "body{}"},
]}


class _BuildProvider:
    supports_tools = False

    async def stream(self, *a, **k):  # pragma: no cover
        yield ""

    async def complete(self, messages, **k):
        from app.ai_providers.base import CompletionResult

        payload = _COMPONENTS if "React engineer" in messages[0].content else _PLAN
        # Capture the plan user prompt so improve-mode tests can assert the
        # analysis was injected.
        _BuildProvider.last_user = messages[-1].content
        return CompletionResult(text=json.dumps(payload), model="fake", provider="fake")


async def _fake_analyze(url, *, max_pages=3):
    return {
        "source_url": "https://acme.com",
        "brand": "Acme Corp",
        "description": "We sell widgets",
        "logo": None,
        "palette": ["#0f766e", "#111827"],
        "fonts": ["Inter"],
        "nav": ["/", "/about", "/pricing"],
        "pages": [{"url": "https://acme.com", "title": "Acme", "headings": ["Welcome to Acme"]}],
        "fetched": 2,
    }


@pytest.fixture
def modes_env(monkeypatch):
    from app.api.v1.endpoints import workspaces
    from app.core import website_analyzer

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _BuildProvider())
    monkeypatch.setattr(website_analyzer, "analyze", _fake_analyze)


# --- Clients --------------------------------------------------------------


def test_client_crud_and_company_scoping(client):
    headers = _login(client, "cl-crud@example.com")
    a = _company(client, headers, "AgencyA")
    b = _company(client, headers, "AgencyB")

    created = client.post(f"{API}/clients", json={"name": "Acme", "company_id": a, "website": "acme.com"}, headers=headers)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    # Listed under company A, not B.
    assert any(c["id"] == cid for c in client.get(f"{API}/clients?company_id={a}", headers=headers).json())
    assert all(c["id"] != cid for c in client.get(f"{API}/clients?company_id={b}", headers=headers).json())

    # Another user can't see or fetch it.
    other = _login(client, "cl-other@example.com")
    assert client.get(f"{API}/clients", headers=other).json() == []
    assert client.get(f"{API}/clients/{cid}", headers=other).status_code == 404

    detail = client.get(f"{API}/clients/{cid}", headers=headers).json()
    assert detail["name"] == "Acme" and detail["projects"] == []


def test_empty_client_name_rejected(client):
    headers = _login(client, "cl-empty@example.com")
    assert client.post(f"{API}/clients", json={"name": "  "}, headers=headers).status_code == 422


# --- Mode validation on create -------------------------------------------


def test_create_validates_modes(client):
    headers = _login(client, "wm-validate@example.com")
    # bad mode
    assert client.post(f"{API}/workspaces", json={"action": "web_builder", "mode": "nope"}, headers=headers).status_code == 422
    # improve needs url
    assert client.post(f"{API}/workspaces", json={"action": "web_builder", "mode": "improve"}, headers=headers).status_code == 422
    # client needs client_id
    assert client.post(f"{API}/workspaces", json={"action": "web_builder", "mode": "client"}, headers=headers).status_code == 422
    # client_id must exist/be owned
    assert client.post(
        f"{API}/workspaces", json={"action": "web_builder", "mode": "client", "client_id": "nope"}, headers=headers
    ).status_code == 404


# --- Mode 1: New ----------------------------------------------------------


def test_new_mode_default(client):
    headers = _login(client, "wm-new@example.com")
    company = _company(client, headers, "PrimalPenni")
    s = client.post(f"{API}/workspaces", json={"action": "web_builder", "company_id": company}, headers=headers).json()
    assert s["mode"] == "new" and s["client_id"] is None
    assert s["project_id"]  # its own project


# --- Mode 2: Improve Existing --------------------------------------------


def test_improve_mode_creates_session_and_analyzes(client, modes_env):
    headers = _login(client, "wm-improve@example.com")
    company = _company(client, headers, "PrimalPenni")
    s = client.post(
        f"{API}/workspaces",
        json={"action": "web_builder", "company_id": company, "mode": "improve", "source_url": "acme.com"},
        headers=headers,
    ).json()
    assert s["mode"] == "improve" and s["source_url"] == "acme.com"

    resp = client.post(f"{API}/workspaces/{s['id']}/website/build", json={"approved": False}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert '"stage": "analyze"' in resp.text and '"type": "awaiting_approval"' in resp.text

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    analysis = full["state"]["source_analysis"]
    assert analysis["brand"] == "Acme Corp" and analysis["fetched"] == 2
    # A plan was produced grounded in the analysis.
    assert full["state"]["sitemap"]
    assert "Acme Corp" in _BuildProvider.last_user  # analysis injected into the plan prompt
    # Analysis saved as an artifact.
    assert any(a["title"] == "Existing site analysis" for a in full["artifacts"])


def test_improve_mode_blocks_private_urls(client, monkeypatch):
    # Use the REAL analyzer here to exercise the SSRF guard.
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _BuildProvider())
    headers = _login(client, "wm-ssrf@example.com")
    s = client.post(
        f"{API}/workspaces",
        json={"action": "web_builder", "mode": "improve", "source_url": "http://127.0.0.1:8000"},
        headers=headers,
    ).json()
    resp = client.post(f"{API}/workspaces/{s['id']}/website/build", json={"approved": False}, headers=headers)
    assert resp.status_code == 200
    assert '"type": "error"' in resp.text  # blocked, reported honestly
    assert '"stage": "plan"' not in resp.text


# --- Mode 3: Client -------------------------------------------------------


def test_client_mode_scopes_project_under_client(client, modes_env):
    headers = _login(client, "wm-client@example.com")
    company = _company(client, headers, "AgencyCo")
    cid = client.post(f"{API}/clients", json={"name": "Beta Client", "company_id": company}, headers=headers).json()["id"]

    s = client.post(
        f"{API}/workspaces",
        json={"action": "web_builder", "company_id": company, "mode": "client", "client_id": cid},
        headers=headers,
    ).json()
    assert s["mode"] == "client" and s["client_id"] == cid

    # The session's project is tagged to the client and named for it.
    client_detail = client.get(f"{API}/clients/{cid}", headers=headers).json()
    assert client_detail["project_count"] == 1
    assert any(p["id"] == s["project_id"] for p in client_detail["projects"])
    assert any("Beta Client" in p["name"] for p in client_detail["projects"])

    # Build runs and tailors to the client.
    resp = client.post(f"{API}/workspaces/{s['id']}/website/build", json={"approved": False}, headers=headers)
    assert resp.status_code == 200 and '"type": "awaiting_approval"' in resp.text
    assert "Beta Client" in _BuildProvider.last_user  # client directive injected

    # A company-level (non-client) build stays separate from the client.
    s2 = client.post(
        f"{API}/workspaces", json={"action": "web_builder", "company_id": company}, headers=headers
    ).json()
    assert s2["client_id"] is None
    still_one = client.get(f"{API}/clients/{cid}", headers=headers).json()
    assert still_one["project_count"] == 1  # the company build did NOT land under the client
