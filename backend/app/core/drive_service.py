"""
Orchestration layer between Drive's HTTP endpoints and the lower-level
pieces: credential_store (encrypted, company-scoped tokens),
capability_service (the permission/enable gate), and
GoogleDriveIntegration (the real Drive API calls). Mirrors
app.core.gmail_service / app.core.calendar_service — see gmail_service's
docstring for the shape this follows.

Both actions app.core.capabilities_registry's "google_drive" entry declares
(list_files, read_document) are direct — no approval needed — so unlike
gmail_service/calendar_service there is no propose_*/execute_action/
register_executor here yet. Add that the same way Gmail's send or
Calendar's create_event were added if a write action (upload/create/
delete) is ever registered for this capability.
"""
from app.core import capability_service, credential_store
from app.db.models.company import Company
from app.exceptions import ValidationError
from app.integrations.google_drive_integration import GoogleDriveIntegration

CAPABILITY_NAME = "google_drive"


def _load_integration(db, *, owner_id: str, company_id: str | None) -> GoogleDriveIntegration:
    creds = credential_store.load_credentials(db, owner_id=owner_id, company_id=company_id, provider=CAPABILITY_NAME)
    if not creds or not creds.get("access_token"):
        raise ValidationError("Drive is not connected for this company yet — connect it from Integrations first.")
    return GoogleDriveIntegration(credentials=creds)


async def _call(db, owner_id: str, company_id: str | None, integration: GoogleDriveIntegration, method_name: str, **kwargs):
    """Every real Drive call goes through here so a refreshed access token
    (GoogleDriveIntegration._authed_request refreshes in-memory on a 401
    but can't persist it itself — it has no db session) gets written back
    via credential_store exactly once, right after the call that
    triggered it."""
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
# Direct actions — read, no approval needed
# ---------------------------------------------------------------------------


def _combine_query(folder_id: str | None, query: str) -> str:
    """Builds the final Drive `q` string. A folder-scoped clause
    ('<id>' in parents) is joined with the caller's own query — which may
    itself be raw Drive syntax or a bare search term — using the same
    bare-term-vs-syntax heuristic GoogleDriveIntegration.list_files uses,
    so the combined string is unambiguous either way."""
    clauses = []
    if folder_id:
        clauses.append(f"'{folder_id}' in parents")
    if query:
        looks_like_raw_syntax = any(op in query for op in ("=", "contains", "in "))
        clauses.append(query if looks_like_raw_syntax else f"name contains '{query}'")
    return " and ".join(clauses)


def _company_name(db, owner_id: str, company_id: str) -> str | None:
    company = db.query(Company).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    return company.name if company else None


async def list_files(
    db, *, owner_id: str, company_id: str | None, query: str = "", max_results: int = 10, all_drive: bool = False
) -> list[dict]:
    """Powers 'list my files' (query=""), 'search Drive' (query=
    "invoice", etc.), and company-scoped listing alike. When a company is
    active and all_drive isn't set, results are restricted to a Drive
    folder named exactly like that company — the same shared Google
    account, isolated by folder rather than by a separate connection per
    company (see credential_store's account-wide fallback for the other
    half of that: a company workspace with no OAuth connection of its own
    still uses the account-wide one instead of reporting 'disconnected').
    A missing folder (company has no matching folder yet) degrades to an
    unscoped listing rather than an error. Pass all_drive=True (or omit
    company_id) to search the whole connected Drive regardless of any
    per-company folder."""
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="list_files", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)

    folder_id = None
    if company_id and not all_drive:
        name = _company_name(db, owner_id, company_id)
        if name:
            folder_id = await _call(db, owner_id, company_id, integration, "find_folder_id", name=name)

    effective_query = _combine_query(folder_id, query)
    result = await _call(db, owner_id, company_id, integration, "list_files", query=effective_query, max_results=max_results)
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="list_files", company_id=company_id,
        result={"count": len(result.data), "folder_scoped": bool(folder_id)},
    )
    return result.data


async def read_document(db, *, owner_id: str, company_id: str | None, file_id: str) -> dict:
    capability_service.authorize_direct_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="read_document", company_id=company_id
    )
    integration = _load_integration(db, owner_id=owner_id, company_id=company_id)
    result = await _call(db, owner_id, company_id, integration, "read_document", file_id=file_id)
    capability_service.log_capability_action(
        db, owner_id=owner_id, capability_name=CAPABILITY_NAME, action_type="read_document", company_id=company_id,
        note=file_id,
    )
    return result.data
