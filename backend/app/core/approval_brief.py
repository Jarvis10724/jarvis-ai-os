"""
The decision brief attached to every approval request.

Nobody can responsibly approve "shopify · update_product {json}". A brief
answers the four questions a human actually needs: what is this, what will
happen if I say yes, what could go wrong, and can I undo it.

Briefs are DATA, not AI output — derived deterministically from the action type
and its payload, so they're identical every time, cost nothing, and can't
hallucinate a reassurance. A proposer that knows better (the Work Queue planner
knows *why* a step exists) can override any field.

Adding a capability action here is the whole job of making it explainable; an
action with no entry still gets an honest generic brief that names the
capability and says the effect is outside Jarvis and may not be reversible.
"""
import json
from collections.abc import Callable

#: (capability_name, action_type) -> builder(payload) -> partial brief dict
_BRIEFS: dict[tuple[str, str], Callable[[dict], dict]] = {}

#: Actions that cannot be taken back once they happen. Used for the default
#: undo language so a missing entry errs toward caution, never toward
#: implying something is reversible when it isn't.
IRREVERSIBLE = "This cannot be undone once it happens."


def _register(capability: str, action: str):
    def deco(fn: Callable[[dict], dict]):
        _BRIEFS[(capability, action)] = fn
        return fn

    return deco


def _short(value, limit: int = 120) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- Email -----------------------------------------------------------------


@_register("email", "send")
def _email_send(p: dict) -> dict:
    to = p.get("to") or "an unspecified recipient"
    subject = p.get("subject") or "(no subject)"
    return {
        "summary": f"Send an email to {to} — “{_short(subject, 80)}”",
        "expected_outcome": f"{to} receives this email immediately, from your connected mailbox.",
        "risks": [
            "The recipient is a real person and will see this exactly as written.",
            "Anything inaccurate in the message goes out as if you wrote it.",
        ],
        "undo_plan": f"{IRREVERSIBLE} A sent email cannot be recalled — the only remedy is a follow-up correction.",
    }


@_register("email", "forward")
def _email_forward(p: dict) -> dict:
    to = p.get("to") or "an unspecified recipient"
    return {
        "summary": f"Forward a message to {to}",
        "expected_outcome": f"{to} receives the full original message, including any quoted history.",
        "risks": ["Forwarded threads often contain earlier content you may not intend to share."],
        "undo_plan": f"{IRREVERSIBLE} The forwarded copy is already in the recipient's mailbox.",
    }


@_register("email", "trash")
def _email_trash(p: dict) -> dict:
    return {
        "summary": "Move a message to trash",
        "expected_outcome": "The message leaves the inbox and sits in Trash.",
        "risks": ["Gmail permanently deletes trashed mail after 30 days."],
        "undo_plan": "Reversible: restore it from Trash within 30 days.",
    }


@_register("email", "archive")
def _email_archive(p: dict) -> dict:
    return {
        "summary": "Archive a message",
        "expected_outcome": "The message leaves the inbox but stays searchable in All Mail.",
        "risks": ["Nothing is deleted; the thread just stops appearing in the inbox."],
        "undo_plan": "Reversible: move it back to the inbox at any time.",
    }


# --- Calendar --------------------------------------------------------------


@_register("google_calendar", "create_event")
def _cal_create(p: dict) -> dict:
    title = p.get("summary") or p.get("title") or "an event"
    when = p.get("start") or p.get("start_time") or "the specified time"
    attendees = p.get("attendees") or []
    risks = ["The event appears on your real calendar."]
    if attendees:
        risks.append(f"{len(attendees)} attendee(s) receive an invitation email immediately.")
    return {
        "summary": f"Create the calendar event “{_short(title, 80)}” at {_short(when, 40)}",
        "expected_outcome": "The event is added to your connected calendar"
        + (" and invitations go out to the attendees." if attendees else "."),
        "risks": risks,
        "undo_plan": "Reversible: delete the event afterwards"
        + (" — though attendees will already have seen the invite." if attendees else "."),
    }


@_register("google_calendar", "update_event")
def _cal_update(p: dict) -> dict:
    return {
        "summary": "Update an existing calendar event",
        "expected_outcome": "The event changes on your calendar; attendees are notified of the change.",
        "risks": ["Attendees receive an update notice, including for small edits."],
        "undo_plan": "Reversible: the previous values can be set back, but the notification already went out.",
    }


@_register("google_calendar", "delete_event")
def _cal_delete(p: dict) -> dict:
    return {
        "summary": "Delete/cancel a calendar event",
        "expected_outcome": "The event is removed and attendees receive a cancellation.",
        "risks": ["Attendees are told the meeting is cancelled."],
        "undo_plan": f"{IRREVERSIBLE} The event can be recreated, but the cancellation notice has been sent.",
    }


# --- Commerce / business data ----------------------------------------------


@_register("business_data", "update_product")
def _product_update(p: dict) -> dict:
    fields = [k for k in p.keys() if k not in ("product_id", "id", "company_id") and not k.startswith("_")]
    return {
        "summary": f"Change {', '.join(fields) if fields else 'fields'} on a product record",
        "expected_outcome": "The product record in Jarvis is updated. This does not touch the live store.",
        "risks": ["Downstream views (pricing, margin, inventory) read from this record."],
        "undo_plan": "Reversible: the previous values are kept in the audit log and can be set back.",
    }


@_register("shopify", "refund_order")
def _refund(p: dict) -> dict:
    amount = p.get("amount")
    return {
        "summary": f"Refund order {p.get('order_id', '(unspecified)')}"
        + (f" for {amount}" if amount else ""),
        "expected_outcome": "Money is returned to the customer's payment method by Shopify.",
        "risks": [
            "This moves real money out of the business account.",
            "The customer is notified by Shopify.",
        ],
        "undo_plan": f"{IRREVERSIBLE} A refund cannot be reversed — recovering it means charging the customer again.",
    }


@_register("shopify", "fulfill_order")
def _fulfill(p: dict) -> dict:
    return {
        "summary": f"Mark order {p.get('order_id', '(unspecified)')} fulfilled",
        "expected_outcome": "Shopify marks the order fulfilled and emails the customer a shipping notice.",
        "risks": ["The customer is told their order shipped — premature if it hasn't."],
        "undo_plan": "Partly reversible: fulfillment can be cancelled in Shopify, but the customer email has been sent.",
    }


# --- Shopify storefront writes ---------------------------------------------
# Jarvis PREPARES these from the phone; none of them has an executor, so
# approving records the decision and nothing reaches the live store until an
# executor is deliberately enabled. The briefs say so plainly rather than
# implying the change is about to go live.

_NOT_LIVE = (
    "Approving records your decision. Nothing is pushed to Shopify — storefront writes "
    "are not enabled, so this will not change the live store by itself."
)


def _target(p: dict) -> str:
    return p.get("product") or p.get("title") or p.get("handle") or "the store"


@_register("shopify", "update_inventory")
def _shopify_inventory(p: dict) -> dict:
    return {
        "summary": f"Set stock for {_target(p)} to {p.get('quantity', '?')}",
        "expected_outcome": f"The recorded stock level for {_target(p)} becomes {p.get('quantity', '?')}. " + _NOT_LIVE,
        "risks": [
            "Stock drives what customers can buy — too high oversells, too low hides a product.",
        ],
        "undo_plan": "Reversible: set the previous quantity back. The prior value is in the audit trail.",
    }


@_register("shopify", "update_price")
def _shopify_price(p: dict) -> dict:
    return {
        "summary": f"Change the price of {_target(p)} to {p.get('price', '?')}",
        "expected_outcome": f"{_target(p)} would be priced at {p.get('price', '?')}. " + _NOT_LIVE,
        "risks": [
            "Price is customer-facing and affects margin on every subsequent order.",
            "Shoppers who saw the old price may notice the change.",
        ],
        "undo_plan": "Reversible: restore the previous price from the audit trail.",
    }


@_register("shopify", "update_product")
def _shopify_product(p: dict) -> dict:
    # Underscore-prefixed keys are internal plumbing the executor puts on the
    # payload (_preview, _approval_id). They are not fields being edited and
    # must never appear in a summary a human reads.
    fields = [k for k in p if k not in ("product", "handle", "product_id") and not k.startswith("_")]
    return {
        "summary": f"Edit {', '.join(fields) if fields else 'fields'} on {_target(p)}",
        "expected_outcome": f"The listed fields on {_target(p)} would change. " + _NOT_LIVE,
        "risks": ["Product copy and status are customer-facing."],
        "undo_plan": "Reversible: the previous values are kept in the audit trail.",
    }


@_register("shopify", "update_seo")
def _shopify_seo(p: dict) -> dict:
    return {
        "summary": f"Update SEO title/description for {_target(p)}",
        "expected_outcome": f"Search-engine title and description for {_target(p)} would change. " + _NOT_LIVE,
        "risks": ["Search rankings can move after an SEO change, in either direction."],
        "undo_plan": "Reversible: restore the previous SEO text.",
    }


@_register("shopify", "update_images")
def _shopify_images(p: dict) -> dict:
    return {
        "summary": f"Change product images for {_target(p)}",
        "expected_outcome": f"The image set for {_target(p)} would change. " + _NOT_LIVE,
        "risks": ["Images are the first thing a customer judges the product on."],
        "undo_plan": "Reversible while the original image files still exist.",
    }


@_register("shopify", "create_draft_product")
def _shopify_draft(p: dict) -> dict:
    return {
        "summary": f"Create “{p.get('title', 'a new product')}” as an UNPUBLISHED draft",
        "expected_outcome": "A draft product would be created. Drafts are not visible to customers. " + _NOT_LIVE,
        "risks": ["None to customers while it stays a draft — publishing is a separate approval."],
        "undo_plan": "Reversible: delete the draft.",
    }


@_register("shopify", "publish_product")
def _shopify_publish(p: dict) -> dict:
    return {
        "summary": f"PUBLISH {_target(p)} to the live storefront",
        "expected_outcome": f"{_target(p)} would become visible and purchasable by customers. " + _NOT_LIVE,
        "risks": [
            "This is the step that makes something public.",
            "Publishing with wrong pricing or stock is immediately visible to customers.",
        ],
        "undo_plan": "Reversible: unpublish it — though anyone who saw it in the meantime already did.",
    }


@_register("shopify", "create_collection")
def _shopify_collection(p: dict) -> dict:
    return {
        "summary": f"Create the collection “{p.get('title', 'untitled')}”",
        "expected_outcome": "A new collection would be created to group products. " + _NOT_LIVE,
        "risks": ["Collections shape storefront navigation."],
        "undo_plan": "Reversible: delete the collection.",
    }


@_register("shopify", "create_discount")
def _shopify_discount(p: dict) -> dict:
    return {
        "summary": f"Create discount “{p.get('code', p.get('title', 'untitled'))}” ({p.get('value', '?')})",
        "expected_outcome": "A discount customers could redeem would be created. " + _NOT_LIVE,
        "risks": [
            "Discounts cost real margin on every order that uses them.",
            "A code that leaks can be shared publicly.",
        ],
        "undo_plan": "Reversible: deactivate the discount — but orders already placed with it stand.",
    }


# --- Jarvis's own planned work ---------------------------------------------


@_register("work_queue", "execute_step")
def _work_step(p: dict) -> dict:
    title = p.get("title") or "a planned step"
    return {
        "summary": _short(title, 160),
        "expected_outcome": "Jarvis carries out this step and continues the rest of the plan in order.",
        "risks": ["This step was flagged as having real-world consequences outside Jarvis."],
        "undo_plan": "Depends on the step — review the wording above before approving.",
    }


def build_brief(capability_name: str, action_type: str, payload: dict | None) -> dict:
    """The four decision fields for one proposed action. Always returns every
    key, so the UI never has to handle a missing field."""
    payload = payload or {}
    builder = _BRIEFS.get((capability_name, action_type))
    brief = builder(payload) if builder else {}
    return {
        "summary": brief.get("summary") or f"{capability_name} · {action_type}",
        "expected_outcome": brief.get("expected_outcome")
        or f"Jarvis performs '{action_type}' via {capability_name}. The effect happens outside Jarvis.",
        "risks": brief.get("risks") or [f"This is a real-world action through {capability_name}."],
        "undo_plan": brief.get("undo_plan")
        or f"Unknown for this action — assume it may not be reversible. {IRREVERSIBLE}",
    }


def merge_brief(capability_name: str, action_type: str, payload: dict | None, overrides: dict | None) -> dict:
    """The derived brief, with any proposer-supplied fields winning. `reason`
    has no derived default: only the proposer knows *why* it asked."""
    brief = build_brief(capability_name, action_type, payload)
    overrides = {k: v for k, v in (overrides or {}).items() if v}
    brief.update(overrides)
    brief.setdefault("reason", None)
    return brief
