from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PluginConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user, per-plugin settings (enabled/disabled, JSON config blob)."""

    __tablename__ = "plugin_configs"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    plugin_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # arbitrary JSON, serialized
