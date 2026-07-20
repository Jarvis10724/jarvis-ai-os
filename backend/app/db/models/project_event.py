"""
ProjectEvent — the Project Timeline.

An append-only activity log for one Project: every meaningful thing that
happens to a project's work (a Quick-Action session opened, a deliverable
saved, a task created/completed, an approval proposed/decided, a website
built, an image generated, a memory captured) leaves one row here. This is
what the Project workspace renders as its "Timeline" bucket.

Deliberately written through a single funnel — app.core.project_service.
record_project_event — so every module that touches a project logs the same
way, exactly like memory goes through memory_service. `kind` and `source`
are free-form strings (flat list below, same reasoning as MEMORY_KINDS):
adding a new event type is a one-line change, never a migration.
"""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Not a DB enum — `record_project_event` accepts anything and callers stay
# free to add kinds. This list documents the ones Jarvis writes today.
PROJECT_EVENT_KINDS = [
    "session_created",
    "artifact_saved",
    "task_created",
    "task_completed",
    "approval_requested",
    "approval_decided",
    "website_built",
    "image_generated",
    "memory_added",
    "note",
]


class ProjectEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "project_events"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    # Denormalized company scope so the timeline can be filtered/isolated by
    # business without a join, mirroring how other models carry company_id.
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which module wrote this — e.g. "web_builder", "logo_design", "chat",
    # "project_manager". Free-form, same reasoning as MemoryEntry.source.
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="jarvis")
    # An id pointing back to the origin object (a session id, task id, approval
    # id, artifact id) so a timeline row can be traced to what it's about.
    ref_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
