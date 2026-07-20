"""
Coverage for the Capability framework (app.core.capability_service +
api/v1/endpoints/capabilities.py) — the shared approval queue, audit log,
company-scoped permissions, and health checks every external-service
capability (Gmail, Calendar, Shopify, ...) is meant to plug into instead of
rebuilding this machinery per integration.

Same pattern as the rest of the suite — real HTTP calls via TestClient
against a real (test) SQLite database. "email" (Gmail) now has a real
executor wired in (see app.core.gmail_service), so the one test that
exercises a full propose -> approve -> execute cycle without any real
credentials connected uses "shopify" instead — still a pure stub with no
registered executor, which is exactly what that test needs to isolate the
framework's own generic behavior. Everything else below uses "email" only
for permission/company-isolation/error-path checks that never reach an
executor either way. "google_calendar" is used specifically to prove
capabilities can be registered ahead of their integration existing (see
test_health_check_on_unimplemented_integration_reports_error_not_500).
"""
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


def _grant(client, headers: dict, capability: str, permissions: list[str], company_id: str | None = None, enabled: bool = True) -> dict:
    resp = client.put(
        f"{API}/capabilities/{capability}/config",
        json={"enabled": enabled, "permissions": permissions, "company_id": company_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _propose(client, headers: dict, capability: str, action_type: str, payload: dict, company_id: str | None = None) -> dict:
    resp = client.post(
        f"{API}/approvals",
        json={"capability_name": capability, "action_type": action_type, "payload": payload, "company_id": company_id},
        headers=headers,
    )
    return resp


# ---------------------------------------------------------------------------
# Full propose -> approve -> execute lifecycle
# ---------------------------------------------------------------------------


def test_propose_approve_execute_flow(client):
    """Uses "shopify" deliberately — it has no registered executor (unlike
    "email"/Gmail now), so approving here exercises capability_service's
    own generic behavior (stays 'approved' until something else finishes
    the loop) rather than a real integration call."""
    headers = _register_and_login(client, "cap-lifecycle@example.com")
    company = _create_company(client, headers, "LifecycleCo")
    _grant(client, headers, "shopify", ["list_orders", "list_inventory", "refund_order"], company_id=company)

    resp = _propose(client, headers, "shopify", "refund_order", {"order_id": "1001", "amount": "19.99"}, company)
    assert resp.status_code == 201, resp.text
    req = resp.json()
    assert req["status"] == "pending"

    approve_resp = client.post(f"{API}/approvals/{req['id']}/approve", json={"note": "looks good"}, headers=headers)
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    executed_resp = client.post(f"{API}/approvals/{req['id']}/executed", json={"note": "refunded via Shopify admin"}, headers=headers)
    assert executed_resp.status_code == 200, executed_resp.text
    assert executed_resp.json()["status"] == "executed"

    audit = client.get(
        f"{API}/capabilities/audit-log", params={"capability_name": "shopify", "company_id": company}, headers=headers
    ).json()
    actions = [a["action"] for a in audit]
    assert "proposed" in actions
    assert "approved" in actions
    assert "executed" in actions


def test_reject_flow_and_rejected_cannot_be_approved_later(client):
    headers = _register_and_login(client, "cap-reject@example.com")
    company = _create_company(client, headers, "RejectCo")
    _grant(client, headers, "email", ["send"], company_id=company)

    resp = _propose(client, headers, "email", "send", {"to": "x@y.com"}, company)
    req = resp.json()

    reject_resp = client.post(f"{API}/approvals/{req['id']}/reject", json={"note": "not now"}, headers=headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # A rejected request is no longer pending — approving it later is a
    # validation error, not a silent no-op.
    second_approve = client.post(f"{API}/approvals/{req['id']}/approve", json={}, headers=headers)
    assert second_approve.status_code == 422


def test_mark_executed_requires_approved_status(client):
    headers = _register_and_login(client, "cap-exec-order@example.com")
    company = _create_company(client, headers, "ExecOrderCo")
    _grant(client, headers, "email", ["send"], company_id=company)

    req = _propose(client, headers, "email", "send", {"to": "x@y.com"}, company).json()
    resp = client.post(f"{API}/approvals/{req['id']}/executed", json={}, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Permission + enable/disable gating (both must pass before approval matters)
# ---------------------------------------------------------------------------


def test_action_not_permitted_by_default_cannot_be_proposed(client):
    """send requires_approval=True and is NOT in default_permissions
    (write actions are an explicit opt-in, on top of the per-call approval
    gate) — proposing it before granting permission must fail."""
    headers = _register_and_login(client, "cap-default-perms@example.com")
    company = _create_company(client, headers, "DefaultPermsCo")

    resp = _propose(client, headers, "email", "send", {"to": "x@y.com"}, company)
    assert resp.status_code == 403


def test_disabled_capability_blocks_proposal_even_with_permission(client):
    headers = _register_and_login(client, "cap-disabled@example.com")
    company = _create_company(client, headers, "DisabledCo")
    _grant(client, headers, "email", ["send"], company_id=company, enabled=False)

    resp = _propose(client, headers, "email", "send", {"to": "x@y.com"}, company)
    assert resp.status_code == 403


def test_read_only_action_cannot_be_proposed_for_approval(client):
    headers = _register_and_login(client, "cap-read-not-proposable@example.com")
    company = _create_company(client, headers, "ReadNotProposableCo")

    resp = _propose(client, headers, "email", "list_messages", {}, company)
    assert resp.status_code == 422


def test_unknown_action_type_rejected(client):
    headers = _register_and_login(client, "cap-unknown-action@example.com")
    resp = _propose(client, headers, "email", "not_a_real_action", {})
    assert resp.status_code == 422


def test_unknown_capability_name_rejected(client):
    headers = _register_and_login(client, "cap-unknown-capability@example.com")
    resp = client.get(f"{API}/capabilities/not_a_real_capability", headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Company isolation
# ---------------------------------------------------------------------------


def test_capability_config_isolated_per_company(client):
    headers = _register_and_login(client, "cap-company-isolation@example.com")
    company_a = _create_company(client, headers, "PermsCoA")
    company_b = _create_company(client, headers, "PermsCoB")
    _grant(client, headers, "email", ["send"], company_id=company_a)

    cfg_a = client.get(f"{API}/capabilities/email", params={"company_id": company_a}, headers=headers).json()
    cfg_b = client.get(f"{API}/capabilities/email", params={"company_id": company_b}, headers=headers).json()

    assert "send" in cfg_a["permissions"]
    assert "send" not in cfg_b["permissions"]

    # Proposing under company B still requires B's own grant, even though A
    # already has one — permissions never leak across companies.
    resp = _propose(client, headers, "email", "send", {"to": "x@y.com"}, company_b)
    assert resp.status_code == 403


def test_cannot_approve_or_reject_someone_elses_request(client):
    owner_headers = _register_and_login(client, "cap-owner@example.com")
    other_headers = _register_and_login(client, "cap-other@example.com")
    company = _create_company(client, owner_headers, "IsolatedApprovalCo")
    _grant(client, owner_headers, "email", ["send"], company_id=company)

    req = _propose(client, owner_headers, "email", "send", {"to": "x@y.com"}, company).json()

    approve_resp = client.post(f"{API}/approvals/{req['id']}/approve", json={}, headers=other_headers)
    assert approve_resp.status_code == 404

    reject_resp = client.post(f"{API}/approvals/{req['id']}/reject", json={}, headers=other_headers)
    assert reject_resp.status_code == 404


def test_approvals_list_isolated_across_users(client):
    a = _register_and_login(client, "cap-list-a@example.com")
    b = _register_and_login(client, "cap-list-b@example.com")
    company = _create_company(client, a, "ListIsolationCo")
    _grant(client, a, "email", ["send"], company_id=company)
    _propose(client, a, "email", "send", {"to": "x@y.com"}, company)

    b_view = client.get(f"{API}/approvals", params={"company_id": "any"}, headers=b).json()
    assert b_view == []


def test_cannot_propose_action_against_someone_elses_company(client):
    owner_headers = _register_and_login(client, "cap-company-owner@example.com")
    other_headers = _register_and_login(client, "cap-company-other@example.com")
    owners_company = _create_company(client, owner_headers, "NotYoursForCapabilities")

    resp = _propose(client, other_headers, "email", "send", {"to": "x@y.com"}, owners_company)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Health checks — including capabilities registered ahead of their
# integration actually being implemented (see capabilities_registry.py)
# ---------------------------------------------------------------------------


def test_health_check_known_integration_without_credentials_is_disconnected(client):
    headers = _register_and_login(client, "cap-health-disconnected@example.com")
    for cap in ("email", "google_calendar"):
        resp = client.post(f"{API}/capabilities/{cap}/health-check", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["health_status"] == "disconnected", cap


def test_health_check_on_unimplemented_integration_reports_error_not_500(client):
    """slack is registered in capabilities_registry (so it can be built later
    without touching this framework) but has no matching entry in
    app.integrations.registry yet — the health check must degrade to a
    reported 'error' status, not crash the endpoint.

    (google_calendar used to be the example here; it now has a real
    integration class, so it reports 'disconnected' — see the test above.)"""
    headers = _register_and_login(client, "cap-health-unimplemented@example.com")
    resp = client.post(f"{API}/capabilities/slack/health-check", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["health_status"] == "error"


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------


def test_scheduled_job_requires_permitted_action(client):
    headers = _register_and_login(client, "cap-schedule-perms@example.com")
    company = _create_company(client, headers, "SchedulePermsCo")

    resp = client.post(
        f"{API}/scheduled-jobs",
        json={"capability_name": "email", "action_type": "send", "schedule_cron": "0 8 * * *", "company_id": company},
        headers=headers,
    )
    assert resp.status_code == 403

    _grant(client, headers, "email", ["send"], company_id=company)
    resp2 = client.post(
        f"{API}/scheduled-jobs",
        json={"capability_name": "email", "action_type": "send", "schedule_cron": "0 8 * * *", "company_id": company},
        headers=headers,
    )
    assert resp2.status_code == 201, resp2.text
    job = resp2.json()
    assert job["enabled"] is True

    disabled = client.put(f"{API}/scheduled-jobs/{job['id']}", json={"enabled": False}, headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    delete_resp = client.delete(f"{API}/scheduled-jobs/{job['id']}", headers=headers)
    assert delete_resp.status_code == 204

    remaining = client.get(f"{API}/scheduled-jobs", params={"company_id": company}, headers=headers).json()
    assert remaining == []
