from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkspaceSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A persistent Quick-Action workspace session — one running "project
    application" (Website Studio, Logo Studio, Product Studio, Research,
    Code, Automation). Everything the user does in a workspace lives here so
    it survives reloads/restarts and can be switched between without losing
    state:

    - `messages_json`: the full conversation history (list of {role, content, ts}).
    - `artifacts_json`: saved deliverables. Each is a dict
      {id, kind, title, content, version, stage, ts}; older rows may only
      have {title, content} and are read leniently.
    - `state_json`: the action-specific *structured* workspace state — the
      thing that makes each Quick Action a real studio rather than a chat.
      Website keeps sitemap/copy/design/versions here; Logo keeps
      brief/concepts/revisions/exports; Research keeps plan/sources/citations;
      Automation keeps trigger/actions/conditions/enabled; etc. It's merged
      from a fenced ``jarvis-state`` block the model emits, so it stays
      AI-generated, never mock data.
    - `project_id`: the real Project this workspace is attached to (Tasks the
      workspace creates hang off it), so workspace output shows up in the
      normal Project Manager too.

    Scoped to a user and optionally a company (Jarvis is multi-company), so
    the same action can have separate, isolated sessions per workspace.
    """

    __tablename__ = "workspace_sessions"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    #: which Quick Action — matches the builtin plugin names
    #: (web_builder | logo_design | product_creation | deep_research |
    #: code_writer | automation).
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")  # active | archived
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    artifacts_json: Mapped[str] = mapped_column(Text, default="[]")
    #: Action-specific structured workspace state (JSON object). See the class
    #: docstring — this is what turns each Quick Action into its own studio.
    state_json: Mapped[str] = mapped_column(Text, default="{}")
