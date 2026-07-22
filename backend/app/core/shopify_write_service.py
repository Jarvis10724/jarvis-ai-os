"""
The Shopify action layer: preview a storefront change, then commit it — but
only after a human approves, and only if writing has been deliberately enabled.

Two halves:

  * PREVIEW (read-only, always available). Before a change is proposed, the
    current value is read from the synced catalog so the approval shows
    `before -> after` rather than just the intended new value. A preview that
    can't find the product says so instead of implying the change is safe.

  * COMMIT (gated twice over). Registered as the `shopify` executor, so the
    Approval Center runs it the moment a change is approved — and it refuses
    unless BOTH gates are open: SHOPIFY_WRITE_ENABLED is true, and the app
    actually holds the write scope the action needs. This app is installed
    with read_products,read_inventory only, so today every commit is refused
    with that reason rather than attempted and failed halfway.

Nothing here can run without an approved ApprovalRequest behind it: the
executor is only ever invoked by capability_executors after approve_action.
"""
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import ValidationError
from app.core import brand_brain_service
from app.core.capability_executors import register_executor
from app.logging_config import get_logger

logger = get_logger(__name__)

CAPABILITY_NAME = "shopify"

#: The Shopify OAuth scope each write action needs. An action whose scope the
#: app doesn't hold can't be committed, no matter what the operator approves.
REQUIRED_SCOPES: dict[str, str] = {
    "update_inventory": "write_inventory",
    "update_price": "write_products",
    "update_product": "write_products",
    "update_seo": "write_products",
    "update_images": "write_products",
    "create_draft_product": "write_products",
    "publish_product": "write_products",
    "create_collection": "write_products",
    "create_discount": "write_discounts",
    "refund_order": "write_orders",
    "fulfill_order": "write_fulfillments",
}

#: Which payload field carries the new value, per action — used to build the
#: before/after diff.
CHANGED_FIELD: dict[str, str] = {
    "update_inventory": "quantity",
    "update_price": "price",
    "update_seo": "seo_title",
    "publish_product": "status",
}

#: How to read the CURRENT value of that field off a synced product.
CURRENT_READER: dict[str, str] = {
    "update_inventory": "total_inventory",
    "update_price": "price_min",
    "update_seo": "seo",
    "publish_product": "status",
}


def _find_product(db: Session, company_id: str, name: str | None) -> dict | None:
    if not name:
        return None
    needle = name.strip().lower()
    for p in brand_brain_service.list_products(db, company_id, limit=250):
        if needle in (p.get("title") or "").lower() or needle == (p.get("handle") or ""):
            return p
    return None


def build_preview(db: Session, *, company_id: str, action_type: str, changes: dict) -> dict:
    """What this change would do, stated as before -> after against the live
    catalog. Read-only. Returns `resolved: False` when the product can't be
    found, so a proposal never implies it verified something it didn't."""
    preview: dict = {
        "action": action_type,
        "resolved": False,
        "product": changes.get("product") or changes.get("title"),
        "before": None,
        "after": None,
        "warnings": [],
    }

    scope = REQUIRED_SCOPES.get(action_type)
    if scope:
        preview["required_scope"] = scope
    if not settings.SHOPIFY_WRITE_ENABLED:
        preview["warnings"].append(
            "Storefront writes are disabled, so approving records the decision without changing the store."
        )

    product = _find_product(db, company_id, preview["product"])
    if product is None:
        if action_type in ("create_draft_product", "create_collection", "create_discount"):
            preview["resolved"] = True
            preview["after"] = changes
            return preview
        preview["warnings"].append(
            f"No product matching {preview['product']!r} in the synced catalog — the before value is unknown."
        )
        return preview

    preview["resolved"] = True
    preview["handle"] = product.get("handle")
    field, reader = CHANGED_FIELD.get(action_type), CURRENT_READER.get(action_type)
    if field and reader:
        preview["field"] = field
        preview["before"] = product.get(reader)
        preview["after"] = changes.get(field)
        if str(preview["before"]) == str(preview["after"]):
            preview["warnings"].append("The proposed value matches the current one — this would change nothing.")
    else:
        # Field-level diffing isn't defined for this action; show what was asked
        # for rather than inventing a before.
        preview["after"] = {k: v for k, v in changes.items() if k not in ("product", "handle")}
    return preview


def describe_preview(preview: dict) -> str:
    """One line an operator can read in the approval, e.g.
    'RARE EARTH | Mineral Polish: total inventory 0 -> 120'."""
    if not preview.get("resolved"):
        return f"Could not resolve {preview.get('product') or 'the target'} in the synced catalog."
    name = preview.get("product") or "the store"
    if preview.get("field") is not None:
        return f"{name}: {preview['field']} {preview.get('before')!r} → {preview.get('after')!r}"
    return f"{name}: {preview.get('after')}"


async def execute(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str, payload: dict
) -> dict:
    """Commit an APPROVED storefront change.

    Only ever called by capability_executors after an ApprovalRequest reached
    'approved'. Refuses — clearly, without attempting a partial write — when
    writing is disabled or the app lacks the scope the action needs.
    """
    scope = REQUIRED_SCOPES.get(action_type)

    if not settings.SHOPIFY_WRITE_ENABLED:
        # Raising (rather than returning) is deliberate: capability_executors
        # marks a request 'executed' whenever the executor returns normally, and
        # nothing was executed. The request stays 'approved' with this reason.
        raise ValidationError(
            "Approved, but storefront writes are turned off (SHOPIFY_WRITE_ENABLED is false). "
            "Nothing was sent to Shopify."
        )

    granted = {s.strip() for s in (settings.SHOPIFY_SCOPES or "").split(",") if s.strip()}
    if scope and scope not in granted:
        raise ValidationError(
            f"Approved, but this app isn't authorised to '{scope}'. It holds: "
            f"{', '.join(sorted(granted)) or 'no write scopes'}. Re-install the Shopify app with "
            f"'{scope}' before this can be committed."
        )

    # Both gates open. Committing is a deliberate, separately-enabled step; the
    # per-action Admin API calls are implemented as each one is turned on, so an
    # unimplemented action reports that rather than silently doing nothing.
    logger.info("shopify_commit_attempt", action=action_type, company_id=company_id)
    raise ValidationError(
        f"Writes are enabled and '{scope}' is granted, but the Admin API call for "
        f"'{action_type}' hasn't been implemented yet. Nothing was sent to Shopify."
    )


register_executor(CAPABILITY_NAME, execute)
