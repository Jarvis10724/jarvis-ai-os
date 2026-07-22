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
    actually holds the write scope the action needs.

The commit sequence is fixed, and every step must succeed or nothing is
marked done:

  1. read the CURRENT value live from Shopify (not from the local mirror);
  2. refuse if that live value has drifted from what the preview showed —
     the approval was given for a diff that no longer describes reality;
  3. send the mutation;
  4. refuse if Shopify returns userErrors;
  5. read the product back from Shopify;
  6. refuse unless the read-back actually equals what was asked for.

Only after (6) does this return — and returning is what marks the request
executed (see capability_executors). Every refusal raises, so a request can
never claim an execution that didn't happen or wasn't verified.

Nothing here can run without an approved ApprovalRequest behind it: the
executor is only ever invoked by capability_executors after approve_action.
"""
import json
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.core import brand_brain_service, shopify_action_registry as registry, shopify_service
from app.core.capability_executors import register_executor
from app.db.models.brand_brain import BrandProduct
from app.db.models.capability import CapabilityAuditLog
from app.exceptions import ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)

CAPABILITY_NAME = "shopify"

#: The Shopify OAuth scope each write action needs. An action whose scope the
#: app doesn't hold can't be committed, no matter what the operator approves.
#: Sourced from the action registry so a new action can't be added without one,
#: plus the order-side actions that live outside the storefront registry.
REQUIRED_SCOPES: dict[str, str] = {
    **registry.REQUIRED_SCOPES,
    "refund_order": "write_orders",
    "fulfill_order": "write_fulfillments",
    "update_images": "write_products",  # legacy alias of add_images
}

#: What each action may change: payload key -> attribute on a SYNCED product
#: holding the current value. Used to build the preview before anything is
#: proposed. (Verification uses the live record instead — see LIVE_FIELDS.)
_CATALOG_KEYS = {
    "quantity": "total_inventory", "price": "price_min", "title": "title",
    "description": "description", "status": "status", "vendor": "vendor",
    "product_type": "product_type", "tags": "tags",
}
EDITABLE_FIELDS: dict[str, dict[str, str]] = {
    name: {key: _CATALOG_KEYS.get(key, key) for key in spec.fields}
    for name, spec in registry.ACTIONS.items()
    if spec.fields
}

#: Kept for the single-field preview shape the approval UI already reads.
CHANGED_FIELD: dict[str, str] = {
    "update_inventory": "quantity",
    "update_price": "price",
    "update_seo": "seo_title",
    "publish_product": "status",
}
CURRENT_READER: dict[str, str] = {
    "update_inventory": "total_inventory",
    "update_price": "price_min",
    "update_seo": "seo",
    "publish_product": "status",
}

VALID_STATUSES = ("ACTIVE", "DRAFT", "ARCHIVED")


# --- Preview (read-only) --------------------------------------------------


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
    preview["shopify_id"] = product.get("shopify_id")

    # Every field this action would touch, each with its own before -> after.
    editable = EDITABLE_FIELDS.get(action_type, {})
    fields = []
    for key, reader in editable.items():
        if key not in changes:
            continue
        fields.append({"field": key, "before": product.get(reader), "after": changes.get(key)})
    if fields:
        preview["fields"] = fields
        unchanged = [f for f in fields if _same(f["before"], f["after"])]
        if len(unchanged) == len(fields):
            preview["warnings"].append("The proposed value matches the current one — this would change nothing.")
        # A single-field change keeps the flat shape the approval UI reads.
        if len(fields) == 1:
            preview["field"] = fields[0]["field"]
            preview["before"] = fields[0]["before"]
            preview["after"] = fields[0]["after"]
        return preview

    field, reader = CHANGED_FIELD.get(action_type), CURRENT_READER.get(action_type)
    if field and reader:
        preview["field"] = field
        preview["before"] = product.get(reader)
        preview["after"] = changes.get(field)
        if _same(preview["before"], preview["after"]):
            preview["warnings"].append("The proposed value matches the current one — this would change nothing.")
    else:
        # Field-level diffing isn't defined for this action; show what was asked
        # for rather than inventing a before.
        preview["after"] = {k: v for k, v in changes.items() if k not in ("product", "handle")}
    return preview


def describe_preview(preview: dict) -> str:
    """One line an operator can read in the approval, e.g.
    'RARE EARTH | Mineral Polish: quantity 0 -> 120'."""
    if not preview.get("resolved"):
        return f"Could not resolve {preview.get('product') or 'the target'} in the synced catalog."
    name = preview.get("product") or "the store"
    fields = preview.get("fields")
    if fields and len(fields) > 1:
        parts = "; ".join(f"{f['field']} {f['before']!r} → {f['after']!r}" for f in fields)
        return f"{name}: {parts}"
    if preview.get("field") is not None:
        return f"{name}: {preview['field']} {preview.get('before')!r} → {preview.get('after')!r}"
    return f"{name}: {preview.get('after')}"


# --- Comparing values -----------------------------------------------------


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _same(before, after) -> bool:
    """Is the stored value already what was asked for? Compared the way each
    kind of field actually differs, so 38.0 vs '38.00' isn't reported as a
    change and an HTML-wrapped description isn't reported as drift."""
    if before is None or after is None:
        return before == after
    a, b = str(before).strip(), str(after).strip()
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 0.0001
    except (TypeError, ValueError):
        pass
    if "<" in a or "<" in b:
        return _strip_html(a).lower() == _strip_html(b).lower()
    return a.upper() == b.upper()

# --- Live reads -----------------------------------------------------------
#
# Verification compares against SHOPIFY, never against the local mirror, so
# each kind of target needs its own read. The keys returned here are the same
# keys ActionSpec.fields points at.

_LIVE_PRODUCT_Q = """
query LiveProduct($id: ID!) {
  product(id: $id) {
    id title handle status description descriptionHtml totalInventory vendor productType tags
    seo { title description }
    variants(first: 1) { nodes {
      id price compareAtPrice sku barcode inventoryPolicy
      inventoryItem { id tracked measurement { weight { value unit } } }
    } }
  }
}
"""

_LIVE_COLLECTION_Q = """
query LiveCollection($id: ID!) {
  collection(id: $id) { id title handle description descriptionHtml productsCount { count } }
}
"""

_LIVE_DISCOUNT_Q = """
query LiveDiscount($id: ID!) {
  codeDiscountNode(id: $id) {
    id
    codeDiscount { ... on DiscountCodeBasic { title status startsAt endsAt } }
  }
}
"""

_LIVE_PAGE_Q = """
query LivePage($id: ID!) { page(id: $id) { id title handle body isPublished } }
"""

_LIVE_MENU_Q = """
query LiveMenu($id: ID!) { menu(id: $id) { id title handle } }
"""

_LOCATIONS_Q = """
query Locations { locations(first: 5) { nodes { id name } } }
"""


def _flatten_product(product: dict, location_id: str | None) -> dict:
    variants = ((product.get("variants") or {}).get("nodes")) or []
    first = variants[0] if variants else {}
    item = first.get("inventoryItem") or {}
    weight = ((item.get("measurement") or {}).get("weight")) or {}
    seo = product.get("seo") or {}
    return {
        "id": product.get("id"),
        "title": product.get("title"),
        "description": product.get("descriptionHtml") or product.get("description"),
        "status": product.get("status"),
        "quantity": product.get("totalInventory"),
        "vendor": product.get("vendor"),
        "product_type": product.get("productType"),
        "tags": product.get("tags"),
        "seo_title": seo.get("title"),
        "seo_description": seo.get("description"),
        "price": first.get("price"),
        "compare_at_price": first.get("compareAtPrice"),
        "sku": first.get("sku"),
        "barcode": first.get("barcode"),
        "continue_selling": (first.get("inventoryPolicy") == "CONTINUE"),
        "tracked": item.get("tracked"),
        "weight": weight.get("value"),
        "variant_id": first.get("id"),
        "inventory_item_id": item.get("id"),
        "location_id": location_id,
        "raw": product,
    }


_TARGET_QUERIES = {
    "product": (_LIVE_PRODUCT_Q, "product"),
    "collection": (_LIVE_COLLECTION_Q, "collection"),
    "discount": (_LIVE_DISCOUNT_Q, "codeDiscountNode"),
    "page": (_LIVE_PAGE_Q, "page"),
    "menu": (_LIVE_MENU_Q, "menu"),
}


async def _read_live(
    db: Session, *, owner_id: str, company_id: str | None, gid: str, target: str = "product"
) -> dict:
    """The target as Shopify has it right now. This — never the local mirror —
    is what a commit compares against and verifies with."""
    query, root = _TARGET_QUERIES.get(target, _TARGET_QUERIES["product"])
    data = await shopify_service.run_approved_query(
        db, owner_id=owner_id, company_id=company_id, query=query, variables={"id": gid}
    )
    node = (data or {}).get(root)
    if not node:
        raise ValidationError(
            f"Shopify no longer has a {target} at {gid}. Nothing was changed — re-sync the catalog."
        )

    if target == "product":
        location_id = None
        locations = await shopify_service.run_approved_query(
            db, owner_id=owner_id, company_id=company_id, query=_LOCATIONS_Q
        )
        nodes = ((locations or {}).get("locations") or {}).get("nodes") or []
        if nodes:
            location_id = nodes[0]["id"]
        return _flatten_product(node, location_id)

    if target == "discount":
        detail = node.get("codeDiscount") or {}
        return {"id": node.get("id"), "title": detail.get("title"), "status": detail.get("status"),
                "ends_at": detail.get("endsAt"), "raw": node}
    if target == "page":
        return {"id": node.get("id"), "title": node.get("title"), "body": node.get("body"),
                "published": node.get("isPublished"), "raw": node}
    if target == "collection":
        return {"id": node.get("id"), "title": node.get("title"),
                "description": node.get("descriptionHtml") or node.get("description"), "raw": node}
    return {"id": node.get("id"), "title": node.get("title"), "raw": node}


# --- Mutations ------------------------------------------------------------


def _user_errors(data: dict, root: str) -> list[dict]:
    node = (data or {}).get(root) or {}
    # Media mutations return mediaUserErrors instead of userErrors.
    return node.get("userErrors") or node.get("mediaUserErrors") or []


def _raise_on_errors(errors: list[dict], action_type: str) -> None:
    if errors:
        detail = "; ".join(e.get("message", "") for e in errors if e.get("message"))
        raise ValidationError(f"Shopify rejected the {action_type}: {detail or 'unspecified error'}.")


def _validate(action_type: str, spec, live: dict, payload: dict) -> None:
    """Refuse malformed input BEFORE anything is sent, with a reason naming the
    field — a rejection from Shopify halfway through is a worse outcome."""
    if "status" in payload and payload["status"] is not None and "status" in spec.fields:
        if _status_of(payload["status"]) not in VALID_STATUSES:
            raise ValidationError(
                f"{payload['status']!r} isn't a Shopify product status. Use one of: "
                f"{', '.join(s.lower() for s in VALID_STATUSES)}. Nothing was sent to Shopify."
            )
    if spec.target == "product" and action_type in (
        "update_price", "update_compare_at_price", "update_variant", "set_continue_selling"
    ) and not live.get("variant_id"):
        raise ValidationError("This product has no variant to change — nothing was sent to Shopify.")
    if action_type in ("update_inventory", "set_inventory_tracking", "update_weight"):
        if not live.get("inventory_item_id"):
            raise ValidationError("This product has no inventory item — nothing was sent to Shopify.")
    if action_type == "update_inventory" and not (payload.get("location_id") or live.get("location_id")):
        raise ValidationError("No Shopify location to set stock at — nothing was sent to Shopify.")


def _status_of(value) -> str:
    return str(value).strip().upper()


async def _apply(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str,
    spec, live: dict, payload: dict,
) -> dict:
    """Send the Admin API mutation this action declares. Raises on userErrors
    so a partially-rejected write is never treated as success."""
    _validate(action_type, spec, live, payload)
    data = await shopify_service.run_approved_mutation(
        db, owner_id=owner_id, company_id=company_id, action_type=action_type,
        query=spec.mutation, variables=spec.variables(live, payload),
    )
    _raise_on_errors(_user_errors(data, spec.root), action_type)
    return data


# --- Commit ---------------------------------------------------------------


def _intent(action_type: str, payload: dict) -> dict:
    """The fields this approval actually asked to change."""
    editable = EDITABLE_FIELDS.get(action_type, {})
    return {k: payload[k] for k in editable if k in payload and payload[k] is not None}


def _assert_not_stale(preview: dict, live: dict, intent: dict) -> None:
    """Refuse an approval whose preview no longer describes the live store.

    The operator approved a specific `before -> after`. If someone edited the
    product in Shopify Admin since then, the before they reviewed is fiction —
    committing anyway would silently overwrite a change they never saw.
    """
    reviewed = {f["field"]: f["before"] for f in (preview.get("fields") or [])}
    if not reviewed and preview.get("field") is not None:
        reviewed = {preview["field"]: preview.get("before")}
    for field in intent:
        if field not in reviewed:
            continue
        current = live.get(field)
        if not _same(reviewed[field], current):
            raise ValidationError(
                f"Stale approval: this was reviewed against {field} = {reviewed[field]!r}, but Shopify has "
                f"{current!r}. Either it was edited in Shopify since, or the synced catalog was already out "
                f"of date — either way the diff that was approved isn't the change that would happen. "
                f"Nothing was sent to Shopify — re-sync and re-propose against the current value."
            )


def _sync_catalog(db: Session, *, company_id: str | None, product_gid: str, verified: dict) -> None:
    """Bring the local mirror in line with what Shopify just confirmed, so the
    catalog both devices read shows the committed value immediately."""
    row = (
        db.query(BrandProduct)
        .filter(BrandProduct.company_id == company_id, BrandProduct.shopify_id == product_gid)
        .first()
    )
    if row is None:
        return
    if verified.get("title"):
        row.title = verified["title"]
    if verified.get("status"):
        row.status = verified["status"]
    if verified.get("description") is not None:
        row.description = _strip_html(str(verified["description"]))
    if verified.get("quantity") is not None:
        row.total_inventory = verified["quantity"]
    if verified.get("price") is not None:
        try:
            row.price_min = float(verified["price"])
        except (TypeError, ValueError):
            pass
    db.commit()


def _audit(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str,
    request_id: str | None, before: dict, after: dict, response: dict, verified: dict,
) -> None:
    """The permanent record: what was asked, what it was before, what it is
    now, and what Shopify said. Append-only; survives the request."""
    db.add(
        CapabilityAuditLog(
            owner_id=owner_id,
            company_id=company_id,
            capability_name=CAPABILITY_NAME,
            approval_request_id=request_id,
            action=f"committed:{action_type}"[:30],
            before_json=json.dumps(before, default=str)[:4000],
            after_json=json.dumps(
                {"requested": after, "verified": verified, "shopify_response": response}, default=str
            )[:4000],
            note="verified by read-back from Shopify",
        )
    )
    db.commit()



def _resolve_target(db: Session, *, company_id: str | None, spec, payload: dict) -> str | None:
    """The Shopify gid this action is aimed at.

    Products can be resolved by name against the synced catalog. Everything
    else — a collection, a discount, a page, a menu — must carry its id,
    because guessing at which discount 'the spring one' means is exactly the
    kind of inference that should never precede a write.
    """
    preview = payload.get("_preview") or {}
    explicit = payload.get("id") or payload.get("shopify_id") or preview.get("shopify_id")
    if explicit:
        return explicit
    if spec.target == "product":
        found = _find_product(db, company_id, payload.get("product") or payload.get("title"))
        return (found or {}).get("shopify_id")
    return None


async def execute(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str, payload: dict
) -> dict:
    """Commit an APPROVED storefront change, and verify it landed.

    Only ever called by capability_executors after an ApprovalRequest reached
    'approved'. Every failure path raises, which leaves the request in
    'approved' with the reason — returning is reserved for a change Shopify
    confirmed, and (where the action can be verified) that was read back
    successfully.
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

    spec = registry.get(action_type)
    if spec is None or spec.mutation is None:
        raise ValidationError(
            f"'{action_type}' is a recognised action but has no Admin API call implemented "
            f"({'theme-editor change, not an Admin API resource' if spec and spec.target == 'theme' else 'not built yet'}). "
            f"Nothing was sent to Shopify."
        )

    # A create has no prior value to read, diff, or verify against, so it is
    # allowed to proceed without resolving an existing target.
    gid = _resolve_target(db, company_id=company_id, spec=spec, payload=payload)
    creates_something = action_type.startswith("create_")

    if not gid and not creates_something:
        raise ValidationError(
            f"Could not resolve which {spec.target} this refers to. "
            f"{'Pass the Shopify id.' if spec.target != 'product' else ''} Nothing was sent to Shopify."
        )

    live: dict = {}
    before: dict = {}
    intent = _intent(action_type, payload)

    if gid:
        # 1. Read the CURRENT live value — never trust the local mirror here.
        live = await _read_live(
            db, owner_id=owner_id, company_id=company_id, gid=gid, target=spec.target
        )
        before = {f: live.get(f) for f in intent}

        # 2. The approval was for a specific before -> after. Refuse if it drifted.
        _assert_not_stale(payload.get("_preview") or {}, live, intent)

        # Already correct: verified without sending a redundant mutation.
        if intent and all(_same(live.get(f), v) for f, v in intent.items()):
            logger.info("shopify_commit_noop", action=action_type, company_id=company_id)
            return {
                "committed": True, "changed": False, "verified": True,
                "action": action_type, "target": spec.target,
                "product": live.get("title"), "before": before, "after": before,
                "note": "Shopify already holds these values — nothing needed changing.",
            }

    # 3-4. Send it; userErrors raise.
    logger.info("shopify_commit_attempt", action=action_type, company_id=company_id)
    response = await _apply(
        db, owner_id=owner_id, company_id=company_id, action_type=action_type,
        spec=spec, live=live, payload=payload,
    )

    # 5-6. Read it back and require it to match — where that is meaningful.
    if spec.verifies and gid and intent:
        verified_record = await _read_live(
            db, owner_id=owner_id, company_id=company_id, gid=gid, target=spec.target
        )
        mismatched = {f: {"expected": v, "actual": verified_record.get(f)} for f, v in intent.items()
                      if not _same(verified_record.get(f), v)}
        if mismatched:
            raise ValidationError(
                f"The {action_type} was sent, but reading the {spec.target} back from Shopify does NOT show "
                f"the new value: {mismatched}. Not marking this as completed — check it in Shopify Admin."
            )
        after = {f: verified_record.get(f) for f in intent}
        verified = True
        note = "Confirmed by reading it back from Shopify."
        if spec.target == "product":
            _sync_catalog(db, company_id=company_id, product_gid=gid, verified=verified_record)
    else:
        # No prior value to compare against (create/duplicate/delete/reorder).
        # Report what Shopify returned and be explicit that equality was not
        # checked, rather than calling this "verified".
        after = _created_summary(response, spec)
        verified = False
        note = (
            "Shopify accepted the call and returned the result below. There is no prior value to "
            "compare against for this kind of action, so this was NOT verified by a read-back."
        )

    _audit(
        db, owner_id=owner_id, company_id=company_id, action_type=action_type,
        request_id=payload.get("_approval_id"), before=before, after=after,
        response=response, verified=after if verified else {},
    )
    logger.info("shopify_commit_done", action=action_type, company_id=company_id, verified=verified)
    return {
        "committed": True, "changed": True, "verified": verified,
        "action": action_type, "target": spec.target,
        "product": live.get("title") or payload.get("title") or payload.get("product"),
        "before": before, "after": after, "shopify_response": response, "note": note,
    }


def _created_summary(response: dict, spec) -> dict:
    """The useful part of a create/delete response — the new or removed id."""
    node = (response or {}).get(spec.root) or {}
    for key, value in node.items():
        if key in ("userErrors", "mediaUserErrors"):
            continue
        if isinstance(value, dict) and value.get("id"):
            return {"id": value["id"], **{k: v for k, v in value.items() if k != "id"}}
        if value:
            return {key: value}
    return {}


register_executor(CAPABILITY_NAME, execute)
