"""
The Approval Center: one queue for every real-world action, with enough
information to decide, and the machinery to carry out what's approved.

Verified here (AI provider monkeypatched, so it's offline + deterministic):
  * every request carries a decision brief — summary, expected outcome, risks,
    undo — including rows proposed before the brief existed,
  * the proposer's `reason` survives onto the request,
  * edit-then-approve changes what runs, and the audit trail keeps the original,
  * a multi-step plan is grouped into one queue entry, in execution order,
  * approving a plan approves AND executes its steps in sequence,
  * a rejected step re-plans the rest of the work instead of dying,
  * the queue is database-backed, so it survives a restart,
  * every decision lands in the audit log and in workspace history.
"""
import json

API = "/api/v1"


class _FakeResult:
    def __init__(self, text):
        self.text = text
        self.tool_calls = []
        self.content_blocks = None


class _FakeProvider:
    """Plans two steps (one internal, one real-world), and re-plans to a single
    safe alternative step when asked."""

    async def complete(self, messages, **kwargs):
        system = messages[0].content if messages else ""
        if "re-planning" in system:
            return _FakeResult(
                '{"subtasks":[{"title":"Draft a written reorder request for review","real_world":false,'
                '"why":"Keeps the goal moving without sending anything."}]}'
            )
        if "planner" in system:
            return _FakeResult(
                '{"subtasks":['
                '{"title":"Research competitor pricing","real_world":false,"why":"Grounds the reorder size."},'
                '{"title":"Email the supplier a reorder","real_world":true,'
                '"why":"The supplier needs the order to ship in time for spring."}]}'
            )
        return _FakeResult("Work product for the step.")


def _patch(monkeypatch):
    monkeypatch.setattr("app.core.work_queue_service.get_ai_provider", lambda: _FakeProvider())


def _login(client, email):
    client.post(f"{API}/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "supersecret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _company(client, headers, name="Primal Penni"):
    return client.post(f"{API}/companies", json={"name": name}, headers=headers).json()["id"]


def _plan_and_run(client, headers, company):
    """A work run whose real-world step lands in the Approval Center."""
    run = client.post(
        f"{API}/work-queue", json={"request": "Prep a spring reorder", "company_id": company}, headers=headers
    ).json()
    client.post(f"{API}/work-queue/{run['id']}/stream", headers=headers)
    return run


def _grant(client, headers, capability, permissions, company_id):
    return client.put(
        f"{API}/capabilities/{capability}/config",
        json={"enabled": True, "permissions": permissions, "company_id": company_id},
        headers=headers,
    )


# --- The brief -------------------------------------------------------------


def test_every_request_explains_itself(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-brief@example.com")
    company = _company(client, headers)
    _plan_and_run(client, headers, company)

    queue = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()
    step = queue["plans"][0]["steps"][0]
    assert step["summary"]
    assert step["expected_outcome"]
    assert step["risks"] and isinstance(step["risks"], list)
    assert step["undo_plan"]
    # The planner's own justification survives onto the request.
    assert "spring" in (step["reason"] or "").lower()


def test_brief_is_derived_for_a_request_that_never_stored_one(client, monkeypatch):
    """Approvals proposed before the Approval Center existed have no stored
    brief — it's rebuilt on read, so nothing in the queue is undecidable."""
    headers = _login(client, "ac-legacy@example.com")
    company = _company(client, headers)

    from app.db.models.capability import ApprovalRequest
    from app.db.session import SessionLocal
    from app.db.models.company import Company

    db = SessionLocal()
    try:
        owner_id = db.query(Company).filter(Company.id == company).first().owner_id
        db.add(
            ApprovalRequest(
                owner_id=owner_id,
                company_id=company,
                capability_name="email",
                action_type="send",
                payload_json=json.dumps({"to": "supplier@example.com", "subject": "Reorder"}),
                status="pending",
            )
        )
        db.commit()
    finally:
        db.close()

    item = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["standalone"][0]
    assert "supplier@example.com" in item["summary"]
    assert "receives this email" in item["expected_outcome"]
    assert any("cannot be recalled" in r or "real person" in r for r in item["risks"])
    assert "cannot be undone" in item["undo_plan"].lower()


# --- Edit then approve -----------------------------------------------------


def test_edit_then_approve_changes_what_runs_and_keeps_the_original(client, monkeypatch):
    headers = _login(client, "ac-edit@example.com")
    company = _company(client, headers)
    _grant(client, headers, "email", ["send"], company)
    proposed = client.post(
        f"{API}/approvals",
        json={
            "capability_name": "email",
            "action_type": "send",
            "payload": {"to": "wrong@example.com", "subject": "Reorder"},
            "company_id": company,
        },
        headers=headers,
    ).json()

    edited = client.post(
        f"{API}/approvals/{proposed['id']}/edit",
        json={"payload": {"to": "right@example.com", "subject": "Reorder — revised"}},
        headers=headers,
    ).json()
    assert edited["payload"]["to"] == "right@example.com"
    # The brief is rebuilt so it describes what will actually happen now.
    assert "right@example.com" in edited["summary"]

    audit = client.get(f"{API}/approvals/{proposed['id']}/audit", headers=headers).json()
    edit_row = next(a for a in audit if a["action"] == "edited")
    assert edit_row["before"]["payload"]["to"] == "wrong@example.com"
    assert edit_row["after"]["payload"]["to"] == "right@example.com"


def test_approve_can_edit_in_the_same_decision(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-editapprove@example.com")
    company = _company(client, headers)
    _plan_and_run(client, headers, company)
    step = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["plans"][0]["steps"][0]

    decided = client.post(
        f"{API}/approvals/{step['id']}/approve",
        json={"payload": {**step["payload"], "title": "Email the supplier a SMALLER reorder"}, "note": "Trimmed"},
        headers=headers,
    ).json()
    assert decided["payload"]["title"].endswith("SMALLER reorder")
    assert decided["status"] in ("approved", "executed")


# --- Plans -----------------------------------------------------------------


def test_plan_steps_are_grouped_in_execution_order(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-plan@example.com")
    company = _company(client, headers)
    run = _plan_and_run(client, headers, company)

    queue = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()
    assert len(queue["plans"]) == 1
    plan = queue["plans"][0]
    assert plan["group_id"] == run["id"]
    assert plan["label"] == "Prep a spring reorder"
    assert plan["pending_steps"] == 1
    assert [s["sequence"] for s in plan["steps"]] == sorted(s["sequence"] for s in plan["steps"])
    assert queue["pending_count"] == 1


def test_approving_a_plan_executes_its_steps_in_sequence(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-planapprove@example.com")
    company = _company(client, headers)
    run = _plan_and_run(client, headers, company)

    result = client.post(f"{API}/approvals/plans/{run['id']}/approve", json={"note": "Go"}, headers=headers).json()
    assert result["decided"] == 1
    assert result["stopped_at"] is None
    # The work_queue executor ran: the step is executed, not merely approved.
    assert result["steps"][0]["status"] == "executed"
    # And the plan itself moved on.
    final = client.get(f"{API}/work-queue/{run['id']}", headers=headers).json()
    assert final["status"] == "completed"
    assert all(s["status"] == "complete" for s in final["subtasks"])
    # Nothing left waiting.
    assert client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["pending_count"] == 0


def test_rejecting_a_step_replans_the_remaining_work(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-reject@example.com")
    company = _company(client, headers)
    run = _plan_and_run(client, headers, company)
    step = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["plans"][0]["steps"][0]

    rejected = client.post(
        f"{API}/approvals/{step['id']}/reject",
        json={"note": "Don't contact the supplier yet."},
        headers=headers,
    ).json()
    assert rejected["status"] == "rejected"
    assert rejected["replan"]["replanned"] is True
    assert "Draft a written reorder request for review" in rejected["replan"]["new_steps"]

    # The rejection is recorded on the run, and the safe alternative is queued.
    final = client.get(f"{API}/work-queue/{run['id']}", headers=headers).json()
    titles = [s["title"] for s in final["subtasks"]]
    assert "Draft a written reorder request for review" in titles


# --- Durability, isolation, and the record ---------------------------------


def test_queue_survives_a_restart(client, monkeypatch):
    """The queue is the database, not client state: a brand-new session (as
    after a refresh or an app restart) sees exactly the same pending work."""
    _patch(monkeypatch)
    headers = _login(client, "ac-durable@example.com")
    company = _company(client, headers)
    _plan_and_run(client, headers, company)
    before = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()

    fresh = _login(client, "ac-durable@example.com")  # new token, new session
    after = client.get(f"{API}/approvals/queue?company_id={company}", headers=fresh).json()
    assert after["pending_count"] == before["pending_count"] == 1
    assert after["plans"][0]["steps"][0]["id"] == before["plans"][0]["steps"][0]["id"]


def test_decisions_are_written_to_audit_log_and_workspace_history(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-record@example.com")
    company = _company(client, headers)
    run = _plan_and_run(client, headers, company)
    step = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["plans"][0]["steps"][0]
    client.post(f"{API}/approvals/{step['id']}/approve", json={"note": "Approved for spring"}, headers=headers)

    audit = client.get(f"{API}/approvals/{step['id']}/audit", headers=headers).json()
    assert {"proposed", "approved", "executed"} <= {a["action"] for a in audit}

    # Workspace history: the decision is searchable from the workspace itself.
    memories = client.get(f"{API}/memory?company_id={company}", headers=headers).json()
    assert any(m["source"] == "approval_center" and "Approval approved" in m["title"] for m in memories)

    # And it shows up in the decided-history view, not the pending queue.
    history = client.get(f"{API}/approvals/history?company_id={company}", headers=headers).json()
    assert any(h["id"] == step["id"] for h in history)
    assert run["id"] in {h["group_id"] for h in history}


def test_queue_is_scoped_to_its_own_workspace_and_owner(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-scope@example.com")
    penni = _company(client, headers, "Primal Penni")
    greener = _company(client, headers, "Greener Capitol")
    _plan_and_run(client, headers, penni)

    assert client.get(f"{API}/approvals/queue?company_id={greener}", headers=headers).json()["pending_count"] == 0

    stranger = _login(client, "ac-stranger@example.com")
    assert client.get(f"{API}/approvals/queue?company_id={penni}", headers=stranger).json()["pending_count"] == 0


def test_a_decided_request_cannot_be_decided_again(client, monkeypatch):
    _patch(monkeypatch)
    headers = _login(client, "ac-double@example.com")
    company = _company(client, headers)
    _plan_and_run(client, headers, company)
    step = client.get(f"{API}/approvals/queue?company_id={company}", headers=headers).json()["plans"][0]["steps"][0]

    client.post(f"{API}/approvals/{step['id']}/approve", json={}, headers=headers)
    again = client.post(f"{API}/approvals/{step['id']}/approve", json={}, headers=headers)
    assert again.status_code == 422


# --- One approval, one execution ------------------------------------------


async def test_a_double_tap_decides_once(client):
    """Two taps on a phone arrive as two requests. The second must not run the
    action again — for a storefront write that would be two live changes."""
    import asyncio as _asyncio

    from app.core import approval_center_service, capability_executors
    from app.db.models.user import User
    from app.db.session import SessionLocal

    headers = _login(client, "double-tap@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    _grant(client, headers, "email", ["send"], company)
    me = client.get(f"{API}/auth/me", headers=headers).json()

    runs: list[str] = []

    async def slow_executor(_db, *, owner_id, company_id, action_type, payload):
        # Long enough that a second decision would overlap it.
        await _asyncio.sleep(0.05)
        runs.append(action_type)
        return {"ok": True}

    original = capability_executors._EXECUTORS.get("email")
    capability_executors.register_executor("email", slow_executor)
    try:
        req = client.post(
            f"{API}/approvals",
            json={"capability_name": "email", "action_type": "send",
                  "payload": {"product": "X", "quantity": 1}, "company_id": company},
            headers=headers,
        ).json()

        db_a, db_b = SessionLocal(), SessionLocal()
        try:
            owner = db_a.query(User).filter(User.id == me["id"]).first().id
            results = await _asyncio.gather(
                approval_center_service.decide(db_a, owner_id=owner, request_id=req["id"], approve=True),
                approval_center_service.decide(db_b, owner_id=owner, request_id=req["id"], approve=True),
                return_exceptions=True,
            )
        finally:
            db_a.close()
            db_b.close()
    finally:
        if original:
            capability_executors.register_executor("email", original)
        else:
            capability_executors._EXECUTORS.pop("email", None)

    assert len(runs) == 1, f"the action ran {len(runs)} times"
    assert sum(1 for r in results if isinstance(r, Exception)) == 1  # the loser was told, not silently dropped


def test_the_deciding_device_is_recorded(client):
    """The queue is open on the phone and the desktop; the audit has to say
    which one the decision came from."""
    headers = _login(client, "device-audit@example.com")
    company = client.post(f"{API}/companies", json={"name": "SPN Group LLC"}, headers=headers).json()["id"]
    _grant(client, headers, "email", ["send"], company)
    req = client.post(
        f"{API}/approvals",
        json={"capability_name": "email", "action_type": "send",
              "payload": {"to": "a@b.com", "subject": "s", "body": "b"}, "company_id": company},
        headers=headers,
    ).json()

    client.post(
        f"{API}/approvals/{req['id']}/reject",
        json={},
        headers={**headers, "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari"},
    )
    trail = client.get(f"{API}/approvals/{req['id']}/audit", headers=headers).json()
    assert any("iPhone" in (row.get("note") or "") for row in trail), trail
