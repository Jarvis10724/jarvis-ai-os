"""
Coverage for live Deep Research web-search integration
(app.core.search_service + app.search + the deep_research turn wiring).

The search provider AND the AI provider are monkeypatched so tests run offline
and deterministically. What we verify: retrieved sources land in the session
state with derived=false + real URLs, the model can cite them, results are
cached (the provider is hit once per query), search stays company-isolated,
and an unconfigured provider degrades gracefully.
"""
import pytest

from app.core import search_service
from app.search.base import SearchResult

API = "/api/v1"


def _register_and_login(client, email: str, password: str = "supersecret123") -> dict:
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_company(client, headers, name):
    resp = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class _CountingSearchProvider:
    """Deterministic search results + a call counter to prove caching."""

    name = "testsearch"

    def __init__(self):
        self.calls = 0

    @property
    def configured(self):
        return True

    async def search(self, query, *, max_results=5):
        self.calls += 1
        return [
            SearchResult(
                title="Copper Peptide Skincare Market Report 2024",
                url="https://research.example.com/copper-peptides",
                snippet="The copper peptide skincare segment grew ~20% YoY.",
                source="research.example.com",
                score=0.95,
            ),
            SearchResult(
                title="GHK-Cu Clinical Evidence Review",
                url="https://journal.example.com/ghk-cu",
                snippet="GHK-Cu shows collagen-supporting activity in studies.",
                source="journal.example.com",
                score=0.88,
            ),
        ]


class _CitingAIProvider:
    """Streams a report + a jarvis-state block that cites the retrieved sources."""

    supports_tools = False

    async def complete(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, *a, **k):
        yield "Copper peptides are a growing skincare segment.\n\n"
        yield (
            "```jarvis-state\n"
            '{"report": "The market grew ~20% YoY [s1]; GHK-Cu supports collagen [s2].",'
            ' "citations": [{"claim": "market grew ~20% YoY", "source_id": "s1"},'
            ' {"claim": "GHK-Cu supports collagen", "source_id": "s2"}]}\n'
            "```"
        )


@pytest.fixture
def search_wired(monkeypatch):
    """Wire a counting search provider + a citing AI provider into the endpoint,
    with a clean cache."""
    from app.api.v1.endpoints import workspaces

    provider = _CountingSearchProvider()
    search_service.cache_clear()
    monkeypatch.setattr(search_service, "get_search_provider", lambda: provider)
    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _CitingAIProvider())
    return provider


def test_research_turn_attaches_live_sources_and_citations(client, search_wired):
    headers = _register_and_login(client, "dr-live@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    s = client.post(
        f"{API}/workspaces", json={"action": "deep_research", "company_id": company}, headers=headers
    ).json()

    resp = client.post(
        f"{API}/workspaces/{s['id']}/message",
        json={"content": "copper peptide skincare market size"},
        headers=headers,
    )
    assert resp.status_code == 200 and '"type": "done"' in resp.text

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    sources = full["state"]["sources"]
    # Real retrieved sources, marked live (derived=false) with real URLs + ids.
    assert len(sources) == 2
    assert sources[0]["id"] == "s1" and sources[0]["derived"] is False
    assert sources[0]["url"].startswith("https://research.example.com/")
    # Citations map claims to those source ids.
    cites = full["state"]["citations"]
    assert {c["source_id"] for c in cites} == {"s1", "s2"}
    # The report references them.
    assert "[s1]" in full["state"]["report"]


def test_search_results_are_cached(client, search_wired):
    headers = _register_and_login(client, "dr-cache@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "deep_research"}, headers=headers).json()

    for _ in range(3):
        client.post(
            f"{API}/workspaces/{s['id']}/message",
            json={"content": "copper peptide market"},  # identical query each time
            headers=headers,
        )
    # Three research turns on the same query hit the search API only once.
    assert search_wired.calls == 1


def test_search_cache_shared_but_sources_stay_company_isolated(client, search_wired):
    headers = _register_and_login(client, "dr-iso@example.com")
    a = _create_company(client, headers, "CompanyA")
    b = _create_company(client, headers, "CompanyB")
    sa = client.post(
        f"{API}/workspaces", json={"action": "deep_research", "company_id": a}, headers=headers
    ).json()
    sb = client.post(
        f"{API}/workspaces", json={"action": "deep_research", "company_id": b}, headers=headers
    ).json()

    q = {"content": "copper peptide market"}
    client.post(f"{API}/workspaces/{sa['id']}/message", json=q, headers=headers)
    client.post(f"{API}/workspaces/{sb['id']}/message", json=q, headers=headers)

    # Public results cached once across companies...
    assert search_wired.calls == 1
    # ...but each company's session owns its own sources, and neither leaks.
    fa = client.get(f"{API}/workspaces/{sa['id']}", headers=headers).json()
    fb = client.get(f"{API}/workspaces/{sb['id']}", headers=headers).json()
    assert fa["company_id"] == a and fb["company_id"] == b
    assert len(fa["state"]["sources"]) == 2 and len(fb["state"]["sources"]) == 2
    # Company A cannot see Company B's research session.
    only_a = client.get(f"{API}/workspaces?company_id={a}&action=deep_research", headers=headers).json()
    assert all(x["company_id"] == a for x in only_a)
    assert all(x["id"] != sb["id"] for x in only_a)


def test_search_status_reports_provider(client, monkeypatch):
    from app.api.v1.endpoints import workspaces as ws_endpoint
    from app.search import factory

    headers = _register_and_login(client, "dr-status@example.com")

    # Unconfigured -> honest "not configured".
    monkeypatch.setattr(factory, "get_search_provider", lambda: None)
    body = client.get(f"{API}/workspaces/search/status", headers=headers).json()
    assert body["configured"] is False and body["provider"] is None

    # Configured -> reports the provider name.
    monkeypatch.setattr(factory, "get_search_provider", lambda: _CountingSearchProvider())
    body = client.get(f"{API}/workspaces/search/status", headers=headers).json()
    assert body["configured"] is True and body["provider"] == "testsearch"


def test_research_without_search_still_works(client, monkeypatch):
    """When no provider is configured, the turn proceeds with no injected
    sources (honest model-knowledge mode) and still persists normally."""
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(search_service, "get_search_provider", lambda: None)

    class _Plain:
        supports_tools = False

        async def complete(self, *a, **k):  # pragma: no cover
            raise NotImplementedError

        async def stream(self, *a, **k):
            yield "A knowledge-based briefing."

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _Plain())

    headers = _register_and_login(client, "dr-nosearch@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "deep_research"}, headers=headers).json()
    resp = client.post(
        f"{API}/workspaces/{s['id']}/message", json={"content": "some topic"}, headers=headers
    )
    assert resp.status_code == 200 and '"type": "error"' not in resp.text
    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant"]
    # No live sources were injected.
    assert full["state"].get("sources") in (None, [])


def test_factory_selects_provider_from_config(monkeypatch):
    from app.config import settings
    from app.search import factory

    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "")
    factory.reset_cache()
    assert factory.get_search_provider() is None

    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "mock")
    factory.reset_cache()
    p = factory.get_search_provider()
    assert p is not None and p.name == "mock" and factory.search_configured() is True

    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "nonexistent")
    factory.reset_cache()
    assert factory.get_search_provider() is None
