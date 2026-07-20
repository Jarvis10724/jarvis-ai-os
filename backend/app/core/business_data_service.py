"""
Business-data writes Jarvis's chat agent can propose — product fields and
company profile sections. Unlike Gmail/Calendar (real external services),
these are internal DB rows, but Priority 6 (the user's approval-gate rule)
is explicit: nothing Jarvis does should ever change business data without a
human approving it first. So this mirrors the exact propose/approve/execute
shape gmail_service and calendar_service use, just with capability_service's
generic approval queue standing in for an external API.

Validation (company ownership, unknown fields/sections/statuses) happens up
front in the propose_* functions — before an ApprovalRequest is even
created — so a bad call fails immediately with a clear error instead of
sitting in the approval queue as something that will fail once approved.

Note: this deliberately does NOT touch the direct REST endpoints in
api/v1/endpoints/company.py (PUT /companies/{id}, PUT .../products/{id}).
Those are the human directly editing their own data through the app's own
forms/tables (CompanyProfile, LaunchDashboard) — not an autonomous action,
so they stay immediate. The approval gate applies to writes Jarvis's chat
agent initiates on the user's behalf.
"""
import json

from app.core import capability_service
from app.core.capability_executors import register_executor
from app.db.models.company import Company, Product
from app.exceptions import NotFoundError, ValidationError

CAPABILITY_NAME = "business_data"

UPDATABLE_PRODUCT_FIELDS = {
    "name",
    "sku",
    "manufacturer",
    "packaging",
    "cogs",
    "moq",
    "freight",
    "price",
    "margin",
    "inventory",
    "launch_status",
    "notes",
}

SECTION_KEYS = [
    "brand",
    "manufacturing",
    "packaging",
    "shopify",
    "amazon",
    "quickbooks",
    "marketing",
    "compliance",
    "tasks",
    "documents",
    "approvals",
]
SECTION_STATUSES = ["not_started", "in_progress", "needs_rebuild", "set_up_not_connected", "done"]


def _get_owned_company(db, company_id: str, owner_id: str) -> Company:
    company = db.query(Company).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found (or it isn't yours).")
    return company


def propose_update_product(db, *, owner_id: str, company_id: str, product_id: str, fields: dict, requested_by: str | None = None) -> dict:
    company = _get_owned_company(db, company_id, owner_id)
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company.id).first()
    if not product:
        raise NotFoundError(f"Product '{product_id}' not found on {company.name}. Call list_products first.")
    unknown = set(fields) - UPDATABLE_PRODUCT_FIELDS
    if unknown:
        raise ValidationError(
            f"Unknown product field(s): {', '.join(sorted(unknown))}. Valid fields: {', '.join(sorted(UPDATABLE_PRODUCT_FIELDS))}"
        )
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="update_product",
        payload={"product_id": product_id, "product_name": product.name, "fields": fields},
        company_id=company_id,
        requested_by=requested_by or owner_id,
    )


def propose_update_company_section(
    db, *, owner_id: str, company_id: str, section: str, status: str | None = None, notes: str | None = None,
    requested_by: str | None = None,
) -> dict:
    if section not in SECTION_KEYS:
        raise ValidationError(f"Unknown section '{section}'. Valid: {', '.join(SECTION_KEYS)}")
    if status is not None and status not in SECTION_STATUSES:
        raise ValidationError(f"Unknown status '{status}'. Valid: {', '.join(SECTION_STATUSES)}")
    if status is None and notes is None:
        raise ValidationError("Provide at least one of status or notes to update.")
    company = _get_owned_company(db, company_id, owner_id)
    return capability_service.propose_action(
        db,
        owner_id=owner_id,
        capability_name=CAPABILITY_NAME,
        action_type="update_company_section",
        payload={"section": section, "status": status, "notes": notes, "company_name": company.name},
        company_id=company_id,
        requested_by=requested_by or owner_id,
    )


async def execute_action(db, *, owner_id: str, company_id: str | None, action_type: str, payload: dict) -> dict:
    """Called only by capability_executors after a human approves the
    ApprovalRequest — applies the actual DB write."""
    if action_type == "update_product":
        company = _get_owned_company(db, company_id, owner_id)
        product = db.query(Product).filter(Product.id == payload["product_id"], Product.company_id == company.id).first()
        if not product:
            raise NotFoundError(f"Product '{payload['product_id']}' no longer exists on {company.name}.")
        for field, value in payload["fields"].items():
            setattr(product, field, value)
        db.commit()
        db.refresh(product)
        return {"product_id": product.id, "updated_fields": payload["fields"]}

    if action_type == "update_company_section":
        company = _get_owned_company(db, company_id, owner_id)
        existing = json.loads(company.sections_json) if company.sections_json else {}
        current = existing.get(payload["section"], {"status": "not_started", "notes": ""})
        if payload.get("status") is not None:
            current["status"] = payload["status"]
        if payload.get("notes") is not None:
            current["notes"] = payload["notes"]
        existing[payload["section"]] = current
        company.sections_json = json.dumps(existing)
        db.commit()
        return {"section": payload["section"], "status": current["status"]}

    raise ValidationError(f"business_data has no executor for action '{action_type}'.")


register_executor(CAPABILITY_NAME, execute_action)
