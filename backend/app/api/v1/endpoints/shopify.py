"""
Shopify read-only HTTP surface (Phase 1). Every route is a GET; there is no
POST/PUT/PATCH/DELETE here by design. Each data route is workspace-scoped
via `company_id` (must be the Primal-Penni workspace bound in env) and
delegates to shopify_service, which applies the isolation guard and the
capability audit trail. Nothing here ever serializes a credential — the
`/status` route returns booleans + the non-secret store domain only.
"""
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import CurrentUser
from app.core import shopify_service
# Importing this registers the Shopify write executor with capability_executors,
# so an approved storefront change is routed to it (and refused there unless
# writes are enabled and the scope is granted).
from app.core import shopify_write_service  # noqa: F401
from app.db.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/shopify", tags=["shopify"])


@router.get("/status")
def status(current_user: CurrentUser, company_id: str | None = Query(None)):
    """Non-secret connection status for the Settings card."""
    return shopify_service.status(owner_id=current_user.id, company_id=company_id)


@router.get("/products")
async def products(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_products(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/collections")
async def collections(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_collections(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/inventory")
async def inventory(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_inventory(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/orders")
async def orders(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_orders(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/customers")
async def customers(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_customers(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/discounts")
async def discounts(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_discounts(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/themes")
async def themes(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_themes(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/settings")
async def settings_(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None)):
    return await shopify_service.get_settings(db, owner_id=current_user.id, company_id=company_id)


@router.get("/metafields")
async def metafields(current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = Query(None), first: int = Query(20, le=100)):
    return await shopify_service.list_metafields(db, owner_id=current_user.id, company_id=company_id, first=first)


@router.get("/metaobjects")
async def metaobjects(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = Query(None),
    type: str = Query(..., description="Metaobject definition type/handle, e.g. 'ingredient'"),
    first: int = Query(20, le=100),
):
    return await shopify_service.list_metaobjects(db, owner_id=current_user.id, company_id=company_id, metaobject_type=type, first=first)
