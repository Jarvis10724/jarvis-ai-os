from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A durable, shared container for everything Jarvis produces for one
    business (Company) — the single place a business's Quick-Action output is
    rolled together instead of siloed per session. A Project aggregates
    Conversations (attached WorkspaceSessions), generated Files/Images/
    Components/Research (session artifacts + state), Tasks (Task.project_id),
    Approvals (ApprovalRequest.project_id), a Timeline (ProjectEvent), and
    Memory (MemoryEntry.project_id).

    Every Company has one `is_default` Project that Quick Actions attach to
    when no specific project is chosen; a business can have several Projects
    with a frontend-tracked "active" one (see app.core.project_service for the
    get-or-create/aggregate funnel). This replaces the old behaviour where each
    Quick Action minted its own throwaway project.
    """

    __tablename__ = "projects"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    #: The business (Company) this project belongs to. Nullable so pre-migration
    #: rows and account-wide projects (no active company) are still valid, but
    #: normally set — this is what makes projects re-scope when you switch
    #: business workspaces, mirroring Task/MemoryEntry/Client company scoping.
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active | archived | done
    #: The one auto-created default project per (company[, client]) that Quick
    #: Actions attach to when nothing else is specified.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Set when this project belongs to a Client (Website Builder "Build Client
    #: Website" mode) — keeps client work separate from the company's own.
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
