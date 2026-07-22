"""
Autonomous Work Queue: decompose a request into subtasks, work through them
with approval-gated autonomy, and stream state changes.

The AI provider is monkeypatched, so tests are offline + deterministic. What's
verified:
  * a request is decomposed into ordered subtasks (Planned),
  * executing runs internal subtasks to Complete (with a work product),
  * a real-world subtask stops at waiting_approval and creates a real approval,
  * the run reports "waiting" while an approval is outstanding,
  * everything is workspace-scoped.
"""
import json

API = "/api/v1"


class _FakeResult:
    def __init__(self, text):
        self.text = text
        self.tool_calls = []
        self.content_blocks = None


class _FakeProvider:
    async def complete(self, messages, **kwargs):
        system = messages[0].content if messages else ""
        if "planner" in system:
            return _FakeResult(
                '{"subtasks":[{"title":"Research competitor pricing","real_world":false},'
                '{"title":"Email the supplier a reorder","real_world":true}]}'
            )
        return _FakeResult("Completed work product for the subtask.")


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name):
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def _patch_ai(monkeypatch):
    monkeypatch.setattr("app.core.work_queue_service.get_ai_provider", lambda: _FakeProvider())


def test_plan_decomposes_into_subtasks(client, monkeypatch):
    _patch_ai(monkeypatch)
    headers = _login(client, "wq-plan@example.com")
    company = _company(client, headers, "Primal Penni")
    resp = client.post(f"{API}/work-queue", json={"request": "Prep a reorder", "company_id": company}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "planned"
    assert len(body["subtasks"]) == 2
    assert all(s["status"] == "planned" for s in body["subtasks"])
    assert body["subtasks"][0]["real_world"] is False
    assert body["subtasks"][1]["real_world"] is True


def test_execute_runs_internal_and_gates_real_world(client, monkeypatch):
    _patch_ai(monkeypatch)
    headers = _login(client, "wq-exec@example.com")
    company = _company(client, headers, "Primal Penni")
    run = client.post(f"{API}/work-queue", json={"request": "Prep a reorder", "company_id": company}, headers=headers).json()

    # Stream execution — TestClient returns the full SSE body.
    stream = client.post(f"{API}/work-queue/{run['id']}/stream", headers=headers)
    assert stream.status_code == 200, stream.text
    events = [json.loads(line[len("data: "):]) for line in stream.text.splitlines() if line.startswith("data: ")]
    statuses = {(e.get("id"), e.get("status")) for e in events if e.get("type") == "subtask"}
    assert any(s == "complete" for _, s in statuses)
    assert any(s == "waiting_approval" for _, s in statuses)
    assert events[-1] == {"type": "done", "status": "waiting"}

    # Final state: one complete (with a work product), one waiting for approval.
    final = client.get(f"{API}/work-queue/{run['id']}", headers=headers).json()
    assert final["status"] == "waiting"
    internal = next(s for s in final["subtasks"] if not s["real_world"])
    realworld = next(s for s in final["subtasks"] if s["real_world"])
    assert internal["status"] == "complete" and internal["result"]
    assert realworld["status"] == "waiting_approval" and realworld["approval_id"]

    # The real-world step created a real, pending approval in this workspace.
    approvals = client.get(f"{API}/approvals?company_id={company}&status=pending", headers=headers).json()
    assert any(a["capability_name"] == "work_queue" for a in approvals)


def test_work_run_scoped_to_owner(client, monkeypatch):
    _patch_ai(monkeypatch)
    a = _login(client, "wq-a@example.com")
    b = _login(client, "wq-b@example.com")
    company = _company(client, a, "Primal Penni")
    run = client.post(f"{API}/work-queue", json={"request": "x", "company_id": company}, headers=a).json()
    assert client.get(f"{API}/work-queue/{run['id']}", headers=b).status_code == 404
