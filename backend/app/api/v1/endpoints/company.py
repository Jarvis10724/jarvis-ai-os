"""
Real company workspaces — Jarvis is a multi-company operating system, so
this is a collection resource (/companies), not a singleton. A user may own
any number of companies; each is fully isolated (its own sections, owner
roles, checklists, products). Adding a new company is just a POST here —
nothing about the architecture changes as companies are added.
"""
import json
import uuid

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.models.company import Company, Product
from app.db.session import get_db
from app.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/companies", tags=["companies"])

DEFAULT_SECTIONS = {
    key: {"status": "not_started", "notes": ""}
    for key in [
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
}

DEFAULT_OWNERS = [
    {"role_title": "CEO / Brand Lead", "person_name": None, "email": None},
    {"role_title": "CFO / Operations Lead", "person_name": None, "email": None},
]


def _checklist(*labels: str) -> list[dict]:
    return [{"id": str(uuid.uuid4()), "label": label, "done": False, "notes": ""} for label in labels]


DEFAULT_CHECKLISTS = {
    "shopify_recovery": _checklist(
        "Confirm ownership/access to the Shopify admin account",
        "Verify domain registrar access and that DNS points to Shopify",
        "Recover or reset the Shopify admin password",
        "Review staff accounts and remove any unrecognized access",
        "Audit installed apps and remove unused/unrecognized ones",
        "Review current theme — decide what to keep vs. rebuild",
        "Review existing product listings for accuracy",
        "Review payment provider setup (e.g. Shopify Payments) status",
        "Review shipping settings and rates",
        "Verify domain SSL is active",
        "Test the full checkout flow end-to-end before going live",
        "Connect SHOPIFY_ACCESS_TOKEN in Jarvis once ready (requires owner approval)",
    ),
    "security_review": _checklist(
        "Review all active users with access to the Shopify admin",
        "Review all active users with access to QuickBooks",
        "Review all active users with access to the business bank account",
        "Verify strong, unique passwords on all critical accounts",
        "Verify domain registrar account access and contact details are current",
        "Review who has access to the business email account",
        "Enable two-factor authentication on Shopify",
        "Enable two-factor authentication on QuickBooks",
        "Enable two-factor authentication on the domain registrar",
        "Enable two-factor authentication on the business email",
        "Store 2FA recovery codes somewhere secure and access-controlled",
        "Review and revoke access for any former contractors or freelancers",
        "Review and revoke any unused API keys or access tokens",
    ),
}


class SectionData(BaseModel):
    status: str = "not_started"
    notes: str = ""
    #: Structured knowledge extracted from the workspace's own connected files
    #: (app.core.workspace_import_service). Read-only from the UI's point of
    #: view: it's written by extraction, never by the notes editor, so a
    #: section update that omits it must not wipe it.
    data: dict | None = None


class OwnerRole(BaseModel):
    role_title: str
    person_name: str | None = None
    email: str | None = None


class ChecklistItem(BaseModel):
    id: str
    label: str
    done: bool = False
    notes: str = ""


class CompanyRead(BaseModel):
    id: str
    name: str
    tagline: str | None
    industry: str | None
    website: str | None
    # Structured workspace metadata — see Company model.
    company_type: str | None
    parent_company_id: str | None
    parent_company_name: str | None
    divisions: list[str]
    sections: dict[str, SectionData]
    owners: list[OwnerRole]
    checklists: dict[str, list[ChecklistItem]]

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    name: str
    tagline: str | None = None
    industry: str | None = None
    website: str | None = None
    company_type: str | None = None
    parent_company_id: str | None = None
    divisions: list[str] | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    tagline: str | None = None
    industry: str | None = None
    website: str | None = None
    company_type: str | None = None
    parent_company_id: str | None = None
    divisions: list[str] | None = None
    sections: dict[str, SectionData] | None = None
    owners: list[OwnerRole] | None = None
    checklists: dict[str, list[ChecklistItem]] | None = None


class ProductRead(BaseModel):
    id: str
    name: str
    sku: str | None
    manufacturer: str | None
    packaging: str | None
    cogs: float | None
    moq: int | None
    freight: float | None
    price: float | None
    margin: float | None
    inventory: int | None
    launch_status: str
    notes: str | None

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    manufacturer: str | None = None
    packaging: str | None = None
    cogs: float | None = None
    moq: int | None = None
    freight: float | None = None
    price: float | None = None
    margin: float | None = None
    inventory: int | None = None
    launch_status: str | None = None
    notes: str | None = None


def _serialize(company: Company) -> CompanyRead:
    sections = json.loads(company.sections_json) if company.sections_json else {}
    owners = json.loads(company.owners_json) if company.owners_json else []
    checklists = json.loads(company.checklists_json) if company.checklists_json else {}
    divisions = json.loads(company.divisions_json) if company.divisions_json else []
    return CompanyRead(
        id=company.id,
        name=company.name,
        tagline=company.tagline,
        industry=company.industry,
        website=company.website,
        company_type=company.company_type,
        parent_company_id=company.parent_company_id,
        parent_company_name=company.parent.name if company.parent else None,
        divisions=divisions,
        sections={k: SectionData(**v) for k, v in sections.items()},
        owners=[OwnerRole(**o) for o in owners],
        checklists={k: [ChecklistItem(**item) for item in v] for k, v in checklists.items()},
    )


def _get_owned_company(company_id: str, current_user, db: Session) -> Company:
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.owner_id == current_user.id)
        .first()
    )
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found")
    return company


def _validate_parent(parent_id: str | None, current_user, db: Session, self_id: str | None = None) -> None:
    """A parent workspace must exist, belong to the same owner (never cross
    accounts — workspace isolation is a hard rule), and not be the company
    itself. Passing None (clearing the parent) is always allowed."""
    if not parent_id:
        return
    if parent_id == self_id:
        raise ValidationError("A workspace cannot be its own parent.")
    _get_owned_company(parent_id, current_user, db)  # raises NotFoundError if not owned


@router.get("", response_model=list[CompanyRead])
def list_companies(current_user: CurrentUser, db: Session = Depends(get_db)):
    companies = db.query(Company).filter(Company.owner_id == current_user.id).all()
    return [_serialize(c) for c in companies]


@router.post("", response_model=CompanyRead, status_code=201)
def create_company(payload: CompanyCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    _validate_parent(payload.parent_company_id, current_user, db)
    company = Company(
        owner_id=current_user.id,
        name=payload.name,
        tagline=payload.tagline,
        industry=payload.industry,
        website=payload.website,
        company_type=payload.company_type,
        parent_company_id=payload.parent_company_id,
        divisions_json=json.dumps(payload.divisions) if payload.divisions else None,
        sections_json=json.dumps(DEFAULT_SECTIONS),
        owners_json=json.dumps(DEFAULT_OWNERS),
        checklists_json=json.dumps(DEFAULT_CHECKLISTS),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return _serialize(company)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return _serialize(_get_owned_company(company_id, current_user, db))


@router.put("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: str, payload: CompanyUpdate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    company = _get_owned_company(company_id, current_user, db)

    if payload.name is not None:
        company.name = payload.name
    if payload.tagline is not None:
        company.tagline = payload.tagline
    if payload.industry is not None:
        company.industry = payload.industry
    if payload.website is not None:
        company.website = payload.website
    if payload.company_type is not None:
        company.company_type = payload.company_type or None
    if payload.parent_company_id is not None:
        # Empty string clears the parent; otherwise validate ownership + no self-ref.
        parent_id = payload.parent_company_id or None
        _validate_parent(parent_id, current_user, db, self_id=company.id)
        company.parent_company_id = parent_id
    if payload.divisions is not None:
        company.divisions_json = json.dumps(payload.divisions)
    if payload.sections is not None:
        existing = json.loads(company.sections_json) if company.sections_json else {}
        for key, value in payload.sections.items():
            incoming = value.model_dump()
            # Editing notes/status must never drop extracted knowledge.
            if incoming.get("data") is None:
                incoming.pop("data", None)
                keep = (existing.get(key) or {}).get("data")
                if keep is not None:
                    incoming["data"] = keep
            existing[key] = {**(existing.get(key) or {}), **incoming}
        company.sections_json = json.dumps(existing)
    if payload.owners is not None:
        company.owners_json = json.dumps([o.model_dump() for o in payload.owners])
    if payload.checklists is not None:
        existing = json.loads(company.checklists_json) if company.checklists_json else {}
        existing.update({k: [item.model_dump() for item in v] for k, v in payload.checklists.items()})
        company.checklists_json = json.dumps(existing)

    db.commit()
    db.refresh(company)
    return _serialize(company)


@router.get("/{company_id}/products", response_model=list[ProductRead])
def list_products(company_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    company = _get_owned_company(company_id, current_user, db)
    return company.products


@router.post("/{company_id}/products", response_model=ProductRead, status_code=201)
def create_product(
    company_id: str, payload: ProductCreate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    company = _get_owned_company(company_id, current_user, db)
    product = Product(company_id=company.id, name=payload.name, launch_status="planning")
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{company_id}/products/{product_id}", response_model=ProductRead)
def update_product(
    company_id: str,
    product_id: str,
    payload: ProductUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    company = _get_owned_company(company_id, current_user, db)
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company.id)
        .first()
    )
    if not product:
        raise NotFoundError(f"Product '{product_id}' not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product
