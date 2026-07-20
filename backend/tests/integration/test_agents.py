"""
Coverage for the AI Agent framework (app.core.agents + endpoints/agents.py).

The AI provider is monkeypatched with a scripted fake so runs are deterministic
and offline. We verify the framework contract: an agent run is persisted with a
full decision log, is workspace-scoped, can create Tasks/Projects and route
important actions through the approval queue, writes its outcome to AI Memory,
and both foreground (stream) and background execution work + restore.
"""
import pytest

from app.ai_providers.base import CompletionResult, ToolCall

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


class _ScriptedProvider:
    """Emits a fixed sequence of completions: first a batch of tool calls,
    then a final text answer (mirrors a real agentic loop, deterministically)."""

    supports_tools = True

    def __init__(self, tool_calls):
        self._tool_calls = tool_calls
        self._step = 0

    async def complete(self, *, messages=None, model=None, tools=None, **k):
        if self._step == 0 and self._tool_calls:
            self._step += 1
            return CompletionResult(
                text="Planning the work.",
                model="fake",
                provider="fake",
                tool_calls=self._tool_calls,
                content_blocks=[{"type": "text", "text": "Planning the work."}],
            )
        return CompletionResult(text="Done — here is the summary.", model="fake", provider="fake", tool_calls=[])

    async def stream(self, *a, **k):  # pragma: no cover - unused
        yield ""


def _patch_provider(monkeypatch, tool_calls):
    from app.core import agents

    monkeypatch.setattr(agents, "get_ai_provider", lambda name=None: _ScriptedProvider(tool_calls))


def test_list_agents(client):
    headers = _register_and_login(client, "agent-list@example.com")
    roster = client.get(f"{API}/agents", headers=headers).json()
    keys = {a["key"] for a in roster}
    assert keys == {"ceo", "marketing", "finance", "research", "operations"}
    # Every agent has memory + task/project tools available.
    for a in roster:
        assert "search_memory" in a["tools"] and "create_task" in a["tools"] and "create_project" in a["tools"]


def test_run_creates_task_scoped_to_workspace(client, monkeypatch):
    headers = _register_and_login(client, "agent-run@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    # The agent tries to create a task WITHOUT a company_id — the framework must
    # inject the run's workspace id (isolation), so the task lands in this company.
    _patch_provider(
        monkeypatch,
        [ToolCall(id="t1", name="create_task", input={"title": "Draft Q3 launch plan"})],
    )

    resp = client.post(
        f"{API}/agents/ceo/stream",
        json={"objective": "Plan the Q3 launch", "company_id": company},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert '"type": "tool_call"' in body and '"type": "done"' in body

    # A task was created in THIS company.
    tasks = client.get(f"{API}/companies/{company}/tasks", headers=headers).json()
    assert any(t["title"] == "Draft Q3 launch plan" for t in tasks)

    # The run is persisted with a full decision log.
    runs = client.get(f"{API}/agents/runs?company_id={company}", headers=headers).json()
    assert len(runs) == 1
    detail = client.get(f"{API}/agents/runs/{runs[0]['id']}", headers=headers).json()
    assert detail["status"] == "completed"
    kinds = [e["type"] for e in detail["reasoning_log"]]
    assert "tool_call" in kinds and "tool_result" in kinds and "reasoning" in kinds


def test_important_action_routes_to_approval(client, monkeypatch):
    headers = _register_and_login(client, "agent-approval@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    # Enable + permit the section-update capability so the propose call is
    # allowed (permission name is the ACTION name, not the tool name).
    granted = client.put(
        f"{API}/capabilities/business_data/config",
        json={"enabled": True, "permissions": ["update_company_section"], "company_id": company},
        headers=headers,
    )
    assert granted.status_code == 200, granted.text
    _patch_provider(
        monkeypatch,
        [
            ToolCall(
                id="p1",
                name="propose_update_company_section",
                input={"section": "marketing", "status": "in_progress", "notes": "kick off"},
            )
        ],
    )
    resp = client.post(
        f"{API}/agents/operations/stream",
        json={"objective": "Start the marketing workstream", "company_id": company},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # An approval was created — nothing was applied directly.
    approvals = client.get(f"{API}/approvals?company_id={company}&status=pending", headers=headers).json()
    assert any(a["capability_name"] == "business_data" for a in approvals)


def test_background_run_persists_and_restores(client, monkeypatch):
    headers = _register_and_login(client, "agent-bg@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    _patch_provider(
        monkeypatch,
        [ToolCall(id="pr1", name="create_project", input={"name": "New Initiative"})],
    )
    # TestClient runs BackgroundTasks synchronously after the response, so by the
    # time we poll, the background run has completed — exactly the restore path.
    start = client.post(
        f"{API}/agents/research/run",
        json={"objective": "Research the market", "company_id": company},
        headers=headers,
    )
    assert start.status_code == 202, start.text
    run_id = start.json()["id"]

    detail = client.get(f"{API}/agents/runs/{run_id}", headers=headers).json()
    assert detail["status"] == "completed"
    assert detail["result"]

    # Outcome captured to AI Memory for continuity.
    mem = client.get(f"{API}/memory?company_id={company}", headers=headers).json()
    assert any("Research Agent" in m["title"] for m in mem)


def test_unknown_agent_rejected(client):
    headers = _register_and_login(client, "agent-bad@example.com")
    resp = client.post(f"{API}/agents/nope/run", json={"objective": "x"}, headers=headers)
    assert resp.status_code == 422, resp.text
