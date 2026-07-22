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
from app.core import brand_brain_service, shopify_service
from app.core.capability_executors import register_executor
from app.db.models.brand_brain import BrandProduct
from app.db.models.capability import CapabilityAuditLog
from app.exceptions import ValidationError
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

#: The fields each action may change: payload key -> attribute on a synced
#: product carrying the current value. Actions absent here have no implemented
#: Admin API call yet and are refused at commit time rather than half-attempted.
EDITABLE_FIELDS: dict[str, dict[str, str]] = {
    "update_inventory": {"quantity": "total_inventory"},
    "update_price": {"price": "price_min"},
    "update_product": {"title": "title", "description": "description", "status": "status"},
    "publish_product": {"status": "status"},
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

_LIVE_PRODUCT_Q = """
query LiveProduct($id: ID!) {
  product(id: $id) {
    id title handle status description descriptionHtml totalInventory
    variants(first: 1) { nodes { id price inventoryItem { id } } }
  }
}
"""

_LOCATIONS_Q = """
query Locations { locations(first: 5) { nodes { id name } } }
"""


async def _read_live(db: Session, *, owner_id: str, company_id: str | None, product_gid: str) -> dict:
    """The product as Shopify has it right now. This — never the local
    mirror — is what a commit compares against and verifies with."""
    data = await shopify_service.run_approved_query(
        db, owner_id=owner_id, company_id=company_id, query=_LIVE_PRODUCT_Q, variables={"id": product_gid}
    )
    product = (data or {}).get("product")
    if not product:
        raise ValidationError(
            f"Shopify no longer has a product at {product_gid}. Nothing was changed — re-sync the catalog."
        )
    variants = ((product.get("variants") or {}).get("nodes")) or []
    first = variants[0] if variants else {}
    return {
        "raw": product,
        "title": product.get("title"),
        "description": product.get("descriptionHtml") or product.get("description"),
        "status": product.get("status"),
        "quantity": product.get("totalInventory"),
        "price": first.get("price"),
        "variant_id": first.get("id"),
        "inventory_item_id": (first.get("inventoryItem") or {}).get("id"),
    }


# --- Mutations ------------------------------------------------------------

_PRODUCT_UPDATE_M = """
mutation ProductUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id title status descriptionHtml }
    userErrors { field message }
  }
}
"""

_VARIANT_PRICE_M = """
mutation VariantPrice($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price }
    userErrors { field message }
  }
}
"""

_INVENTORY_SET_M = """
mutation InventorySet($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup { createdAt reason }
    userErrors { field message }
  }
}
"""


def _user_errors(data: dict, root: str) -> list[dict]:
    return ((data or {}).get(root) or {}).get("userErrors") or []


async def _apply(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str,
    product_gid: str, live: dict, intent: dict,
) -> dict:
    """Send the actual Admin API mutation. Raises on any userErrors so a
    partially-rejected write is never treated as success."""
    if "quantity" in intent:
        if not live.get("inventory_item_id"):
            raise ValidationError("This product has no inventory item to set — nothing was sent to Shopify.")
        locations = await shopify_service.run_approved_query(
            db, owner_id=owner_id, company_id=company_id, query=_LOCATIONS_Q
        )
        nodes = ((locations or {}).get("locations") or {}).get("nodes") or []
        if not nodes:
            raise ValidationError("No Shopify location to set stock at — nothing was sent to Shopify.")
        data = await shopify_service.run_approved_mutation(
            db, owner_id=owner_id, company_id=company_id, action_type=action_type,
            query=_INVENTORY_SET_M,
            variables={"input": {
                "name": "available",
                "reason": "correction",
                "ignoreCompareQuantity": True,
                "quantities": [{
                    "inventoryItemId": live["inventory_item_id"],
                    "locationId": nodes[0]["id"],
                    "quantity": int(intent["quantity"]),
                }],
            }},
        )
        _raise_on_errors(_user_errors(data, "inventorySetQuantities"), action_type)
        return data

    if "price" in intent:
        if not live.get("variant_id"):
            raise ValidationError("This product has no variant to price — nothing was sent to Shopify.")
        data = await shopify_service.run_approved_mutation(
            db, owner_id=owner_id, company_id=company_id, action_type=action_type,
            query=_VARIANT_PRICE_M,
            variables={
                "productId": product_gid,
                "variants": [{"id": live["variant_id"], "price": str(intent["price"])}],
            },
        )
        _raise_on_errors(_user_errors(data, "productVariantsBulkUpdate"), action_type)
        return data

    product_input: dict = {"id": product_gid}
    if "title" in intent:
        product_input["title"] = str(intent["title"])
    if "description" in intent:
        product_input["descriptionHtml"] = str(intent["description"])
    if "status" in intent:
        status = str(intent["status"]).strip().upper()
        if status not in VALID_STATUSES:
            raise ValidationError(
                f"{status!r} isn't a Shopify product status. Use one of: "
                f"{', '.join(s.lower() for s in VALID_STATUSES)}. Nothing was sent to Shopify."
            )
        product_input["status"] = status
    data = await shopify_service.run_approved_mutation(
        db, owner_id=owner_id, company_id=company_id, action_type=action_type,
        query=_PRODUCT_UPDATE_M, variables={"input": product_input},
    )
    _raise_on_errors(_user_errors(data, "productUpdate"), action_type)
    return data


def _raise_on_errors(errors: list[dict], action_type: str) -> None:
    if errors:
        detail = "; ".join(e.get("message", "") for e in errors if e.get("message"))
        raise ValidationError(f"Shopify rejected the {action_type}: {detail or 'unspecified error'}.")


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


async def execute(
    db: Session, *, owner_id: str, company_id: str | None, action_type: str, payload: dict
) -> dict:
    """Commit an APPROVED storefront change, and verify it landed.

    Only ever called by capability_executors after an ApprovalRequest reached
    'approved'. Every failure path raises, which leaves the request in
    'approved' with the reason — returning is reserved for a change Shopify
    confirmed and that was read back successfully.
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

    intent = _intent(action_type, payload)
    if not intent:
        raise ValidationError(
            f"Writes are enabled and '{scope}' is granted, but the Admin API call for "
            f"'{action_type}' hasn't been implemented yet. Nothing was sent to Shopify."
        )

    preview = payload.get("_preview") or {}
    product_gid = preview.get("shopify_id")
    if not product_gid:
        found = _find_product(db, company_id, payload.get("product") or payload.get("title"))
        product_gid = (found or {}).get("shopify_id")
    if not product_gid:
        raise ValidationError(
            f"Could not resolve {payload.get('product')!r} to a Shopify product. Nothing was sent to Shopify."
        )

    # 1. Read the CURRENT live value — never trust the local mirror for this.
    live = await _read_live(db, owner_id=owner_id, company_id=company_id, product_gid=product_gid)
    before = {f: live.get(f) for f in intent}

    # 2. The approval was for a specific before -> after. Refuse if it drifted.
    _assert_not_stale(preview, live, intent)

    # Already correct: verified without sending a redundant mutation.
    if all(_same(live.get(f), v) for f, v in intent.items()):
        logger.info("shopify_commit_noop", action=action_type, company_id=company_id)
        return {
            "committed": True, "changed": False, "verified": True,
            "product": live.get("title"), "before": before, "after": before,
            "note": "Shopify already holds these values — nothing needed changing.",
        }

    # 3-4. Send it; userErrors raise.
    logger.info("shopify_commit_attempt", action=action_type, company_id=company_id)
    response = await _apply(
        db, owner_id=owner_id, company_id=company_id, action_type=action_type,
        product_gid=product_gid, live=live, intent=intent,
    )

    # 5-6. Read it back from Shopify and require it to match.
    verified = await _read_live(db, owner_id=owner_id, company_id=company_id, product_gid=product_gid)
    mismatched = {f: {"expected": v, "actual": verified.get(f)} for f, v in intent.items()
                  if not _same(verified.get(f), v)}
    if mismatched:
        raise ValidationError(
            f"The {action_type} was sent, but reading the product back from Shopify does NOT show the new "
            f"value: {mismatched}. Not marking this as completed — check the product in Shopify Admin."
        )

    after = {f: verified.get(f) for f in intent}
    _sync_catalog(db, company_id=company_id, product_gid=product_gid, verified=verified)
    _audit(
        db, owner_id=owner_id, company_id=company_id, action_type=action_type,
        request_id=payload.get("_approval_id"), before=before, after=after,
        response=response, verified=after,
    )
    logger.info("shopify_commit_verified", action=action_type, company_id=company_id)
    return {
        "committed": True, "changed": True, "verified": True,
        "product": verified.get("title"), "before": before, "after": after,
        "note": "Confirmed by reading the product back from Shopify.",
    }


register_executor(CAPABILITY_NAME, execute)
