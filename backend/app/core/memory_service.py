"""
The read/write/search API for Jarvis's memory system — its long-term brain.

`record_memory()` is the single ingestion funnel. Every source of memory
writes through it, and only it:
  - the chat endpoint, after every exchange (kind="conversation")
  - the `remember` agent tool, when Jarvis (or the user, via chat) decides
    something durable is worth saving explicitly (a decision, a quote, a
    fact)
  - every future integration (Gmail, Google Calendar, Shopify, Amazon,
    QuickBooks, Slack, SMS, ...): once a phase wires up real API calls, the
    handler that fetches a new email/event/order/etc. should call
    `record_memory()` with kind="email"/"meeting"/... and source set to the
    integration name. No integration should invent its own storage table
    for "things that happened" — this is that table.

`search_memory()` is natural-language search across everything the owner
can see: their global (company_id=None) memory plus, when a company is
given, that company's memory too. Ranking uses real vector cosine
similarity when the stored embedding and the query embedding used the same
model, and falls back to token-overlap similarity otherwise (see
app.core.embeddings for why two models can coexist).

`link_memories()` / `get_related()` are what make memory a graph instead of
a flat log — e.g. linking a decision to the quote it was based on, or a
meeting to the contact who attended it.
"""
import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.embeddings import cosine_similarity, embed_text, jaccard_similarity, tokenize
from app.core.memory_scope import MEMORY_SCOPES, resolve_scope
from app.db.models.company import Company
from app.db.models.memory import MEMORY_KINDS, MemoryAuditLog, MemoryEntry, MemoryLink
from app.db.models.project import Project
from app.exceptions import NotFoundError, ValidationError


def _entry_owned(db: Session, entry_id: str, owner_id: str) -> MemoryEntry:
    entry = (
        db.query(MemoryEntry)
        .filter(MemoryEntry.id == entry_id, MemoryEntry.owner_id == owner_id)
        .first()
    )
    if not entry:
        raise NotFoundError(f"Memory entry '{entry_id}' not found (or it isn't yours).")
    return entry


def _assert_company_owned(db: Session, company_id: str, owner_id: str) -> None:
    exists = (
        db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    )
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found (or it isn't yours).")


def _assert_project_owned(db: Session, project_id: str, owner_id: str) -> None:
    exists = (
        db.query(Project.id).filter(Project.id == project_id, Project.owner_id == owner_id).first()
    )
    if not exists:
        raise NotFoundError(f"Project '{project_id}' not found (or it isn't yours).")


def _write_audit(
    db: Session,
    *,
    memory_entry_id: str,
    owner_id: str,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> None:
    db.add(
        MemoryAuditLog(
            memory_entry_id=memory_entry_id,
            owner_id=owner_id,
            action=action,
            before_json=json.dumps(before) if before is not None else None,
            after_json=json.dumps(after) if after is not None else None,
            note=note,
        )
    )
    db.commit()


def serialize_entry(entry: MemoryEntry, score: float | None = None) -> dict:
    return {
        "id": entry.id,
        "scope": entry.scope,
        "company_id": entry.company_id,
        "project_id": entry.project_id,
        "kind": entry.kind,
        "title": entry.title,
        "content": entry.content,
        "source": entry.source,
        "source_ref": entry.source_ref,
        "confidence": entry.confidence,
        "extra": json.loads(entry.extra_json) if entry.extra_json else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        **({"score": round(score, 4)} if score is not None else {}),
    }


def serialize_audit(row: MemoryAuditLog) -> dict:
    return {
        "id": row.id,
        "action": row.action,
        "before": json.loads(row.before_json) if row.before_json else None,
        "after": json.loads(row.after_json) if row.after_json else None,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def record_memory(
    db: Session,
    *,
    owner_id: str,
    kind: str,
    title: str,
    content: str,
    company_id: str | None = None,
    project_id: str | None = None,
    scope: str | None = None,
    confidence: float | None = None,
    source: str = "manual",
    source_ref: str | None = None,
    extra: dict | None = None,
    link_to: list[str] | None = None,
    relation: str = "related_to",
) -> MemoryEntry:
    if kind not in MEMORY_KINDS:
        kind = "other"
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    resolved_scope, resolved_company_id, resolved_project_id = resolve_scope(
        scope=scope, company_id=company_id, project_id=project_id
    )
    if resolved_company_id:
        _assert_company_owned(db, resolved_company_id, owner_id)
    if resolved_project_id:
        _assert_project_owned(db, resolved_project_id, owner_id)

    embedding, model = await embed_text(f"{title}\n\n{content}")
    entry = MemoryEntry(
        owner_id=owner_id,
        company_id=resolved_company_id,
        project_id=resolved_project_id,
        scope=resolved_scope,
        kind=kind,
        title=title[:500],
        content=content,
        source=source,
        source_ref=source_ref,
        confidence=confidence,
        embedding_json=json.dumps(embedding),
        embedding_model=model,
        extra_json=json.dumps(extra) if extra else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    if link_to:
        for other_id in link_to:
            # Only link to entries the same owner actually has — silently
            # skip anything else rather than failing the whole write.
            if db.query(MemoryEntry).filter(MemoryEntry.id == other_id, MemoryEntry.owner_id == owner_id).first():
                db.add(MemoryLink(from_id=entry.id, to_id=other_id, relation=relation))
        db.commit()

    _write_audit(db, memory_entry_id=entry.id, owner_id=owner_id, action="created", after=serialize_entry(entry))

    return entry


async def update_memory(
    db: Session,
    *,
    owner_id: str,
    entry_id: str,
    title: str | None = None,
    content: str | None = None,
    kind: str | None = None,
    source_ref: str | None = None,
    confidence: float | None = None,
    extra: dict | None = None,
) -> MemoryEntry:
    """Edits the content of an existing entry — never its scope/company/
    project, which is what move_memory_scope is for. Re-embeds if the title
    or content actually changed. Writes an 'updated' audit row with a
    before/after snapshot either way."""
    entry = _entry_owned(db, entry_id, owner_id)
    before = serialize_entry(entry)

    changed_text = False
    if title is not None and title != entry.title:
        entry.title = title[:500]
        changed_text = True
    if content is not None and content != entry.content:
        entry.content = content
        changed_text = True
    if kind is not None:
        entry.kind = kind if kind in MEMORY_KINDS else "other"
    if source_ref is not None:
        entry.source_ref = source_ref
    if confidence is not None:
        entry.confidence = max(0.0, min(1.0, confidence))
    if extra is not None:
        entry.extra_json = json.dumps(extra)

    if changed_text:
        embedding, model = await embed_text(f"{entry.title}\n\n{entry.content}")
        entry.embedding_json = json.dumps(embedding)
        entry.embedding_model = model

    db.commit()
    db.refresh(entry)

    _write_audit(
        db,
        memory_entry_id=entry.id,
        owner_id=owner_id,
        action="updated",
        before=before,
        after=serialize_entry(entry),
    )
    return entry


async def move_memory_scope(
    db: Session,
    *,
    owner_id: str,
    entry_id: str,
    scope: str,
    company_id: str | None = None,
    project_id: str | None = None,
    note: str | None = None,
) -> MemoryEntry:
    """Moves an entry to a different scope (and, implicitly, a different
    company/project) — the one thing update_memory() deliberately can't do,
    so a move is always an explicit, auditable action rather than something
    that can happen as a side effect of an unrelated content edit."""
    entry = _entry_owned(db, entry_id, owner_id)
    before = serialize_entry(entry)

    resolved_scope, resolved_company_id, resolved_project_id = resolve_scope(
        scope=scope, company_id=company_id, project_id=project_id
    )
    if resolved_company_id:
        _assert_company_owned(db, resolved_company_id, owner_id)
    if resolved_project_id:
        _assert_project_owned(db, resolved_project_id, owner_id)

    entry.scope = resolved_scope
    entry.company_id = resolved_company_id
    entry.project_id = resolved_project_id
    db.commit()
    db.refresh(entry)

    auto_note = f"scope: {before['scope']} -> {resolved_scope}"
    _write_audit(
        db,
        memory_entry_id=entry.id,
        owner_id=owner_id,
        action="scope_changed",
        before=before,
        after=serialize_entry(entry),
        note=f"{auto_note} — {note}" if note else auto_note,
    )
    return entry


def get_audit_log(db: Session, *, owner_id: str, entry_id: str) -> list[dict]:
    """Not gated on the entry still existing — a 'deleted' audit row is
    exactly the case where it won't. Ownership is checked against the audit
    rows' own owner_id instead of going through _entry_owned()."""
    rows = (
        db.query(MemoryAuditLog)
        .filter(MemoryAuditLog.memory_entry_id == entry_id, MemoryAuditLog.owner_id == owner_id)
        .order_by(MemoryAuditLog.created_at.desc())
        .all()
    )
    return [serialize_audit(r) for r in rows]


async def search_memory(
    db: Session,
    *,
    owner_id: str,
    query: str,
    company_id: str | None = "any",
    kind: str | None = None,
    scope: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """`company_id`: "any" (default) searches everything the owner has —
    global memory plus every company's. A real company id searches that
    company's memory plus global memory (so personal facts still surface).
    `None` explicitly searches only global memory.

    `scope`: an optional additional filter narrowing to exactly one of
    MEMORY_SCOPES (e.g. "personal" to exclude business memory from a
    search) — independent of the company_id bucketing above, since global/
    organization/personal all share company_id=None.
    """
    q = db.query(MemoryEntry).filter(MemoryEntry.owner_id == owner_id)
    if company_id == "any":
        pass
    elif company_id is None:
        q = q.filter(MemoryEntry.company_id.is_(None))
    else:
        q = q.filter(or_(MemoryEntry.company_id == company_id, MemoryEntry.company_id.is_(None)))
    if kind:
        if kind not in MEMORY_KINDS:
            raise ValidationError(f"Unknown memory kind '{kind}'. Valid: {', '.join(MEMORY_KINDS)}")
        q = q.filter(MemoryEntry.kind == kind)
    if scope:
        if scope not in MEMORY_SCOPES:
            raise ValidationError(f"Unknown memory scope '{scope}'. Valid: {', '.join(MEMORY_SCOPES)}")
        q = q.filter(MemoryEntry.scope == scope)

    entries = q.all()
    if not entries or not query.strip():
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return [serialize_entry(e) for e in entries[:limit]]

    query_vec, query_model = await embed_text(query)
    query_tokens = set(tokenize(query))

    scored: list[tuple[float, MemoryEntry]] = []
    for entry in entries:
        stored_vec = json.loads(entry.embedding_json) if entry.embedding_json else []
        if stored_vec and entry.embedding_model == query_model:
            score = cosine_similarity(query_vec, stored_vec)
        else:
            entry_tokens = set(tokenize(f"{entry.title} {entry.content}"))
            score = jaccard_similarity(query_tokens, entry_tokens)
        scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [serialize_entry(e, score) for score, e in scored[:limit]]


def get_entry_with_links(db: Session, *, owner_id: str, entry_id: str) -> dict:
    entry = _entry_owned(db, entry_id, owner_id)
    outgoing = db.query(MemoryLink).filter(MemoryLink.from_id == entry.id).all()
    incoming = db.query(MemoryLink).filter(MemoryLink.to_id == entry.id).all()

    related_ids = {link.to_id for link in outgoing} | {link.from_id for link in incoming}
    related_entries = {
        e.id: e for e in db.query(MemoryEntry).filter(MemoryEntry.id.in_(related_ids)).all()
    } if related_ids else {}

    result = serialize_entry(entry)
    result["links"] = [
        {"relation": link.relation, "direction": "to", "entry": serialize_entry(related_entries[link.to_id])}
        for link in outgoing
        if link.to_id in related_entries
    ] + [
        {"relation": link.relation, "direction": "from", "entry": serialize_entry(related_entries[link.from_id])}
        for link in incoming
        if link.from_id in related_entries
    ]
    return result


def link_memories(db: Session, *, owner_id: str, from_id: str, to_id: str, relation: str = "related_to") -> None:
    _entry_owned(db, from_id, owner_id)
    _entry_owned(db, to_id, owner_id)
    db.add(MemoryLink(from_id=from_id, to_id=to_id, relation=relation))
    db.commit()


def delete_memory(db: Session, *, owner_id: str, entry_id: str) -> None:
    entry = _entry_owned(db, entry_id, owner_id)
    before = serialize_entry(entry)
    db.query(MemoryLink).filter(or_(MemoryLink.from_id == entry.id, MemoryLink.to_id == entry.id)).delete()
    db.delete(entry)
    db.commit()
    # Written after the row is gone — memory_entry_id is a plain indexed
    # column, not a foreign key, precisely so this audit row survives.
    _write_audit(db, memory_entry_id=entry_id, owner_id=owner_id, action="deleted", before=before)


async def reembed_all(db: Session, *, owner_id: str) -> int:
    """Re-embeds every memory entry for one owner with whatever the current
    active embedding method is — meant to be run once after adding an
    OPENAI_API_KEY so existing entries upgrade from the lexical fallback to
    real semantic embeddings. Returns the count updated."""
    entries = db.query(MemoryEntry).filter(MemoryEntry.owner_id == owner_id).all()
    count = 0
    for entry in entries:
        embedding, model = await embed_text(f"{entry.title}\n\n{entry.content}")
        entry.embedding_json = json.dumps(embedding)
        entry.embedding_model = model
        count += 1
    db.commit()
    return count
