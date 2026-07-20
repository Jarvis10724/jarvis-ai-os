"""
Orchestration layer between Gmail's HTTP endpoints and the lower-level
pieces: credential_store (encrypted, company-scoped tokens),
capability_service (the permission/approval/audit gate), and
EmailIntegration (the real Gmail API calls). Every Gmail action funnels
through here — endpoints never touch credential_store or EmailIntegration
directly, and capability_service never has to know anything Gmail-specific.

Read (list/search/get) and draft creation execute immediately — see
`authorize_direct_action` calls below. Send/forward/trash/archive/label
changes only ever run through `execute_action`, called by
capability_executors.execute_if_registered() after a human has approved
the corresponding ApprovalRequest; the `propose_*` functions below only
create that pending request; they never touch the Gmail API themselves.
"""
from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.core import capability_service, credential_store
from app.core.capability_executors import register_executor
from app.exceptions import ValidationError
from app.integrations.email_integration import EmailIntegration

CAPABILITY_NAME = "email"


def _load_integration(db, *, owner_id: str, company_id: str | None) -> EmailIntegration:
    creds = credential_store.load_credentials(db, owner_id=owner_id, company_id=company_id, provider=CAPABILITY_NAME)
    if not creds or not creds.get("access_token"):
        raise ValidationError("Gmail is not connected for this company yet — connect it from Integrations first.")
    return EmailIntegration(credentials=creds)


async def _call(db, owner_id: str, company_id: str | None, integration: EmailIntegration, method_name: str, **kwargs):
    """Every real Gmail call goes through here so a refreshed access token
    (EmailIntegration._request refreshes in-memory on a 401 but can't
    persist it itself — it has no db session) gets written back via
    credential_store exactly once, right after the call that triggered it."""
    method = getattr(integration, method_name)
    result = await method(**kwargs)
    if integration.refreshed_access_token:
        credential_store.save_credentials(
            db,
            owner_id=owner_id,
            company_id=company_id,
            provider=CAPABILITY_NAME,
            access_token=integration.refreshed_access_token,
        )
    return result


# ---------------------------------------------------------------------------
# Direct actions — read + draft, no approval needed
# ---------------------------------------------------------------------------


async def list_messages(
    db, *, owner_id: str, company_id: str | None, max_results: int = 10, query: str = "", unread_only: bool = False
) -> list[dict]:
    """Powers 'read inbox' (query="", unread_only=False) and 'search
    emails' (query="from:x", "has:attachment", etc. — Gmail search syntax
    passed straight through) alike; both are the same underlying call."""
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="list_messages", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)
    if unread_only:
        result = await _call(db, owner_id, company_id, integration, "list_unread", max_results=max_results)
    else:
        result = await _call(db, owner_id, company_id, integration, "list_messages", max_results=max_results, query=query)
    capability_service.log_capability_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="list_messages",
        company_id=company_id,
        result={"count": len(result.data)},
    )
    return result.data


async def get_message(db, *, owner_id: str, company_id: str | None, message_id: str) -> dict:
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="get_message", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)
    result = await _call(db, owner_id, company_id, integration, "get_message", message_id=message_id)
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="get_message", company_id=company_id, note=message_id
    )
    return result.data


async def summarize(
    db, *, owner_id: str, company_id: str | None, message_id: str | None = None, max_results: int = 10
) -> dict:
    """Summarizes one message (message_id given) or a prioritized digest of
    unread messages (message_id omitted) via the existing AI provider
    abstraction. Read-only in effect — never mutates the mailbox — so it's
    a direct action, same as list/get."""
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="summarize", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)

    if message_id:
        detail = (await _call(db, owner_id, company_id, integration, "get_message", message_id=message_id)).data
        source_text = f"From: {detail.get('from')}\nSubject: {detail.get('subject')}\n\n{detail.get('body')}"
        prompt = "Summarize this email in 2-3 sentences. Note anything that needs a reply or action."
        count = 1
    else:
        messages = (await _call(db, owner_id, company_id, integration, "list_unread", max_results=max_results)).data
        count = len(messages)
        if not messages:
            capability_service.log_capability_action(
                db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="summarize", company_id=company_id,
                result={"count": 0},
            )
            return {"summary": "No unread messages.", "count": 0}
        source_text = "\n\n".join(
            f"From: {m['from']}\nSubject: {m['subject']}\nSnippet: {m['snippet']}" for m in messages
        )
        prompt = f"Summarize these {count} unread emails as a short, prioritized digest — what needs attention first, and why."

    provider = get_ai_provider()
    result = await provider.complete(
        messages=[
            Message(role="system", content="You are Jarvis, summarizing email for a busy founder."),
            Message(role="user", content=f"{prompt}\n\n{source_text}"),
        ],
        temperature=0.3,
        max_tokens=600,
    )
    capability_service.log_capability_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="summarize",
        company_id=company_id,
        result={"provider": result.provider, "count": count},
    )
    return {"summary": result.text, "count": count}


async def create_draft(
    db,
    *,
    owner_id: str,
    company_id: str | None,
    to: str | None = None,
    subject: str | None = None,
    body: str,
    thread_id: str | None = None,
    reply_to_message_id: str | None = None,
) -> dict:
    """`reply_to_message_id` (a Gmail message id, not an RFC822 header) is
    how 'draft a reply to message X' is expressed — the real In-Reply-To/
    References headers are pulled from the original message so threading
    works without the caller needing to know Gmail's header format."""
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="draft", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)
    if reply_to_message_id:
        result = await _call(
            db, owner_id, company_id, integration, "draft_reply", message_id=reply_to_message_id, body=body
        )
    else:
        if not to or not subject:
            raise ValidationError("A new (non-reply) draft requires 'to' and 'subject'.")
        result = await _call(
            db, owner_id, company_id, integration, "create_draft", to=to, subject=subject, body=body, thread_id=thread_id
        )
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="draft", company_id=company_id, result=result.data
    )
    return result.data


# ---------------------------------------------------------------------------
# Approval-gated actions — propose only; execution happens post-approval
# ---------------------------------------------------------------------------


def propose_send(
    db, *, owner_id: str, company_id: str | None, to: str, subject: str, body: str,
    thread_id: str | None = None, in_reply_to: str | None = None,
) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)  # fail fast if Gmail isn't even connected
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="send",
        payload={"to": to, "subject": subject, "body": body, "thread_id": thread_id, "in_reply_to": in_reply_to},
        company_id=company_id,
        requested_by=owner_id,
    )


def propose_forward(db, *, owner_id: str, company_id: str | None, message_id: str, to: str, note: str = "") -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="forward",
        payload={"message_id": message_id, "to": to, "note": note},
        company_id=company_id,
        requested_by=owner_id,
    )


def propose_trash(db, *, owner_id: str, company_id: str | None, message_id: str) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="trash",
        payload={"message_id": message_id},
        company_id=company_id,
        requested_by=owner_id,
    )


def propose_archive(db, *, owner_id: str, company_id: str | None, message_id: str) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="archive",
        payload={"message_id": message_id},
        company_id=company_id,
        requested_by=owner_id,
    )


def propose_modify_labels(
    db, *, owner_id: str, company_id: str | None, message_id: str,
    add_labels: list[str] | None = None, remove_labels: list[str] | None = None,
) -> dict:
    _load_integration(db, owner_id=owner_id, company_id=company_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="modify_labels",
        payload={"message_id": message_id, "add_labels": add_labels or [], "remove_labels": remove_labels or []},
        company_id=company_id,
        requested_by=owner_id,
    )


async def execute_action(db, *, owner_id: str, company_id: str | None, action_type: str, payload: dict) -> dict:
    """Called only by capability_executors after a human approves the
    ApprovalRequest — never by an HTTP endpoint directly. Dispatches to the
    real Gmail API call for whichever approval-gated action was proposed."""
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)

    if action_type == "send":
        result = await _call(
            db, owner_id, company_id, integration, "send_message",
            to=payload["to"], subject=payload["subject"], body=payload["body"],
            thread_id=payload.get("thread_id"), in_reply_to=payload.get("in_reply_to"),
        )
    elif action_type == "forward":
        result = await _call(
            db, owner_id, company_id, integration, "forward_message",
            message_id=payload["message_id"], to=payload["to"], note=payload.get("note", ""),
        )
    elif action_type == "trash":
        result = await _call(db, owner_id, company_id, integration, "trash_message", message_id=payload["message_id"])
    elif action_type == "archive":
        result = await _call(db, owner_id, company_id, integration, "archive_message", message_id=payload["message_id"])
    elif action_type == "modify_labels":
        result = await _call(
            db, owner_id, company_id, integration, "modify_labels",
            message_id=payload["message_id"], add_labels=payload.get("add_labels"), remove_labels=payload.get("remove_labels"),
        )
    else:
        raise ValidationError(f"Gmail has no executor for action '{action_type}'.")
    return result.data


# Registering here (rather than requiring a separate bootstrap step) means
# simply importing this module — which api/v1/endpoints/gmail.py always
# does — is what wires the executor in.
register_executor(CAPABILITY_NAME, execute_action)
