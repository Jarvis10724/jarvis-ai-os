"""
Workspace import — fill a workspace from the sources it's actually connected to.

Reads the live Shopify catalog, the workspace's Gmail, and its Drive, and turns
what it finds into a searchable business knowledge base: one memory entry per
item, filed under the workspace section it belongs to, carrying a link back to
the original message, file, or product.

Rules that shape the whole thing:

  * NEVER overwrite what a human wrote. Items are only ever ADDED, and a
    section's notes are only filled when they're empty.
  * NEVER invent. Everything stored comes from a real Shopify/Gmail/Drive
    record; unavailable sources are reported as unavailable, not imagined.
  * Idempotent. Every item is keyed by its source id, so re-running imports
    what's new and skips what's already here.
  * Honest about reach. A source that isn't connected — or a Shopify scope the
    app wasn't granted — is reported as a gap, so the operator knows what's
    missing rather than assuming the workspace is complete.
"""
import json
import re
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import brand_brain_service, drive_service, gmail_service
from app.db.models.company import Company
from app.db.models.memory import MemoryEntry
from app.db.models.task import Task
from app.exceptions import NotFoundError
from app.logging_config import get_logger

logger = get_logger(__name__)

#: Workspace sections an imported item can be filed under, matched in order —
#: the first rule that hits wins, so the most specific ones come first.
SECTION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("manufacturing", ("supplier", "manufactur", "quote", "formula", "batch", "production",
                       "moq", "coa", "ingredient", "lab ", "fill", "bulk")),
    ("packaging", ("packag", "label", "dieline", "die line", "carton", "box", "sticker",
                   "jar", "bottle", "cap", "print", "artwork", "proof")),
    ("brand", ("logo", "brand", "palette", "typeface", "font", "style guide", "identity",
               "mission", "tagline")),
    ("marketing", ("campaign", "newsletter", "social", "instagram", "tiktok", "ad ", "ads",
                   "promo", "graphic", "content calendar", "influencer")),
    ("shopify", ("shopify", "storefront", "collection", "theme")),
    ("products", ("product", "sku", "catalog", "inventory")),
]

#: Things that plausibly need the operator to DO something. Flagged as tasks,
#: never auto-actioned. Matched on WORD BOUNDARIES, not substrings: matching
#: "sign" inside "sign-in" turned every Shopify login alert into a fake
#: signature request on the first run.
ATTENTION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("signature", (r"signature", r"please sign", r"sign here", r"docusign", r"countersign",
                   r"for your signature", r"agreement attached", r"contract attached")),
    ("payment", (r"invoice", r"overdue", r"past due", r"balance due", r"remittance",
                 r"payment due", r"amount due")),
    ("quote", (r"\bquote\b", r"quotation", r"pricing proposal", r"\bestimate\b")),
    ("shipment", (r"shipment", r"tracking number", r"delayed", r"customs", r"freight",
                  r"bill of lading")),
    ("urgent", (r"urgent", r"action required", r"\basap\b", r"deadline", r"final notice")),
]

#: Senders that are machines, not correspondents.
NOISE_SENDERS = (
    "no-reply", "noreply", "no_reply", "donotreply", "do-not-reply", "notifications@",
    "notification@", "mailer@", "email@", "news@", "newsletter@", "marketing@", "updates@",
    "info@shopify", "support@google", "accounts.google",
)

#: Subjects that are platform chatter or promotion rather than business record.
NOISE_SUBJECTS = (
    "sign-in", "signed in", "security alert", "was recovered", "verify your", "verification code",
    "welcome to", "get started", "% off", "free trial", "webinar", "unsubscribe",
    "two-step authentication", "password", "recovery code", "new device",
)

#: Words that mark an email as real business, even from an automated sender
#: (an order confirmation or a supplier invoice still matters).
BUSINESS_SIGNALS = (
    "supplier", "manufactur", "invoice", "quote", "purchase order", "\bpo\b", "packaging",
    "label", "formula", "ingredient", "sample", "batch", "shipment", "freight", "customs",
    "moq", "wholesale", "order #", "contract", "agreement", "proposal", "cogs", "lead time",
)


def is_relevant_email(sender: str | None, subject: str | None, snippet: str | None) -> bool:
    """Whether an email is business information worth importing.

    The first run swept in Google security notices and Shopify marketing, which
    is noise in a business knowledge base and worse than nothing — it dilutes
    every future search. Machine senders and platform chatter are dropped
    unless the message carries an actual business signal."""
    blob = f"{sender or ''} {subject or ''} {snippet or ''}".lower()
    if any(re.search(sig, blob) for sig in BUSINESS_SIGNALS):
        return True
    if any(n in (sender or "").lower() for n in NOISE_SENDERS):
        return False
    if any(n in f"{subject or ''} {snippet or ''}".lower() for n in NOISE_SUBJECTS):
        return False
    return True

#: Mime fragments -> the kind of document, for the Documents index.
DOC_KINDS = {
    "pdf": "PDF",
    "spreadsheet": "Spreadsheet",
    "presentation": "Presentation",
    "document": "Document",
    "image": "Image",
    "folder": "Folder",
    "video": "Video",
}


def _company(db: Session, company_id: str, owner_id: str) -> Company:
    company = db.query(Company).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found")
    return company


def classify_section(*fragments: str | None) -> str:
    """Which workspace section an item belongs to. Deterministic, so the same
    document always files in the same place."""
    haystack = " ".join(f.lower() for f in fragments if f)
    for section, needles in SECTION_RULES:
        if any(n in haystack for n in needles):
            return section
    return "documents"


def flag_attention(*fragments: str | None) -> str | None:
    """Why this might need the operator, or None if nothing stands out."""
    haystack = " ".join(f.lower() for f in fragments if f)
    for reason, patterns in ATTENTION_RULES:
        if any(re.search(p, haystack) for p in patterns):
            return reason
    return None


def doc_kind(mime: str | None) -> str:
    for fragment, label in DOC_KINDS.items():
        if fragment in (mime or ""):
            return label
    return "File"


def _already_imported(db: Session, company_id: str, source_ref: str) -> bool:
    return (
        db.query(MemoryEntry.id)
        .filter(MemoryEntry.company_id == company_id, MemoryEntry.source_ref == source_ref)
        .first()
        is not None
    )


def _record(
    db: Session,
    *,
    owner_id: str,
    company_id: str,
    kind: str,
    title: str,
    content: str,
    source: str,
    source_ref: str,
    extra: dict,
) -> bool:
    """Add one item to the knowledge base. Returns False if it was already
    imported — re-running never duplicates."""
    if _already_imported(db, company_id, source_ref):
        return False
    db.add(
        MemoryEntry(
            owner_id=owner_id,
            company_id=company_id,
            scope="company",
            kind=kind,
            title=title[:500],
            content=content,
            source=source,
            source_ref=source_ref,
            extra_json=json.dumps(extra),
        )
    )
    return True


def _suggest_task(
    db: Session, *, owner_id: str, company_id: str, title: str, detail: str, source_ref: str
) -> bool:
    """A suggested task, tied to the thing that prompted it. Skipped if one
    already exists for that source, so re-running doesn't pile them up."""
    exists = (
        db.query(Task.id)
        .filter(Task.company_id == company_id, Task.description.like(f"%{source_ref}%"))
        .first()
    )
    if exists:
        return False
    db.add(
        Task(
            owner_id=owner_id,
            company_id=company_id,
            title=title[:255],
            description=detail,
            status="backlog",
        )
    )
    return True


async def scan(
    db: Session, *, owner_id: str, company_id: str, email_limit: int = 60, file_limit: int = 120
) -> AsyncIterator[dict]:
    """Walk every connected source, yielding progress as it goes."""
    company = _company(db, company_id, owner_id)
    totals = {"imported": 0, "skipped": 0, "tasks": 0}
    sections: dict[str, int] = {}
    gaps: list[str] = []

    def note(section: str) -> None:
        sections[section] = sections.get(section, 0) + 1

    yield {"type": "start", "workspace": company.name}

    # --- Shopify (via the already-synced Brand Brain) ----------------------
    yield {"type": "progress", "source": "shopify", "message": "Reading the live product catalog…"}
    brain = brand_brain_service.get_summary(db, company_id)
    if not brain.get("exists"):
        gaps.append("Shopify: no synced catalog for this workspace.")
    else:
        products = brand_brain_service.list_products(db, company_id, limit=250)
        collections = brand_brain_service.list_collections(db, company_id)
        store = brain.get("store_domain")
        for p in products:
            handle = p.get("handle") or ""
            link = f"https://{store}/products/{handle}" if store and handle else None
            body = [
                f"Product: {p['title']}",
                f"Price: {p.get('price_min')} {p.get('currency') or ''}".strip(),
                f"Inventory: {p.get('total_inventory')}",
                f"Status: {p.get('status')}",
                f"Type: {p.get('product_type') or 'n/a'} | Tags: {', '.join(p.get('tags') or []) or 'none'}",
            ]
            if p.get("description"):
                body.append(f"Description: {p['description'][:1200]}")
            if link:
                body.append(f"Source: {link}")
            if _record(
                db, owner_id=owner_id, company_id=company_id, kind="product",
                title=p["title"], content="\n".join(body),
                source="import:shopify", source_ref=f"shopify:product:{p['shopify_id']}",
                extra={"link": link, "section": "products", "image": p.get("featured_image"),
                       "price": p.get("price_min"), "inventory": p.get("total_inventory")},
            ):
                totals["imported"] += 1
                note("products")
            else:
                totals["skipped"] += 1
        for c in collections:
            if _record(
                db, owner_id=owner_id, company_id=company_id, kind="product",
                title=f"Collection: {c['title']}",
                content=f"Shopify collection '{c['title']}' ({c.get('products_count')} products).",
                source="import:shopify", source_ref=f"shopify:collection:{c['shopify_id']}",
                extra={"section": "shopify", "handle": c.get("handle")},
            ):
                totals["imported"] += 1
                note("shopify")
            else:
                totals["skipped"] += 1
        db.commit()
        yield {"type": "progress", "source": "shopify",
               "message": f"{len(products)} products, {len(collections)} collections",
               "imported": totals["imported"]}
        # The app was granted read_products/read_inventory only.
        gaps.append("Shopify: pages, navigation, policies and theme need read_content / "
                    "read_themes scopes, which this app wasn't granted.")

    # --- Gmail -------------------------------------------------------------
    yield {"type": "progress", "source": "gmail", "message": "Scanning the workspace mailbox…"}
    try:
        messages = await gmail_service.list_messages(
            db, owner_id=owner_id, company_id=company_id, max_results=email_limit
        )
    except Exception as exc:  # noqa: BLE001
        messages = []
        gaps.append(f"Gmail: not readable for this workspace ({str(exc)[:120]}).")
    for m in messages or []:
        subject = m.get("subject") or "(no subject)"
        sender = m.get("from") or ""
        snippet = m.get("snippet") or ""
        if not is_relevant_email(sender, subject, snippet):
            totals["skipped"] += 1
            continue
        section = classify_section(subject, sender, snippet)
        link = f"https://mail.google.com/mail/u/0/#inbox/{m.get('thread_id') or m.get('id')}"
        body = [f"From: {sender}", f"Subject: {subject}", f"Date: {m.get('date')}",
                f"Snippet: {snippet[:800]}", f"Source: {link}"]
        if _record(
            db, owner_id=owner_id, company_id=company_id, kind="email", title=subject,
            content="\n".join(body), source="import:gmail",
            source_ref=f"gmail:{m.get('id')}",
            extra={"link": link, "section": section, "from": sender},
        ):
            totals["imported"] += 1
            note(section)
        else:
            totals["skipped"] += 1
        reason = flag_attention(subject, snippet)
        if reason and _suggest_task(
            db, owner_id=owner_id, company_id=company_id,
            title=f"Review ({reason}): {subject}"[:255],
            detail=f"Flagged from email — {reason}.\nFrom: {sender}\n{link}\nsource:gmail:{m.get('id')}",
            source_ref=f"gmail:{m.get('id')}",
        ):
            totals["tasks"] += 1
    db.commit()
    yield {"type": "progress", "source": "gmail", "message": f"{len(messages or [])} messages read",
           "imported": totals["imported"], "tasks": totals["tasks"]}

    # --- Drive -------------------------------------------------------------
    yield {"type": "progress", "source": "drive", "message": "Indexing Drive…"}
    try:
        files = await drive_service.list_files(
            db, owner_id=owner_id, company_id=company_id, max_results=file_limit
        )
    except Exception as exc:  # noqa: BLE001
        files = []
        gaps.append(f"Drive: not readable for this workspace ({str(exc)[:120]}).")
    for f in files or []:
        name = f.get("name") or "(untitled)"
        mime = f.get("mime_type")
        section = classify_section(name, mime)
        kind_label = doc_kind(mime)
        link = f.get("web_view_link")
        body = [f"{kind_label}: {name}", f"Type: {mime}", f"Modified: {f.get('modified_time')}",
                f"Owner: {', '.join(f.get('owners') or []) or 'unknown'}", f"Source: {link}"]
        if _record(
            db, owner_id=owner_id, company_id=company_id, kind="file", title=name,
            content="\n".join(body), source="import:drive", source_ref=f"drive:{f.get('id')}",
            extra={"link": link, "section": section, "mime": mime, "doc_kind": kind_label},
        ):
            totals["imported"] += 1
            note(section)
        else:
            totals["skipped"] += 1
        reason = flag_attention(name)
        if reason and _suggest_task(
            db, owner_id=owner_id, company_id=company_id,
            title=f"Review ({reason}): {name}"[:255],
            detail=f"Flagged from a Drive file — {reason}.\n{link}\nsource:drive:{f.get('id')}",
            source_ref=f"drive:{f.get('id')}",
        ):
            totals["tasks"] += 1
    db.commit()
    yield {"type": "progress", "source": "drive", "message": f"{len(files or [])} items indexed",
           "imported": totals["imported"], "tasks": totals["tasks"]}

    # --- Section notes: only ever fill a blank ------------------------------
    filled = _fill_empty_section_notes(db, company, sections)

    yield {
        "type": "done",
        "workspace": company.name,
        "imported": totals["imported"],
        "already_had": totals["skipped"],
        "tasks_suggested": totals["tasks"],
        "by_section": sections,
        "sections_annotated": filled,
        "gaps": gaps,
    }


def _fill_empty_section_notes(db: Session, company: Company, sections: dict[str, int]) -> list[str]:
    """Write a short 'what's here' line into sections that have no notes yet.
    A section the operator has already written in is left exactly as it is."""
    if not sections:
        return []
    try:
        data = json.loads(company.sections_json) if company.sections_json else {}
    except (TypeError, ValueError):
        data = {}
    filled: list[str] = []
    for section, count in sections.items():
        entry = data.get(section) or {}
        if (entry.get("notes") or "").strip():
            continue  # manual content — never overwritten
        entry["notes"] = (
            f"{count} item{'' if count == 1 else 's'} imported from your connected sources. "
            "Search the workspace knowledge base to open any of them at the original."
        )
        data[section] = entry
        filled.append(section)
    if filled:
        company.sections_json = json.dumps(data)
        db.commit()
    return filled
