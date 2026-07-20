from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single actionable item — either nested under a Project (can be run
    by a plugin, e.g. 'generate logo concepts') or a standalone company-
    scoped to-do (the Project Manager kanban board). project_id is nullable
    so a task can exist as either."""

    __tablename__ = "tasks"

    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # backlog | in_progress | review | done — matches the Project Manager
    # kanban's columns exactly (todo/failed only apply to plugin-run tasks).
    status: Mapped[str] = mapped_column(String(50), default="backlog")
    plugin_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    division: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(20), nullable=True)

    project: Mapped["Project | None"] = relationship(back_populates="tasks")
