"""
AI Command Center: every "Ask Jarvis" request routes itself to the right
subsystem, so the user never picks a tool manually.

The AI provider is monkeypatched (the fake echoes a canned destination keyed off
the request text), so these tests verify the ROUTING CONTRACT offline:
  * the user's example phrases land on the right destination + mode,
  * each decision carries the live status label and an explanation,
  * a clarifying question is passed through when the AI asks one,
  * unknown destinations and AI failures degrade to chat rather than erroring.
"""
API = "/api/v1"

# request substring -> what the fake AI answers with
_ANSWERS = {
    "landing page": "web_builder",
    "logo": "logo_design",
    "competitors": "deep_research",
    "new product": "product_creation",
    "email": "communications",
    "task": "task_manager",
    "project": "project_manager",
    "priorities": "executive_dashboard",
    "gmail": "gmail",
    "meeting": "calendar",
    "primal penni": "brand_brain",
    "launch": "work_queue",
    "banana": "not_a_real_destination",
}


class _FakeResult:
    def __init__(self, text):
        self.text = text
        self.tool_calls = []
        self.content_blocks = None


class _FakeProvider:
    async def complete(self, messages, **kwargs):
        request = messages[-1].content.lower()
        for needle, dest in _ANSWERS.items():
            if needle in request:
                return _FakeResult(
                    f'```json\n{{"destination":"{dest}","explanation":"On it.","clarifying_question":null}}\n```'
                )
        return _FakeResult('{"destination":"chat","explanation":"Answering directly.","clarifying_question":null}')


class _AskingProvider:
    async def complete(self, messages, **kwargs):
        return _FakeResult(
            '{"destination":"web_builder","explanation":"Starting a site.",'
            '"clarifying_question":"Which brand is this for?"}'
        )


class _BrokenProvider:
    async def complete(self, messages, **kwargs):
        raise RuntimeError("provider down")


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _patch(monkeypatch, provider):
    monkeypatch.setattr("app.core.command_center_service.get_ai_provider", lambda: provider)


def _route(client, headers, request, company_id=None):
    payload = {"request": request}
    if company_id:
        payload["company_id"] = company_id
    resp = client.post(f"{API}/command-center/route", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_routes_every_example_request_to_its_subsystem(client, monkeypatch):
    _patch(monkeypatch, _FakeProvider())
    headers = _login(client, "cc-route@example.com")
    company = client.post(f"{API}/companies", json={"name": "Primal Penni"}, headers=headers).json()["id"]

    cases = [
        ("Build me a landing page", "web_builder", "studio"),
        ("Create a logo", "logo_design", "studio"),
        ("Research competitors", "deep_research", "studio"),
        ("Design a new product", "product_creation", "studio"),
        ("Write an email to the supplier", "communications", "chat"),
        ("Create a task for tomorrow", "task_manager", "chat"),
        ("Start a new project", "project_manager", "chat"),
        ("Show today's priorities", "executive_dashboard", "navigate"),
        ("Summarize Gmail", "gmail", "chat"),
        ("Schedule a meeting", "calendar", "chat"),
        ("Analyze Primal Penni", "brand_brain", "navigate"),
    ]
    for request, destination, mode in cases:
        decision = _route(client, headers, request, company)
        assert decision["destination"] == destination, f"{request!r} -> {decision}"
        assert decision["mode"] == mode
        assert decision["status"] and decision["explanation"]
        assert decision["clarifying_question"] is None


def test_multi_step_request_routes_to_work_queue(client, monkeypatch):
    _patch(monkeypatch, _FakeProvider())
    headers = _login(client, "cc-multi@example.com")
    decision = _route(client, headers, "Plan the spring launch end to end")
    assert decision["destination"] == "work_queue"
    assert decision["mode"] == "work_queue"
    assert decision["target"] == "/company/work-queue"


def test_clarifying_question_is_passed_through(client, monkeypatch):
    _patch(monkeypatch, _AskingProvider())
    headers = _login(client, "cc-ask@example.com")
    decision = _route(client, headers, "Build something")
    assert decision["destination"] == "web_builder"
    assert decision["clarifying_question"] == "Which brand is this for?"


def test_unknown_destination_and_ai_failure_fall_back_to_chat(client, monkeypatch):
    headers = _login(client, "cc-fallback@example.com")

    _patch(monkeypatch, _FakeProvider())
    assert _route(client, headers, "banana")["destination"] == "chat"

    _patch(monkeypatch, _BrokenProvider())
    decision = _route(client, headers, "anything at all")
    assert decision["destination"] == "chat"
    assert decision["mode"] == "chat"
    assert decision["explanation"]


def test_destination_catalog_is_exposed(client, monkeypatch):
    headers = _login(client, "cc-catalog@example.com")
    resp = client.get(f"{API}/command-center/destinations", headers=headers)
    assert resp.status_code == 200
    keys = {d["key"] for d in resp.json()}
    assert {"web_builder", "task_manager", "work_queue", "chat"} <= keys


def test_route_requires_auth(client):
    assert client.post(f"{API}/command-center/route", json={"request": "hi"}).status_code in (401, 403)
