from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A unit of work Jarvis is helping with — a website build, a logo job,
    a research task, etc. Tasks (below) belong to a project."""

    __tablename__ = "projects"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active | archived | done

    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
