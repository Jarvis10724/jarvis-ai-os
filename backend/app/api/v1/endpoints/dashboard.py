"""
CEO Dashboard support endpoints — today just one: turning a compact digest
of real signals (unread email, pending approvals, today's meetings,
inventory/section flags) into a short AI-generated executive summary, top
3 priorities, and urgent alerts.

Deliberately thin: every underlying number in the digest is fetched by the
frontend from endpoints that already exist (gmail, calendar, approvals,
companies/products) — this endpoint doesn't re-derive any of that, it only
turns an already-real digest into readable prose via the AI provider. If
the AI call fails for any reason (no API key configured, provider error),
a rule-based fallback still returns something useful rather than a 502.
"""
import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.auth.dependencies import CurrentUser
from app.db.models.memory import MemoryEntry
from app.db.session import get_db
from app.logging_config import get_logger

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = get_logger(__name__)

# Free-form `source` tag (see MemoryEntry's docstring) used to find "the
# latest daily briefing" without a dedicated table/migration — briefings
# are just memory entries, searchable/auditable the same as anything else
# Jarvis remembers.
DAILY_BRIEFING_SOURCE = "daily_briefing"


class SummaryDigestIn(BaseModel):
    company_name: str | None = None
    unread_email_count: int = 0
    email_subjects: list[str] = Field(default_factory=list)
    pending_approvals_count: int = 0
    approval_summaries: list[str] = Field(default_factory=list)
    todays_meeting_titles: list[str] = Field(default_factory=list)
    out_of_stock_products: list[str] = Field(default_factory=list)
    needs_rebuild_sections: list[str] = Field(default_factory=list)


class ExecutiveSummaryOut(BaseModel):
    summary: str
    priorities: list[str]
    alerts: list[str]
    recommendations: list[str]


def _rule_based_fallback(digest: SummaryDigestIn) -> ExecutiveSummaryOut:
    """No AI provider configured/reachable — still return something honest
    and useful, built directly from the digest rather than a canned string."""
    alerts: list[str] = []
    if digest.out_of_stock_products:
        alerts.append(f"{len(digest.out_of_stock_products)} product(s) out of stock: " + ", ".join(digest.out_of_stock_products[:3]))
    if digest.needs_rebuild_sections:
        alerts.append(f"{len(digest.needs_rebuild_sections)} section(s) flagged needs-rebuild: " + ", ".join(digest.needs_rebuild_sections[:3]))
    if digest.pending_approvals_count:
        alerts.append(f"{digest.pending_approvals_count} action(s) waiting on your approval.")

    priorities: list[str] = []
    if digest.pending_approvals_count:
        priorities.append("Clear pending approvals.")
    if digest.out_of_stock_products:
        priorities.append(f"Restock: {digest.out_of_stock_products[0]}.")
    if digest.todays_meeting_titles:
        priorities.append(f"Prep for: {digest.todays_meeting_titles[0]}.")
    if digest.unread_email_count:
        priorities.append(f"Triage {digest.unread_email_count} unread email(s).")
    if digest.needs_rebuild_sections:
        priorities.append(f"Rebuild: {digest.needs_rebuild_sections[0]}.")
    priorities = priorities[:3] or ["Nothing urgent — good day to work ahead on the launch."]

    parts = []
    if digest.unread_email_count:
        parts.append(f"{digest.unread_email_count} unread email(s)")
    if digest.todays_meeting_titles:
        parts.append(f"{len(digest.todays_meeting_titles)} meeting(s) today")
    if digest.pending_approvals_count:
        parts.append(f"{digest.pending_approvals_count} approval(s) pending")
    summary = ("Today: " + ", ".join(parts) + ".") if parts else "Nothing pressing — inbox, calendar, and approvals are all clear."

    recommendations: list[str] = []
    if not digest.todays_meeting_titles and not digest.pending_approvals_count:
        recommendations.append("Open calendar is a good window for deep work on the Primal Penni launch.")
    if digest.unread_email_count > 5:
        recommendations.append("Inbox is piling up — consider a batch triage pass before it grows further.")
    if not recommendations:
        recommendations.append("Nothing proactive to suggest right now — everything's on track.")

    return ExecutiveSummaryOut(summary=summary, priorities=priorities, alerts=alerts, recommendations=recommendations)


def _parse_ai_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


@router.post("/executive-summary", response_model=ExecutiveSummaryOut)
async def executive_summary(payload: SummaryDigestIn, current_user: CurrentUser) -> ExecutiveSummaryOut:
    digest_lines = [
        f"Company in focus: {payload.company_name or 'none (account-wide view)'}",
        f"Unread email: {payload.unread_email_count}"
        + (f" — subjects: {'; '.join(payload.email_subjects[:5])}" if payload.email_subjects else ""),
        f"Pending approvals: {payload.pending_approvals_count}"
        + (f" — {'; '.join(payload.approval_summaries[:5])}" if payload.approval_summaries else ""),
        f"Today's meetings: {'; '.join(payload.todays_meeting_titles) if payload.todays_meeting_titles else 'none'}",
        f"Out-of-stock products: {'; '.join(payload.out_of_stock_products) if payload.out_of_stock_products else 'none'}",
        f"Sections flagged needs-rebuild: {'; '.join(payload.needs_rebuild_sections) if payload.needs_rebuild_sections else 'none'}",
    ]
    prompt = (
        "You are Jarvis, an AI COO. Given ONLY the real signals below (no invented numbers), "
        "produce a short executive briefing. Respond with ONLY a JSON object, no prose outside it, "
        'shaped exactly like: {"summary": "1-2 sentence overview", "priorities": ["top priority 1", '
        '"top priority 2", "top priority 3"], "alerts": ["urgent alert", ...], '
        '"recommendations": ["proactive suggestion", ...]}. '
        "priorities must have at most 3 items and are the most urgent must-do actions; alerts may be "
        "empty if nothing is urgent; recommendations are proactive, lower-urgency suggestions for how "
        "to use the day well (may also be empty). Never mention data you weren't given.\n\n"
        + "\n".join(digest_lines)
    )

    try:
        provider = get_ai_provider()
        result = await provider.complete(
            messages=[Message(role="user", content=prompt)],
            temperature=0.4,
            max_tokens=500,
        )
        parsed = _parse_ai_json(result.text)
        if parsed and "summary" in parsed and "priorities" in parsed:
            return ExecutiveSummaryOut(
                summary=str(parsed.get("summary", "")).strip(),
                priorities=[str(p) for p in parsed.get("priorities", [])][:3],
                alerts=[str(a) for a in parsed.get("alerts", [])],
                recommendations=[str(r) for r in parsed.get("recommendations", [])],
            )
        logger.error("executive_summary_unparseable", raw=result.text[:300])
    except Exception as exc:  # noqa: BLE001 — never let a briefing widget 500 the dashboard
        logger.error("executive_summary_ai_failed", error=str(exc))

    return _rule_based_fallback(payload)


# ---------------------------------------------------------------------------
# Daily Briefing — "every morning, automatically, without asking." Stored as
# a memory entry (source="daily_briefing") rather than a dedicated table, so
# no migration is needed and the briefing is automatically part of Jarvis's
# searchable memory like everything else. The full report text is composed
# by whoever calls POST (the frontend's on-demand "Generate now" button
# using real Jarvis signals, or a scheduled task that can also do a live web
# search for investment/market/AI news) — this endpoint just stores/serves
# the latest one; it doesn't dictate what goes in it.
# ---------------------------------------------------------------------------


class DailyBriefingIn(BaseModel):
    content: str
    #: The company this briefing belongs to. Briefings are per-company so
    #: switching workspaces shows that business's own brief (null = the
    #: account-wide/personal brief when no company is active).
    company_id: str | None = None


class DailyBriefingOut(BaseModel):
    content: str
    generated_at: str | None


@router.post("/daily-briefing", response_model=DailyBriefingOut)
async def save_daily_briefing(payload: DailyBriefingIn, current_user: CurrentUser, db: Session = Depends(get_db)) -> DailyBriefingOut:
    entry = MemoryEntry(
        owner_id=current_user.id,
        company_id=payload.company_id,
        scope="company" if payload.company_id else "organization",
        kind="fact",
        title=f"Daily Briefing — {datetime.now(timezone.utc).date().isoformat()}",
        content=payload.content,
        source=DAILY_BRIEFING_SOURCE,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return DailyBriefingOut(content=entry.content, generated_at=entry.created_at.isoformat() if entry.created_at else None)


@router.get("/daily-briefing/latest", response_model=DailyBriefingOut | None)
async def get_latest_daily_briefing(
    current_user: CurrentUser, db: Session = Depends(get_db), company_id: str | None = None
) -> DailyBriefingOut | None:
    q = db.query(MemoryEntry).filter(
        MemoryEntry.owner_id == current_user.id, MemoryEntry.source == DAILY_BRIEFING_SOURCE
    )
    # Scope to the active company so each workspace shows its own brief. A
    # missing/`none` company means the account-wide (null-company) brief.
    if company_id and company_id != "none":
        q = q.filter(MemoryEntry.company_id == company_id)
    else:
        q = q.filter(MemoryEntry.company_id.is_(None))
    entry = q.order_by(MemoryEntry.created_at.desc()).first()
    if not entry:
        return None
    return DailyBriefingOut(content=entry.content, generated_at=entry.created_at.isoformat() if entry.created_at else None)
