from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single invocation of an AI Agent (CEO, Marketing, Finance, Research,
    Operations) against an objective. This IS the agent's persistent memory of
    what it did:

    - `reasoning_log_json`: the ordered decision log — every reasoning step and
      tool call/result, so an agent's work is fully auditable and streamable
      (live during execution, and replayable afterward).
    - `status`: queued | running | awaiting_approval | completed | failed —
      supports background execution (start, poll, restore after a restart).
    - `result`: the agent's final summary.

    Scoped to a user and a single company (the active workspace) — an agent
    only ever operates within the workspace it was launched in.
    """

    __tablename__ = "agent_runs"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    agent_key: Mapped[str] = mapped_column(String(40), nullable=False)  # ceo | marketing | finance | research | operations
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    reasoning_log_json: Mapped[str] = mapped_column(Text, default="[]")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: a Project the agent created/attached its work to, if any.
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    #: For the Autonomous Work Queue (agent_key="work_queue"): the ordered
    #: subtasks a large request was decomposed into, each tracked through
    #: planned → working → waiting_approval → complete. JSON list; NULL for
    #: ordinary single-objective agent runs. Additive/backward-compatible.
    subtasks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
