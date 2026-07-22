"""
Tools Jarvis's chat can actually call — this is what turns Jarvis from a
chatbot into something that can run plugins and edit real business data on
your behalf, mid-conversation.

Every tool here does one of two things:
  1. Runs one of the existing AI plugins (web_builder, logo_design, ...) —
     same plugin registry Quick Actions and the Plugins page already use.
  2. Reads or writes real rows in the database (products, company sections),
     scoped to the current user exactly like the REST endpoints in
     `api/v1/endpoints/company.py` are — a tool can never touch a company
     that isn't owned by the user making the request.

Add a new tool by writing a handler + JSON schema and registering it in
TOOL_REGISTRY at the bottom of this file.
"""
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.orm import Session

from app.ai_providers.base import ToolDefinition
from app.core import (
    brand_brain_service,
    business_data_service,
    calendar_service,
    drive_service,
    gmail_service,
    memory_service,
)
from app.core.memory_scope import MEMORY_SCOPES
from app.core.orchestrator import orchestrator
from app.db.models.company import Company
from app.db.models.memory import MEMORY_KINDS
from app.db.models.project import Project
from app.db.models.task import Task
from app.exceptions import NotFoundError, ValidationError

ToolHandler = Callable[..., Awaitable[str]]


@dataclass
class AgentTool:
    definition: ToolDefinition
    handler: ToolHandler


def _get_owned_company(company_id: str, current_user, db: Session) -> Company:
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.owner_id == current_user.id)
        .first()
    )
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found (or it isn't yours).")
    return company


# ---------------------------------------------------------------------------
# Plugin tools — one per existing AI plugin.
# ---------------------------------------------------------------------------

_PLUGIN_TOOLS = [
    ("web_builder", "brief", "Plans and scaffolds a website from a plain-language brief."),
    (
        "logo_design",
        "brief",
        "Generates logo concepts and a starter SVG mark from a brand brief. Also requires brand_name.",
    ),
    ("product_creation", "idea", "Turns a product idea into a spec, pricing, and launch checklist."),
    ("deep_research", "question", "Structured multi-angle research synthesis on a topic or question."),
    ("code_writer", "spec", "Generates code from a natural-language spec."),
    ("project_management", "goal", "Breaks a goal into a structured, sequenced task list."),
    ("automation", "task_description", "Designs a repeatable automation workflow from a task description."),
]


def _make_plugin_tool(plugin_name: str, arg_key: str, description: str) -> AgentTool:
    properties: dict = {arg_key: {"type": "string", "description": f"Main input for {plugin_name}."}}
    required = [arg_key]
    if plugin_name == "logo_design":
        properties["brand_name"] = {"type": "string", "description": "The brand name."}
        required.append("brand_name")

    async def handler(current_user, db: Session, **kwargs) -> str:
        result = await orchestrator.run_plugin(plugin_name, **kwargs)
        if not result.success:
            return f"Plugin failed: {result.message}"
        return str(result.output)

    return AgentTool(
        definition=ToolDefinition(
            name=f"run_{plugin_name}",
            description=description,
            input_schema={"type": "object", "properties": properties, "required": required},
        ),
        handler=handler,
    )


# ---------------------------------------------------------------------------
# Real business-data tools.
# ---------------------------------------------------------------------------

async def _list_companies(current_user, db: Session) -> str:
    companies = db.query(Company).filter(Company.owner_id == current_user.id).all()
    if not companies:
        return "No companies found for this user."
    return "\n".join(f"- id={c.id} name={c.name!r} industry={c.industry}" for c in companies)


async def _list_products(current_user, db: Session, *, company_id: str) -> str:
    company = _get_owned_company(company_id, current_user, db)
    if not company.products:
        return f"No products found for {company.name}."
    lines = [f"Products for {company.name}:"]
    for p in company.products:
        lines.append(
            f"- id={p.id} name={p.name!r} status={p.launch_status} "
            f"cogs={p.cogs} price={p.price} inventory={p.inventory}"
        )
    return "\n".join(lines)


_UPDATABLE_PRODUCT_FIELDS = business_data_service.UPDATABLE_PRODUCT_FIELDS
_SECTION_KEYS = business_data_service.SECTION_KEYS
_SECTION_STATUSES = business_data_service.SECTION_STATUSES


# Both of these ONLY ever propose a pending ApprovalRequest — see
# business_data_service's docstring for why writes Jarvis's chat agent
# initiates go through the same approval gate as sending an email or
# creating a calendar event, even though these are internal DB rows rather
# than an external API call.
async def _propose_update_product(
    current_user, db: Session, *, company_id: str, product_id: str, fields: dict
) -> str:
    approval = business_data_service.propose_update_product(
        db, owner_id=current_user.id, company_id=company_id, product_id=product_id, fields=fields,
        requested_by=current_user.id,
    )
    changes = ", ".join(f"{k}={v!r}" for k, v in fields.items())
    return f"Proposed (pending your approval, request id={approval['id']}): {changes}"


async def _propose_update_company_section(
    current_user,
    db: Session,
    *,
    company_id: str,
    section: str,
    status: str | None = None,
    notes: str | None = None,
) -> str:
    approval = business_data_service.propose_update_company_section(
        db, owner_id=current_user.id, company_id=company_id, section=section, status=status, notes=notes,
        requested_by=current_user.id,
    )
    return f"Proposed (pending your approval, request id={approval['id']}): '{section}' -> status={status!r}"


# ---------------------------------------------------------------------------
# Memory tools — Jarvis's long-term brain. `company_id` is optional on both:
# when the model omits it, chat.py's _execute_tool fills in whatever company
# is currently active in the UI, so callers don't have to think about scoping
# for the common case. Pass company_id explicitly to override (e.g. a fact
# that's clearly personal, not tied to the active company).
# ---------------------------------------------------------------------------


async def _remember(
    current_user,
    db: Session,
    *,
    kind: str,
    title: str,
    content: str,
    scope: str | None = None,
    company_id: str | None = None,
    project_id: str | None = None,
    confidence: float | None = None,
    source_ref: str | None = None,
) -> str:
    entry = await memory_service.record_memory(
        db,
        owner_id=current_user.id,
        kind=kind,
        title=title,
        content=content,
        scope=scope,
        company_id=company_id,
        project_id=project_id,
        confidence=confidence,
        source="chat",
        source_ref=source_ref,
    )
    conf = f", confidence={entry.confidence}" if entry.confidence is not None else ""
    return f"Saved to memory (id={entry.id}, kind={entry.kind}, scope={entry.scope}{conf}): {entry.title}"


async def _search_memory(
    current_user,
    db: Session,
    *,
    query: str,
    company_id: str | None = None,
    kind: str | None = None,
    scope: str | None = None,
    limit: int = 8,
) -> str:
    scoped_company_id = company_id if company_id is not None else "any"
    results = await memory_service.search_memory(
        db,
        owner_id=current_user.id,
        query=query,
        company_id=scoped_company_id,
        kind=kind,
        scope=scope,
        limit=limit,
    )
    if not results:
        return "No matching memory found."
    lines = [f"{len(results)} memory match(es):"]
    for r in results:
        where = f"company={r['company_id']}" if r["company_id"] else r["scope"]
        lines.append(
            f"- id={r['id']} kind={r['kind']} scope={r['scope']} ({where}) score={r.get('score', 'n/a')}\n"
            f"  {r['title']}: {r['content'][:280]}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Integration tools — Gmail, Calendar, Drive. Same company-scoping
# convention as the memory tools: `company_id` is optional, and
# chat.py's _execute_tool fills in whatever company is active in the UI
# when the model omits it (see _COMPANY_SCOPED_TOOLS there). Only each
# capability's DIRECT actions (no human approval needed) plus one
# representative propose_* action are exposed here — send/create/etc. only
# ever create a pending ApprovalRequest (capability_service.propose_action
# under the hood), never execute immediately, so exposing them to the model
# doesn't bypass the approval gate built for exactly this reason.
# ---------------------------------------------------------------------------


async def _gmail_list_messages(
    current_user, db: Session, *, query: str = "", unread_only: bool = False, max_results: int = 10,
    company_id: str | None = None,
) -> str:
    messages = await gmail_service.list_messages(
        db, owner_id=current_user.id, company_id=company_id, query=query, unread_only=unread_only, max_results=max_results
    )
    if not messages:
        return "No messages found."
    lines = [f"{len(messages)} message(s):"]
    for m in messages:
        lines.append(
            f"- id={m['id']} from={m['from']} subject={m['subject']!r} unread={m['unread']} "
            f"snippet={(m['snippet'] or '')[:120]!r}"
        )
    return "\n".join(lines)


async def _gmail_summarize(
    current_user, db: Session, *, message_id: str | None = None, max_results: int = 10, company_id: str | None = None,
) -> str:
    result = await gmail_service.summarize(
        db, owner_id=current_user.id, company_id=company_id, message_id=message_id, max_results=max_results
    )
    return result["summary"]


async def _gmail_draft(
    current_user, db: Session, *, body: str, to: str | None = None, subject: str | None = None,
    thread_id: str | None = None, reply_to_message_id: str | None = None, company_id: str | None = None,
) -> str:
    result = await gmail_service.create_draft(
        db, owner_id=current_user.id, company_id=company_id, to=to, subject=subject, body=body,
        thread_id=thread_id, reply_to_message_id=reply_to_message_id,
    )
    return f"Draft created (draft_id={result.get('draft_id')}). Not sent — use propose_send_email to actually send it."


async def _gmail_propose_send(
    current_user, db: Session, *, to: str, subject: str, body: str, thread_id: str | None = None,
    in_reply_to: str | None = None, company_id: str | None = None,
) -> str:
    req = gmail_service.propose_send(
        db, owner_id=current_user.id, company_id=company_id, to=to, subject=subject, body=body,
        thread_id=thread_id, in_reply_to=in_reply_to,
    )
    return f"Send proposed (approval_request_id={req['id']}, status={req['status']}) — waiting on human approval, not sent yet."


async def _calendar_list_events(
    current_user, db: Session, *, max_results: int = 10, upcoming_only: bool = True, company_id: str | None = None,
) -> str:
    events = await calendar_service.list_events(
        db, owner_id=current_user.id, company_id=company_id, max_results=max_results, upcoming_only=upcoming_only
    )
    if not events:
        return "No events found."
    lines = [f"{len(events)} event(s):"]
    for e in events:
        lines.append(f"- id={e['id']} summary={e['summary']!r} start={e['start']} end={e['end']}")
    return "\n".join(lines)


async def _calendar_propose_create_event(
    current_user, db: Session, *, summary: str, start: str, end: str, description: str = "", location: str = "",
    attendees: list[str] | None = None, all_day: bool = False, company_id: str | None = None,
) -> str:
    req = calendar_service.propose_create_event(
        db, owner_id=current_user.id, company_id=company_id, summary=summary, start=start, end=end,
        description=description, location=location, attendees=attendees, all_day=all_day,
    )
    return f"Event creation proposed (approval_request_id={req['id']}, status={req['status']}) — waiting on human approval."


async def _drive_list_files(
    current_user, db: Session, *, query: str = "", max_results: int = 10, company_id: str | None = None,
    all_drive: bool = False,
) -> str:
    files = await drive_service.list_files(
        db, owner_id=current_user.id, company_id=company_id, query=query, max_results=max_results, all_drive=all_drive
    )
    if not files:
        return "No files found."
    lines = [f"{len(files)} file(s):"]
    for f in files:
        lines.append(f"- id={f['id']} name={f['name']!r} type={f['mime_type']} modified={f['modified_time']}")
    return "\n".join(lines)


async def _drive_read_document(current_user, db: Session, *, file_id: str, company_id: str | None = None) -> str:
    doc = await drive_service.read_document(db, owner_id=current_user.id, company_id=company_id, file_id=file_id)
    if not doc["extractable"]:
        return doc["message"]
    return f"{doc['name']}:\n\n{doc['content']}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

async def _create_project(current_user, db: Session, *, name: str, description: str | None = None) -> str:
    project = Project(owner_id=current_user.id, name=name[:255], description=description, status="active")
    db.add(project)
    db.commit()
    db.refresh(project)
    return f"Created project (id={project.id}): {project.name!r}."


async def _create_task(
    current_user,
    db: Session,
    *,
    title: str,
    company_id: str | None = None,
    project_id: str | None = None,
    description: str | None = None,
    status: str = "backlog",
    assignee: str | None = None,
    due_date: str | None = None,
) -> str:
    if company_id:
        _get_owned_company(company_id, current_user, db)
    task = Task(
        owner_id=current_user.id,
        company_id=company_id,
        project_id=project_id,
        title=title[:255],
        description=description,
        status=status,
        assignee=assignee,
        due_date=due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return f"Created task (id={task.id}, status={task.status}): {task.title!r}."


TOOL_REGISTRY: dict[str, AgentTool] = {}

for _plugin_name, _arg_key, _description in _PLUGIN_TOOLS:
    _tool = _make_plugin_tool(_plugin_name, _arg_key, _description)
    TOOL_REGISTRY[_tool.definition.name] = _tool

# --- The live store (Brand Brain) -----------------------------------------
# Read-only views of the workspace's real Shopify catalog. These exist so the
# store can be operated by voice from a phone: the static prompt block only
# carries a summary line per product, which can't answer "how much RARE EARTH
# is left" or "what's in the POLISH collection". Nothing here writes to
# Shopify — writes remain disabled and would go through the Approval Center.


async def _store_catalog(current_user, db: Session, *, company_id: str, query: str = "") -> str:
    _get_owned_company(company_id, current_user, db)
    products = brand_brain_service.list_products(db, company_id, limit=200)
    if not products:
        return "This workspace has no synced store catalog yet. Sync the Brand Brain first."
    needle = (query or "").strip().lower()
    if needle:
        products = [
            p
            for p in products
            if needle in (p["title"] or "").lower()
            or needle in (p["product_type"] or "").lower()
            or any(needle in t.lower() for t in p["tags"])
        ]
        if not products:
            return f"No products in the store match {query!r}."
    lines = []
    for p in products:
        price = f"{p['price_min']:.2f}" if p["price_min"] is not None else "?"
        inv = p["total_inventory"]
        lines.append(
            f"- {p['title']} | {price} {p['currency'] or ''} | status={p['status'] or 'n/a'} "
            f"| inventory={inv if inv is not None else 'unknown'} | handle={p['handle']}"
        )
    return "Live store catalog (source of truth):\n" + "\n".join(lines)


async def _store_product(current_user, db: Session, *, company_id: str, name: str) -> str:
    _get_owned_company(company_id, current_user, db)
    products = brand_brain_service.list_products(db, company_id, limit=200)
    needle = name.strip().lower()
    match = next((p for p in products if needle in (p["title"] or "").lower() or needle == (p["handle"] or "")), None)
    if not match:
        return f"No product named {name!r} in this store. Use store_catalog to see what exists."
    parts = [
        f"{match['title']} (handle={match['handle']}, status={match['status'] or 'n/a'})",
        f"Price: {match['price_min']} - {match['price_max']} {match['currency'] or ''}",
        f"Total inventory: {match['total_inventory']}",
        f"Type: {match['product_type'] or 'n/a'} | Vendor: {match['vendor'] or 'n/a'}",
        f"Tags: {', '.join(match['tags']) or 'none'}",
    ]
    if match.get("variants"):
        parts.append("Variants:")
        for v in match["variants"][:20]:
            parts.append(
                f"  - {v.get('title')} | sku={v.get('sku')} | price={v.get('price')} "
                f"| inventory={v.get('inventoryQuantity')}"
            )
    if match.get("description"):
        parts.append(f"Description: {match['description'][:600]}")
    return "\n".join(parts)


async def _store_collections(current_user, db: Session, *, company_id: str) -> str:
    _get_owned_company(company_id, current_user, db)
    collections = brand_brain_service.list_collections(db, company_id)
    if not collections:
        return "No collections synced for this store yet."
    return "Store collections:\n" + "\n".join(
        f"- {c['title']} (handle={c['handle']}, {c['products_count']} products)" for c in collections
    )


async def _sync_store(current_user, db: Session, *, company_id: str) -> str:
    """Pull the latest catalog from Shopify. Read-only: this imports FROM the
    store, it never changes it."""
    _get_owned_company(company_id, current_user, db)
    try:
        result = await brand_brain_service.sync_from_shopify(db, owner_id=current_user.id, company_id=company_id)
    except Exception as exc:  # noqa: BLE001
        return f"Couldn't reach Shopify: {exc}"
    return (
        f"Synced {result['store_name']}: {result['product_count']} products, "
        f"{result['collection_count']} collections (read-only)."
    )


TOOL_REGISTRY["list_companies"] = AgentTool(
    definition=ToolDefinition(
        name="list_companies",
        description="List the companies (workspaces) the current user owns, with their ids.",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    handler=_list_companies,
)

TOOL_REGISTRY["list_products"] = AgentTool(
    definition=ToolDefinition(
        name="list_products",
        description="List real products/SKUs for a company: id, status, cost, price, inventory.",
        input_schema={
            "type": "object",
            "properties": {"company_id": {"type": "string", "description": "The company's id."}},
            "required": ["company_id"],
        },
    ),
    handler=_list_products,
)

# Read-only store tools — the phone's window into the real catalog.
TOOL_REGISTRY["store_catalog"] = AgentTool(
    definition=ToolDefinition(
        name="store_catalog",
        description=(
            "The workspace's REAL store catalog from Shopify (source of truth): every product with "
            "price, status, and inventory. Use this for any question about what the store sells, "
            "stock levels, or pricing. Optional `query` filters by name, type, or tag."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "The workspace's company id."},
                "query": {"type": "string", "description": "Optional filter, e.g. 'polish' or 'serum'."},
            },
            "required": ["company_id"],
        },
    ),
    handler=_store_catalog,
)

TOOL_REGISTRY["store_product"] = AgentTool(
    definition=ToolDefinition(
        name="store_product",
        description=(
            "Full detail for ONE real store product: variants, per-variant SKU/price/inventory, tags, "
            "and description. Use when asked about a specific product."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "The workspace's company id."},
                "name": {"type": "string", "description": "Product name or handle, e.g. 'RARE EARTH'."},
            },
            "required": ["company_id", "name"],
        },
    ),
    handler=_store_product,
)

TOOL_REGISTRY["store_collections"] = AgentTool(
    definition=ToolDefinition(
        name="store_collections",
        description="The store's real collections and how many products each contains.",
        input_schema={
            "type": "object",
            "properties": {"company_id": {"type": "string", "description": "The workspace's company id."}},
            "required": ["company_id"],
        },
    ),
    handler=_store_collections,
)

TOOL_REGISTRY["sync_store"] = AgentTool(
    definition=ToolDefinition(
        name="sync_store",
        description=(
            "Re-import the latest catalog from Shopify into the Brand Brain. Read-only — it pulls FROM "
            "the store and never changes it. Use when the user says the catalog looks stale."
        ),
        input_schema={
            "type": "object",
            "properties": {"company_id": {"type": "string", "description": "The workspace's company id."}},
            "required": ["company_id"],
        },
    ),
    handler=_sync_store,
)

TOOL_REGISTRY["create_project"] = AgentTool(
    definition=ToolDefinition(
        name="create_project",
        description="Create a new Project to organize a body of work. Returns the new project's id.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short project name."},
                "description": {"type": "string", "description": "What this project is for."},
            },
            "required": ["name"],
        },
    ),
    handler=_create_project,
)

TOOL_REGISTRY["create_task"] = AgentTool(
    definition=ToolDefinition(
        name="create_task",
        description=(
            "Create a real Task. Scope it to the active company (company_id) and optionally a "
            "project (project_id from create_project). status is one of backlog|in_progress|review|done."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "The task title."},
                "company_id": {"type": "string", "description": "Company/workspace id this task belongs to."},
                "project_id": {"type": "string", "description": "Optional project id to nest under."},
                "description": {"type": "string", "description": "Optional details."},
                "status": {"type": "string", "description": "backlog|in_progress|review|done (default backlog)."},
                "assignee": {"type": "string", "description": "Optional assignee name."},
                "due_date": {"type": "string", "description": "Optional due date, YYYY-MM-DD."},
            },
            "required": ["title"],
        },
    ),
    handler=_create_task,
)

TOOL_REGISTRY["propose_update_product"] = AgentTool(
    definition=ToolDefinition(
        name="propose_update_product",
        description=(
            "Propose changing one or more fields on a real product/SKU. This ONLY creates a "
            "pending approval request — nothing changes until the user approves it from the "
            "Approvals page. Get the product_id from list_products first. Only include fields "
            "you want to change."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "product_id": {"type": "string"},
                "fields": {
                    "type": "object",
                    "description": (
                        'Fields to change, e.g. {"cogs": 4.5, "price": 19.99, '
                        '"inventory": 300, "launch_status": "ready"}. Valid keys: '
                        + ", ".join(sorted(_UPDATABLE_PRODUCT_FIELDS))
                    ),
                },
            },
            "required": ["company_id", "product_id", "fields"],
        },
    ),
    handler=_propose_update_product,
)

TOOL_REGISTRY["propose_update_company_section"] = AgentTool(
    definition=ToolDefinition(
        name="propose_update_company_section",
        description=(
            "Propose a status/notes change for one section of a company's profile. This ONLY "
            "creates a pending approval request — nothing changes until the user approves it "
            "from the Approvals page. Section must be one of: " + ", ".join(_SECTION_KEYS)
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "section": {"type": "string", "enum": _SECTION_KEYS},
                "status": {"type": "string", "enum": _SECTION_STATUSES},
                "notes": {"type": "string"},
            },
            "required": ["company_id", "section"],
        },
    ),
    handler=_propose_update_company_section,
)

_SCOPE_GUIDANCE = (
    "Every memory has a scope — classify it into exactly one:\n"
    "  - global: system-wide, or it affects multiple companies, or it's about Jarvis's own "
    "structure/configuration. Prefer global over guessing a single company whenever a memory's "
    "relevance clearly isn't limited to one business — never split one cross-company memory "
    "into several company-scoped ones.\n"
    "  - organization: spans the user's whole business portfolio without being system-structural "
    "(e.g. general operating preferences, practices that apply across all their companies). This "
    "is also the default when no company is active and nothing else fits.\n"
    "  - company: specific to exactly one active business. Requires company_id.\n"
    "  - project: specific to one discrete project/initiative, narrower than company. Requires "
    "project_id (call list_companies/a project-listing tool first if you don't have it — never "
    "guess an id).\n"
    "  - personal: about the user as an individual, not business.\n"
    "If you omit scope it's inferred from company_id/project_id (defaulting to organization with "
    "neither). Only ask the user which scope applies when it's genuinely ambiguous — e.g. it could "
    "plausibly be either company or organization-wide. For the common, clear cases (obviously about "
    "the active company, obviously cross-company, obviously personal) just classify it — don't ask."
)

TOOL_REGISTRY["remember"] = AgentTool(
    definition=ToolDefinition(
        name="remember",
        description=(
            "Save something to Jarvis's long-term memory so it's searchable later — a "
            "decision, a manufacturer/supplier quote, a meeting summary, a contact detail, "
            "a long-term goal or investment plan (kind='goal'), a fact, anything worth not "
            "forgetting. Use this proactively whenever the conversation produces something "
            "durable, don't wait to be asked.\n\n" + _SCOPE_GUIDANCE
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": MEMORY_KINDS, "description": "What kind of thing this is."},
                "title": {"type": "string", "description": "Short title/summary, shown in search results."},
                "content": {"type": "string", "description": "The full detail to remember."},
                "scope": {
                    "type": "string",
                    "enum": MEMORY_SCOPES,
                    "description": "See scope classification rules above. Omit to infer from company_id/project_id.",
                },
                "company_id": {
                    "type": "string",
                    "description": "Company this belongs to. Required if scope='company'; ignored for global/organization/personal.",
                },
                "project_id": {
                    "type": "string",
                    "description": "Project this belongs to. Required if scope='project'.",
                },
                "confidence": {
                    "type": "number",
                    "description": (
                        "How sure you are about the scope classification, 0-1. Include this "
                        "particularly when it's on the lower end (below ~0.6) — that's the signal "
                        "for whether this was actually worth asking the user about instead of guessing."
                    ),
                },
                "source_ref": {
                    "type": "string",
                    "description": "Optional id/url of the thing this is about (e.g. a product id).",
                },
            },
            "required": ["kind", "title", "content"],
        },
    ),
    handler=_remember,
)

TOOL_REGISTRY["search_memory"] = AgentTool(
    definition=ToolDefinition(
        name="search_memory",
        description=(
            "Search Jarvis's long-term memory by natural language — past conversations, "
            "quotes, decisions, contacts, SOPs, meetings, and anything else ever saved. "
            "Use this whenever the user references something from before, or before "
            "answering a question you might already have real context for. Defaults to "
            "searching everything (every scope, global memory plus the active company's); "
            "pass company_id and/or scope explicitly to narrow it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for, in plain language."},
                "company_id": {
                    "type": "string",
                    "description": "Restrict to one company's memory (plus global). Omit to search everything.",
                },
                "kind": {"type": "string", "enum": MEMORY_KINDS, "description": "Restrict to one kind of memory."},
                "scope": {
                    "type": "string",
                    "enum": MEMORY_SCOPES,
                    "description": "Restrict to exactly one scope (e.g. 'personal' to exclude business memory).",
                },
                "limit": {"type": "integer", "description": "Max results (default 8)."},
            },
            "required": ["query"],
        },
    ),
    handler=_search_memory,
)

_COMPANY_ID_PROP = {
    "company_id": {
        "type": "string",
        "description": "Which company's connection to use. Omit to use the currently active company (or the account-wide connection if none is active).",
    }
}

TOOL_REGISTRY["list_gmail_messages"] = AgentTool(
    definition=ToolDefinition(
        name="list_gmail_messages",
        description=(
            "List/search the connected Gmail inbox — read-only, executes immediately. "
            "Use query for Gmail search syntax (e.g. 'from:supplier', 'has:attachment') "
            "or unread_only=true for just unread mail. Requires Gmail to be connected "
            "(check Integrations first if this errors)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search syntax. Empty = inbox."},
                "unread_only": {"type": "boolean"},
                "max_results": {"type": "integer", "description": "Default 10, max 50."},
                **_COMPANY_ID_PROP,
            },
            "required": [],
        },
    ),
    handler=_gmail_list_messages,
)

TOOL_REGISTRY["summarize_gmail"] = AgentTool(
    definition=ToolDefinition(
        name="summarize_gmail",
        description=(
            "Summarize one Gmail message (pass message_id, get it from list_gmail_messages "
            "first) or a prioritized digest of unread mail (omit message_id). Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "max_results": {"type": "integer", "description": "How many unread messages to digest if message_id is omitted."},
                **_COMPANY_ID_PROP,
            },
            "required": [],
        },
    ),
    handler=_gmail_summarize,
)

TOOL_REGISTRY["draft_gmail"] = AgentTool(
    definition=ToolDefinition(
        name="draft_gmail",
        description=(
            "Create a Gmail draft — does NOT send anything, executes immediately (no "
            "approval needed since nothing leaves the mailbox). Either pass to/subject for "
            "a new draft, or reply_to_message_id to draft a reply (subject/threading pulled "
            "from the original automatically)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "reply_to_message_id": {"type": "string", "description": "Gmail message id to reply to instead of composing new."},
                **_COMPANY_ID_PROP,
            },
            "required": ["body"],
        },
    ),
    handler=_gmail_draft,
)

TOOL_REGISTRY["propose_send_email"] = AgentTool(
    definition=ToolDefinition(
        name="propose_send_email",
        description=(
            "Propose sending an email. This does NOT send it — it only creates a pending "
            "approval request a human must approve from the Approvals page before anything "
            "actually goes out. Always tell the user you've proposed it and it's awaiting approval."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                **_COMPANY_ID_PROP,
            },
            "required": ["to", "subject", "body"],
        },
    ),
    handler=_gmail_propose_send,
)

TOOL_REGISTRY["list_calendar_events"] = AgentTool(
    definition=ToolDefinition(
        name="list_calendar_events",
        description="List upcoming events on the connected Google Calendar — read-only, executes immediately.",
        input_schema={
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Default 10, max 50."},
                "upcoming_only": {"type": "boolean", "description": "Default true — only events starting now or later."},
                **_COMPANY_ID_PROP,
            },
            "required": [],
        },
    ),
    handler=_calendar_list_events,
)

TOOL_REGISTRY["propose_create_calendar_event"] = AgentTool(
    definition=ToolDefinition(
        name="propose_create_calendar_event",
        description=(
            "Propose creating a calendar event. This does NOT create it — it only creates a "
            "pending approval request a human must approve before the event actually gets "
            "added. start/end are ISO 8601 datetimes (or plain dates if all_day=true)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start": {"type": "string", "description": "ISO 8601 datetime, or date if all_day."},
                "end": {"type": "string", "description": "ISO 8601 datetime, or date if all_day."},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses."},
                "all_day": {"type": "boolean"},
                **_COMPANY_ID_PROP,
            },
            "required": ["summary", "start", "end"],
        },
    ),
    handler=_calendar_propose_create_event,
)

TOOL_REGISTRY["list_drive_files"] = AgentTool(
    definition=ToolDefinition(
        name="list_drive_files",
        description=(
            "Search/list files in the connected Google Drive — read-only, executes "
            "immediately. query is bare search terms (matched against file name) or raw "
            "Drive query syntax.\n\n"
            "One shared Google Drive account typically serves every company workspace, "
            "isolated by a Drive folder named exactly like the active company (e.g. "
            "'Primal Penni') rather than a separate connection per company — so when a "
            "company is active, results default to just that company's folder. Set "
            "all_drive=true when the user explicitly asks for their whole/entire Drive, "
            "everything, or account-wide (not just the active company's folder)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "description": "Default 10, max 50."},
                "all_drive": {
                    "type": "boolean",
                    "description": "True to search the whole Drive account, ignoring the active company's folder scoping.",
                },
                **_COMPANY_ID_PROP,
            },
            "required": [],
        },
    ),
    handler=_drive_list_files,
)

TOOL_REGISTRY["read_drive_document"] = AgentTool(
    definition=ToolDefinition(
        name="read_drive_document",
        description=(
            "Read a file's text content from the connected Google Drive (get file_id from "
            "list_drive_files first). Google Docs/Sheets/Slides are exported as text/CSV "
            "automatically; other file types are read as-is if they're text, otherwise "
            "reported as not text-extractable. Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {"file_id": {"type": "string"}, **_COMPANY_ID_PROP},
            "required": ["file_id"],
        },
    ),
    handler=_drive_read_document,
)
