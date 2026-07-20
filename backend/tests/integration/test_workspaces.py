"""
Coverage for Quick-Action workspaces (app.api.v1.endpoints.workspaces).

Real HTTP via TestClient against the test SQLite DB, same as the rest of the
suite. The streaming AI call is monkeypatched so tests run offline — what we
verify is the workspace machinery: a session auto-creates a Project + kick-off
Task, is company-scoped/isolated, restores its full state, and a message turn
persists the assistant reply + artifact + a Task and is captured to memory.
"""
import json

import pytest

from app.ai_providers import factory

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


class _FakeProvider:
    """Streams a fixed reply so the workspace turn can be exercised offline."""

    supports_tools = False

    async def complete(self, *a, **k):  # pragma: no cover - unused here
        raise NotImplementedError

    async def stream(self, *a, **k):
        for chunk in ["Here is ", "your ", "deliverable."]:
            yield chunk


class _StateProvider:
    """Streams a reply that ends with a jarvis-state block, to exercise the
    structured-state merge + block-stripping."""

    supports_tools = False

    async def complete(self, *a, **k):  # pragma: no cover - unused here
        raise NotImplementedError

    async def stream(self, *a, **k):
        yield "Proposed sitemap below.\n\n"
        yield '```jarvis-state\n{"sitemap": [{"path": "/", "title": "Home"}]}\n```'


@pytest.fixture
def state_provider(monkeypatch):
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _StateProvider())


@pytest.fixture
def fake_provider(monkeypatch):
    monkeypatch.setattr(factory, "get_ai_provider", lambda name=None: _FakeProvider())
    # workspaces.py imported get_ai_provider by name — patch there too.
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _FakeProvider())


# --- Production-hardening fixtures ----------------------------------------


class _FailingProvider:
    """Streams one chunk then the provider dies mid-stream."""

    supports_tools = False

    async def complete(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, *a, **k):
        from app.exceptions import AIProviderError

        yield "partial "
        raise AIProviderError("provider went down mid-stream")


class _EmptyBlockProvider:
    """Streams prose + an EMPTY jarvis-state block (the model forgot to fill
    it). complete() serves the structuring-fallback pass."""

    supports_tools = False

    async def complete(self, messages, **k):
        from app.ai_providers.base import CompletionResult

        return CompletionResult(
            text='{"plan": [{"step": "scope the market", "status": "todo"}]}',
            model="fake",
            provider="fake",
        )

    async def stream(self, *a, **k):
        yield "Research report body.\n\n"
        yield "```jarvis-state\n{}\n```"


class _MislabelProvider:
    """Puts the state in a ```json fence (mislabeled) instead of jarvis-state."""

    supports_tools = False

    async def complete(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, *a, **k):
        yield "Here is the code.\n\n"
        yield '```json\n{"files": [{"path": "a.py", "language": "python", "content": "x = 1"}]}\n```'


class _FakeImageProvider:
    name = "fakeimg"
    supports_images = True
    supports_tools = False

    async def complete(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, *a, **k):  # pragma: no cover
        yield ""

    async def generate_image(self, prompt, *, size="1024x1024", model=None):
        from app.ai_providers.base import ImageResult

        return ImageResult(b64_png="ZmFrZQ==", model="gpt-image-1", provider=self.name, prompt=prompt)


def _patch_provider(monkeypatch, provider):
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: provider)


def test_create_session_makes_project_and_task(client):
    headers = _register_and_login(client, "ws-create@example.com")
    company = _create_company(client, headers, "PrimalPenni")

    resp = client.post(
        f"{API}/workspaces", json={"action": "web_builder", "company_id": company}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["action"] == "web_builder"
    assert body["action_label"] == "Website Studio"
    assert body["project_id"]  # attached to a real project
    assert len(body["tasks"]) == 1  # kick-off task
    assert body["tasks"][0]["status"] == "backlog"

    # The project is a real Project visible via the projects API.
    projects = client.get(f"{API}/projects", headers=headers).json()
    assert any(p["id"] == body["project_id"] for p in projects)


def test_unknown_action_rejected(client):
    headers = _register_and_login(client, "ws-badaction@example.com")
    resp = client.post(f"{API}/workspaces", json={"action": "nope"}, headers=headers)
    assert resp.status_code == 422, resp.text


def test_list_is_company_scoped_and_isolated(client):
    headers = _register_and_login(client, "ws-scope@example.com")
    a = _create_company(client, headers, "CoA")
    b = _create_company(client, headers, "CoB")
    client.post(f"{API}/workspaces", json={"action": "logo_design", "company_id": a}, headers=headers)
    client.post(f"{API}/workspaces", json={"action": "logo_design", "company_id": b}, headers=headers)

    only_a = client.get(f"{API}/workspaces?company_id={a}", headers=headers).json()
    assert len(only_a) == 1 and only_a[0]["company_id"] == a

    # Another user sees none of them.
    other = _register_and_login(client, "ws-scope-other@example.com")
    assert client.get(f"{API}/workspaces", headers=other).json() == []


def test_restore_full_session(client):
    headers = _register_and_login(client, "ws-restore@example.com")
    created = client.post(f"{API}/workspaces", json={"action": "deep_research"}, headers=headers).json()
    fetched = client.get(f"{API}/workspaces/{created['id']}", headers=headers).json()
    assert fetched["id"] == created["id"]
    assert "messages" in fetched and "artifacts" in fetched and "tasks" in fetched


def test_message_streams_and_persists(client, fake_provider):
    headers = _register_and_login(client, "ws-msg@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    session = client.post(
        f"{API}/workspaces", json={"action": "web_builder", "company_id": company}, headers=headers
    ).json()

    # Stream a turn — TestClient returns the full SSE body.
    resp = client.post(
        f"{API}/workspaces/{session['id']}/message",
        json={"content": "Build a landing page for a skincare brand"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers["content-type"]
    assert '"type": "token"' in resp.text
    assert '"type": "done"' in resp.text
    assert "deliverable" in resp.text  # the streamed reply came through

    # Reload: assistant message + artifact saved, turn task created + moved.
    full = client.get(f"{API}/workspaces/{session['id']}", headers=headers).json()
    roles = [m["role"] for m in full["messages"]]
    assert roles == ["user", "assistant"]
    assert full["messages"][1]["content"] == "Here is your deliverable."
    assert len(full["artifacts"]) == 1
    # kick-off task (backlog) + turn task (moved to review).
    statuses = sorted(t["status"] for t in full["tasks"])
    assert "review" in statuses
    # Session auto-titled from the first message.
    assert full["title"].startswith("Build a landing page")

    # Context was written to AI Memory for this company.
    mem = client.get(f"{API}/memory?company_id={company}", headers=headers).json()
    assert any("Website Studio" in m["title"] for m in mem)


def test_delete_session(client):
    headers = _register_and_login(client, "ws-del@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "code_writer"}, headers=headers).json()
    assert client.delete(f"{API}/workspaces/{s['id']}", headers=headers).status_code == 204
    assert client.get(f"{API}/workspaces/{s['id']}", headers=headers).status_code == 404


def test_actions_expose_stages(client):
    headers = _register_and_login(client, "ws-actions@example.com")
    actions = client.get(f"{API}/workspaces/actions", headers=headers).json()
    by_key = {a["key"]: a for a in actions}
    assert set(by_key) == {
        "web_builder", "logo_design", "product_creation", "deep_research", "code_writer", "automation"
    }
    web_stage_keys = [s["key"] for s in by_key["web_builder"]["stages"]]
    assert web_stage_keys[0] == "requirements"
    assert {"sitemap", "layouts", "components", "images", "preview"} <= set(web_stage_keys)
    assert by_key["logo_design"]["supports_images"] is True


def test_message_merges_structured_state_and_strips_block(client, state_provider):
    headers = _register_and_login(client, "ws-state@example.com")
    session = client.post(f"{API}/workspaces", json={"action": "web_builder"}, headers=headers).json()

    resp = client.post(
        f"{API}/workspaces/{session['id']}/message",
        json={"content": "Plan the site", "stage": "sitemap"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    # The jarvis-state block is stripped from the streamed visible text.
    assert "jarvis-state" not in resp.text

    full = client.get(f"{API}/workspaces/{session['id']}", headers=headers).json()
    # Structured state was merged in.
    assert full["state"]["sitemap"] == [{"path": "/", "title": "Home"}]
    # The saved assistant message is clean prose (no fenced state block).
    assert "jarvis-state" not in full["messages"][1]["content"]
    assert "Proposed sitemap" in full["messages"][1]["content"]
    # Artifact carries the richer shape (kind/version/stage).
    art = full["artifacts"][0]
    assert art["kind"] == "document" and art["version"] == 1 and art["stage"] == "sitemap"


def test_archive_hides_from_default_list(client):
    headers = _register_and_login(client, "ws-archive@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "automation"}, headers=headers).json()
    client.patch(f"{API}/workspaces/{s['id']}", json={"status": "archived"}, headers=headers)

    active = client.get(f"{API}/workspaces?action=automation", headers=headers).json()
    assert all(x["id"] != s["id"] for x in active)
    archived = client.get(f"{API}/workspaces?action=automation&status=archived", headers=headers).json()
    assert any(x["id"] == s["id"] for x in archived)


def test_recent_across_actions(client):
    headers = _register_and_login(client, "ws-recent@example.com")
    client.post(f"{API}/workspaces", json={"action": "web_builder"}, headers=headers)
    client.post(f"{API}/workspaces", json={"action": "logo_design"}, headers=headers)
    recent = client.get(f"{API}/workspaces/recent", headers=headers).json()
    actions = {r["action"] for r in recent}
    assert {"web_builder", "logo_design"} <= actions


def test_save_artifact_and_attach_task(client):
    headers = _register_and_login(client, "ws-artifact@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "code_writer"}, headers=headers).json()

    a1 = client.post(
        f"{API}/workspaces/{s['id']}/artifacts",
        json={"title": "main.py", "content": "print(1)", "kind": "code", "stage": "files"},
        headers=headers,
    ).json()
    assert a1["version"] == 1 and a1["kind"] == "code"
    a2 = client.post(
        f"{API}/workspaces/{s['id']}/artifacts",
        json={"title": "main.py", "content": "print(2)", "kind": "code"},
        headers=headers,
    ).json()
    assert a2["version"] == 2  # version-history chain by title

    task = client.post(
        f"{API}/workspaces/{s['id']}/tasks", json={"title": "Write tests"}, headers=headers
    ).json()
    assert task["status"] == "backlog"
    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    assert any(t["title"] == "Write tests" for t in full["tasks"])


def test_image_and_search_status_report_unconfigured(client, monkeypatch):
    # Force "no provider" so this is hermetic regardless of the developer's .env
    # (which may legitimately have SEARCH_PROVIDER/keys set for live use).
    from app.search import factory

    monkeypatch.setattr(factory, "get_search_provider", lambda: None)
    headers = _register_and_login(client, "ws-imgstatus@example.com")
    img = client.get(f"{API}/workspaces/image/status", headers=headers).json()
    search = client.get(f"{API}/workspaces/search/status", headers=headers).json()
    # Reported honestly, not faked.
    assert "configured" in img
    assert search["configured"] is False


def test_image_generation_degrades_without_provider(client):
    headers = _register_and_login(client, "ws-img@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "logo_design"}, headers=headers).json()
    resp = client.post(
        f"{API}/workspaces/{s['id']}/image",
        json={"prompt": "a minimalist fox mark"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Without an image provider it degrades to a clear message — never a fake image.
    if body["configured"] is False:
        assert "image" not in body


# --- Error handling -------------------------------------------------------


def test_empty_message_rejected(client, fake_provider):
    headers = _register_and_login(client, "ws-empty@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "web_builder"}, headers=headers).json()
    resp = client.post(f"{API}/workspaces/{s['id']}/message", json={"content": "   "}, headers=headers)
    assert resp.status_code == 422, resp.text


def test_message_to_missing_session_404(client, fake_provider):
    headers = _register_and_login(client, "ws-missing@example.com")
    resp = client.post(f"{API}/workspaces/does-not-exist/message", json={"content": "hi"}, headers=headers)
    assert resp.status_code == 404, resp.text


def test_stream_failure_reports_error_and_resets_task(client, monkeypatch):
    _patch_provider(monkeypatch, _FailingProvider())
    headers = _register_and_login(client, "ws-fail@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "web_builder"}, headers=headers).json()

    resp = client.post(
        f"{API}/workspaces/{s['id']}/message", json={"content": "build it"}, headers=headers
    )
    assert resp.status_code == 200  # SSE opens fine; the failure is an in-band event
    assert '"type": "error"' in resp.text

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    # User turn persisted, but NO assistant message and NO artifact saved on failure.
    assert [m["role"] for m in full["messages"]] == ["user"]
    assert full["artifacts"] == []
    # The turn's task was not advanced to review (reset to backlog); session intact.
    assert all(t["status"] != "review" for t in full["tasks"])
    # No structured work merged from the failed turn (web_builder sessions start
    # with just {"mode": "new"}).
    assert not any(k in full["state"] for k in ("sitemap", "components", "images", "preview_html"))


def test_unauthorized_access_is_blocked(client, fake_provider):
    owner = _register_and_login(client, "ws-owner2@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "logo_design"}, headers=owner).json()
    other = _register_and_login(client, "ws-intruder@example.com")
    assert client.get(f"{API}/workspaces/{s['id']}", headers=other).status_code == 404
    assert (
        client.post(f"{API}/workspaces/{s['id']}/message", json={"content": "x"}, headers=other).status_code
        == 404
    )


# --- Structured-state robustness ------------------------------------------


def test_empty_block_triggers_structuring_fallback(client, monkeypatch):
    _patch_provider(monkeypatch, _EmptyBlockProvider())
    headers = _register_and_login(client, "ws-fallback@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "deep_research"}, headers=headers).json()

    resp = client.post(
        f"{API}/workspaces/{s['id']}/message", json={"content": "research it"}, headers=headers
    )
    assert resp.status_code == 200 and '"type": "done"' in resp.text

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    # The empty inline block yielded nothing, so the fallback pass reconstructed state.
    assert full["state"].get("plan") == [{"step": "scope the market", "status": "todo"}]
    # Saved assistant message is clean prose (no raw state block).
    assert "jarvis-state" not in full["messages"][1]["content"]
    assert "Research report body." in full["messages"][1]["content"]


def test_mislabeled_json_block_stripped_and_merged(client, monkeypatch):
    _patch_provider(monkeypatch, _MislabelProvider())
    headers = _register_and_login(client, "ws-mislabel@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "code_writer"}, headers=headers).json()

    resp = client.post(
        f"{API}/workspaces/{s['id']}/message", json={"content": "write code"}, headers=headers
    )
    assert resp.status_code == 200 and '"type": "error"' not in resp.text

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    files = full["state"].get("files", [])
    assert len(files) == 1 and files[0]["path"] == "a.py"
    # The mislabeled block was stripped from the SAVED transcript — no raw JSON leak.
    saved = full["messages"][1]["content"]
    assert "```json" not in saved and '"files"' not in saved
    assert saved.strip() == "Here is the code."


# --- Image generation success ---------------------------------------------


def test_image_generation_success_saves_artifact_and_state(client, monkeypatch):
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(workspaces, "get_image_provider", lambda: _FakeImageProvider())
    headers = _register_and_login(client, "ws-imgok@example.com")
    s = client.post(f"{API}/workspaces", json={"action": "logo_design"}, headers=headers).json()

    resp = client.post(
        f"{API}/workspaces/{s['id']}/image",
        json={"prompt": "a copper fox mark", "concept_id": "c1", "name": "Concept A"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["configured"] is True
    assert body["image"]["kind"] == "image"

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    imgs = full["state"].get("images", [])
    assert len(imgs) == 1 and imgs[0]["data_url"].startswith("data:image/png;base64,")
    assert imgs[0]["concept_id"] == "c1"
    assert any(a.get("kind") == "image" for a in full["artifacts"])


# --- Restart / session restore --------------------------------------------


def test_full_restore_after_turn(client, state_provider):
    """Simulates a restart: after a turn, a fresh GET rehydrates messages,
    artifacts, structured state, config, and tasks (all server-persisted)."""
    headers = _register_and_login(client, "ws-restore2@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    s = client.post(
        f"{API}/workspaces", json={"action": "web_builder", "company_id": company}, headers=headers
    ).json()
    client.post(f"{API}/workspaces/{s['id']}/message", json={"content": "plan the site"}, headers=headers)

    restored = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    assert [m["role"] for m in restored["messages"]] == ["user", "assistant"]
    assert restored["state"]["sitemap"] == [{"path": "/", "title": "Home"}]
    assert restored["config"]["key"] == "web_builder"
    assert len(restored["artifacts"]) == 1 and restored["artifacts"][0]["version"] == 1
    assert any(t["status"] == "review" for t in restored["tasks"])
    # And it still appears (company-scoped) in the recent switcher.
    recent = client.get(f"{API}/workspaces/recent?company_id={company}", headers=headers).json()
    assert any(r["id"] == s["id"] for r in recent)
