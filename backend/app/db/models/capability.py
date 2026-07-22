"""
Shared infrastructure every external-service Capability (Gmail, Calendar,
Shopify, QuickBooks, Amazon, ...) plugs into — see
app.core.capabilities_registry for what a Capability is, and
app.core.capability_service for the read/write funnel every integration is
meant to go through instead of reinventing approval, audit, permissions,
health checks, or scheduling per integration.

Four tables:

  - CapabilityConfig: one row per (owner, capability, company) —
    enabled/disabled, granted permissions (which named actions this
    company is allowed to attempt), and cached health-check state. Company
    isolation for "any future company workspace can enable or disable
    [a capability] independently" comes from company_id being nullable
    (null = account-wide default) exactly like IntegrationCredential
    already works, and exactly like MemoryEntry's scope columns.

  - ApprovalRequest: a proposed side-effecting action, sitting in
    pending/approved/rejected/expired/executed until a human decides.
    Nothing executes an approval-gated action without one of these hitting
    "approved" first.

  - CapabilityAuditLog: append-only, deliberately NOT foreign-keyed to
    ApprovalRequest — same reasoning as MemoryAuditLog: an audit trail that
    disappears when the thing it's auditing is deleted defeats the point.
    Every action a capability takes (approved writes AND direct reads
    alike) leaves a row here.

  - ScheduledJob: a capability action to run on a recurring cadence
    (background agents). The actual dispatch loop (reading `schedule_cron`,
    deciding what's due, executing, then calling back into
    capability_service) is built alongside the first capability that
    actually needs it — this table plus the due-job lookup in
    capability_service is the reusable part.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

APPROVAL_STATUSES = ["pending", "approved", "rejected", "expired", "executed"]
CAPABILITY_HEALTH_STATUSES = ["unknown", "ok", "error", "disconnected"]
CAPABILITY_AUDIT_ACTIONS = [
    "enabled",
    "disabled",
    "permissions_changed",
    "proposed",
    "edited",
    "approved",
    "rejected",
    "executed",
    "read",
    "health_check",
    "scheduled",
    "unscheduled",
]


class CapabilityConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-company (or account-wide, if company_id is null) settings for one
    capability. This is deliberately a separate table from PluginConfig —
    PluginConfig is internal AI plugins (logo design, deep research, ...)
    with no OAuth/permissions/health concept; Capabilities are external
    services with all three, so they get their own model rather than
    overloading a table shaped for something else."""

    __tablename__ = "capability_configs"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    #: matches app.core.capabilities_registry.CAPABILITIES keys
    capability_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSON list of action names this (owner, company, capability) may
    # attempt. Null means "use CapabilityDefinition.default_permissions"
    # (every read-only action, no approval-gated ones) rather than an
    # empty allow-list — see capability_service.is_action_permitted.
    permissions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Arbitrary per-capability settings blob (e.g. which Drive folder to
    # watch, which Shopify location id to report inventory for).
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Health-check cache, refreshed by capability_service.run_health_check
    # (which calls the underlying BaseIntegration.is_connected() and
    # records the result here) rather than hitting the external API on
    # every page load.
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    health_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A proposed external write, waiting on (or resolved by) human review."""

    __tablename__ = "approval_requests"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    #: The Project this approval rolls up to, if it was proposed inside a
    #: project's work. Null for company-level approvals (e.g. an ad-hoc Gmail
    #: send from the Gmail page) that aren't tied to a specific project.
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    capability_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # The proposed call's arguments, e.g. {"to": "...", "subject": "...",
    # "body": "..."} — whatever the capability's action needs to actually
    # run once approved.
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    # --- The brief: what a human needs in order to decide -------------------
    # Filled by app.core.approval_brief (deterministically, per action type) or
    # overridden by the proposer. Nullable so every pre-existing row stays
    # valid; the brief is rebuilt on read when these are empty.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: JSON list of plain-language risk strings.
    risks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: How to undo this if it turns out wrong — or an honest statement that it
    #: can't be undone (an unsent email can't be recalled).
    undo_plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Plan grouping: many approvals that belong to one execution plan ----
    #: Ties this request to the plan it belongs to (a Work Queue run id), so a
    #: whole plan can be approved at once and executed in order. Null for
    #: standalone approvals.
    group_id: Mapped[str | None] = mapped_column(String(), nullable=True, index=True)
    group_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Position within the plan — execution order.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- The outcome, persisted so EVERY device sees the same thing ---------
    # These used to exist only in the HTTP response to whichever device pressed
    # Approve. The other device polled the queue and could see that a request
    # was approved but never why it failed or what it verified.
    #: Structured execution result — verified value, external API response.
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Why it didn't run, in the same words both devices display.
    execution_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Which device the decision was made from ("iPhone", "desktop", …).
    decided_device: Mapped[str | None] = mapped_column(String(40), nullable=True)


class CapabilityAuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only history of every capability action — approved writes,
    direct reads, enable/disable/permission changes, and health checks
    alike. Not foreign-keyed to approval_requests (same reasoning as
    MemoryAuditLog: the log has to survive the thing it's about)."""

    __tablename__ = "capability_audit_log"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    capability_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Plain string, not a foreign key — same survives-the-parent reasoning
    # as memory_entry_id on MemoryAuditLog.
    approval_request_id: Mapped[str | None] = mapped_column(String(), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScheduledJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A capability action to run on a recurring cadence — the data half of
    'background agents'; the dispatch loop is built with the first
    capability that needs one."""

    __tablename__ = "scheduled_jobs"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    capability_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 5-field cron expression, interpreted by whatever runs the dispatch
    # loop — not parsed/validated by this model or by capability_service.
    schedule_cron: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
