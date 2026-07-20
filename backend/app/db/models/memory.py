"""
Memory — Jarvis's long-term brain, not just chat history.

Every conversation, file, email, meeting, manufacturer quote, SOP, decision,
contact, product fact, and task Jarvis touches gets written here as a
`MemoryEntry`, searchable later by natural language. Two isolation levels,
both always scoped to `owner_id` (memory never crosses Jarvis users):

  - `company_id` set   -> scoped to one company's workspace. Never leaks
    into another company's memory, same isolation guarantee Products and
    company sections already have.
  - `company_id` NULL  -> global/personal memory — facts about the user
    that aren't tied to a single business (e.g. "I prefer suppliers who
    offer NET-30 terms" applies everywhere, not just one company).

`MemoryLink` is what makes this a graph instead of a flat log: a decision
can link to the quote it was based on, a meeting can link to the contact
who attended it, and so on. See `app.core.memory_service` for the actual
read/write/search API — nothing should query these tables directly outside
that module, so every future integration writes through the same funnel.
"""
from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Flat list, not a DB enum — adding a new kind later is a one-line change
# here, no migration required. `record_memory()` falls back to "other" for
# anything not in this list rather than rejecting the write.
MEMORY_KINDS = [
    "conversation",
    "email",
    "meeting",
    "quote",  # manufacturer / supplier quotes
    "sop",
    "decision",
    "contact",
    "product",
    "goal",  # long-term goals / investment plans — distinct from a one-off "fact"
    "task",
    "file",
    "fact",
    "other",
]

# Every memory belongs to exactly one of these, broadest to narrowest. See
# app.core.memory_scope for the classification rules and consistency
# constraints (which scopes can carry a company_id/project_id and which
# can't) — that module is the only place these should be interpreted.
MEMORY_SCOPES = ["global", "organization", "company", "project", "personal"]


class MemoryEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "memory_entries"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    # Set only for scope="project" (and, unlike company_id above, a project
    # isn't itself tied to one company in the schema, so this is tracked
    # independently rather than implied by company_id).
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)

    # One of MEMORY_SCOPES. Defaults are enforced in app.core.memory_scope,
    # not here — this column just stores whatever that module resolved.
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="organization", index=True)

    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Where this came from — free-form, not validated against an enum, so a
    # brand-new integration (Slack, SMS, ...) never needs a migration to
    # start writing here. e.g. "chat", "manual", "gmail", "google_calendar",
    # "shopify", "amazon", "quickbooks".
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    # An id/url pointing back to the origin object (a Gmail message id, a
    # product id, a calendar event id) so a memory entry can always be
    # traced back to the thing it's about.
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # JSON-encoded float list. Brute-force cosine similarity over these at
    # query time is plenty fast at the scale one business generates memory
    # (hundreds to low thousands of rows) — see memory_service.search_memory.
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Structured metadata that doesn't deserve its own column — participants,
    # amounts, dates, tags, whatever the source naturally provides.
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # How sure whoever/whatever classified this scope actually was, 0-1.
    # Null means "not stated" (e.g. rows written before this column existed,
    # or a source that doesn't have a meaningful confidence signal). The
    # `remember` tool lets Jarvis report its own classification confidence
    # here rather than that judgment disappearing once the tool call
    # returns — low values are exactly the cases it should have asked about
    # instead of guessing, so this is also a way to audit that behavior.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_memory_entries_owner_company", "owner_id", "company_id"),
    )


class MemoryLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A typed, directed edge between two memory entries."""

    __tablename__ = "memory_links"

    from_id: Mapped[str] = mapped_column(ForeignKey("memory_entries.id"), nullable=False, index=True)
    to_id: Mapped[str] = mapped_column(ForeignKey("memory_entries.id"), nullable=False, index=True)
    # e.g. "related_to", "based_on", "mentions", "supersedes" — free-form,
    # same reasoning as `source` above.
    relation: Mapped[str] = mapped_column(String(50), nullable=False, default="related_to")


# Every action an audit row can record. "deleted" is the one case where the
# MemoryEntry itself no longer exists by the time you'd look this up.
MEMORY_AUDIT_ACTIONS = ["created", "updated", "scope_changed", "deleted"]


class MemoryAuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only history of every change to a memory entry. Deliberately
    NOT foreign-keyed to memory_entries — an audit trail that vanishes the
    moment the thing it's auditing gets deleted defeats the point of having
    one, so `memory_entry_id` is just an indexed id, resolved by
    app.core.memory_service rather than enforced by the database."""

    __tablename__ = "memory_audit_log"

    memory_entry_id: Mapped[str] = mapped_column(String(), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
