"""
Brand Brain HTTP surface — the workspace's structured source of truth.

Reads (GET) are served from Jarvis's own brand_* tables (no Shopify round-trip)
and are scoped to a company the caller owns. The one POST — /sync — triggers a
read-only import FROM Shopify INTO the Brand Brain; it never writes to Shopify
(guarded by shopify_service's workspace + capability checks). There is no route
here that can modify the store.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core import brand_brain_service
from app.db.models.company import Company
from app.db.session import get_db
from app.exceptions import NotFoundError

router = APIRouter(prefix="/brand-brain", tags=["brand-brain"])


def _owned_company_id(company_id: str, current_user, db: Session) -> str:
    """The Brand Brain is always workspace-scoped; a caller may only read a
    company they own (defense in depth on top of Shopify's binding)."""
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.owner_id == current_user.id)
        .first()
    )
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found")
    return company_id


@router.get("")
def summary(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str = Query(...)):
    _owned_company_id(company_id, current_user, db)
    return brand_brain_service.get_summary(db, company_id)


@router.get("/products")
def products(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str = Query(...), limit: int = Query(100, le=250)):
    _owned_company_id(company_id, current_user, db)
    return brand_brain_service.list_products(db, company_id, limit=limit)


@router.get("/collections")
def collections(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str = Query(...)):
    _owned_company_id(company_id, current_user, db)
    return brand_brain_service.list_collections(db, company_id)


@router.get("/context")
def context(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str = Query(...), product_limit: int = Query(50, le=250)):
    """The canonical brand brief consumed by websites/emails/social/research/agents."""
    _owned_company_id(company_id, current_user, db)
    return brand_brain_service.get_brand_context(db, company_id, product_limit=product_limit)


@router.post("/sync")
async def sync(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str = Query(...)):
    """Import the store into the Brand Brain (read-only from Shopify). Requires
    the Shopify-bound workspace + configured credentials (enforced downstream)."""
    _owned_company_id(company_id, current_user, db)
    return await brand_brain_service.sync_from_shopify(db, owner_id=current_user.id, company_id=company_id)
