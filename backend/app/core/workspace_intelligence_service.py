"""
Workspace Intelligence (Phase 3 #4) — an AI reading of what's actually
happening in a workspace, not another wall of counters.

The Executive Dashboard shows the numbers; this explains them: where the
workspace stands, what's at risk, what's being ignored, and what to do next.
It reads only what the workspace already owns (its projects, tasks, approvals,
agent runs, memory, Brand Brain, integrations) — every signal is workspace
scoped, so one workspace's analysis can never be built from another's data.

Recommendations come back as real work: each one can be sent straight to the
Work Queue, where the existing approval gate still governs anything with
real-world consequences.
"""
import json
import time

from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.core import brand_brain_service
from app.db.models.agent_run import AgentRun
from app.db.models.capability import ApprovalRequest
from app.db.models.company import Company
from app.db.models.memory import MemoryEntry
from app.db.models.project import Project
from app.db.models.task import Task
from app.exceptions import NotFoundError

# An analysis costs an AI call, so hold it briefly — revisiting the page or
# asking again shouldn't re-bill or re-think unchanged data.
_CACHE_TTL_SECONDS = 900
_cache: dict[str, tuple[float, dict]] = {}

_SYSTEM = (
    "You are the chief of staff for this workspace. You are given its REAL current signals. "
    "Read them and report like an operator, not a dashboard: what state is this workspace in, "
    "what deserves attention, what is being ignored, and what should happen next.\n"
    "Be specific and reference the actual numbers/names you were given. Never invent data — if a "
    "signal is missing, say what's missing and treat that as a finding.\n"
    "Each recommendation must be a concrete next action, phrased so it could be handed to an "
    "assistant to carry out. Mark real_world=true if carrying it out would send an email, "
    "purchase, publish, change inventory, or move money.\n"
    'Respond with ONLY JSON: {"headline":"<one sentence, the state of the workspace>",'
    '"state_of_play":"<2-4 sentences>","signals":[{"label":"...","detail":"..."}],'
    '"risks":[{"title":"...","detail":"..."}],'
    '"recommendations":[{"title":"...","why":"...","real_world":false}]}'
)


def _owned_company(db: Session, company_id: str, owner_id: str) -> Company:
    company = (
        db.query(Company).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    )
    if not company:
        raise NotFoundError(f"Company '{company_id}' not found")
    return company


def _extract_json(text: str) -> dict:
    s = text.strip()
    if "```" in s:
        parts = s.split("```")
        s = parts[1] if len(parts) > 1 else s
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    a, b = s.find("{"), s.rfind("}")
    if a >= 0 and b > a:
        s = s[a : b + 1]
    return json.loads(s)


def gather(db: Session, *, owner_id: str, company_id: str) -> dict:
    """Every signal the analysis reads — all scoped to this workspace. Returned
    on its own so the UI can show the evidence behind the reading."""
    company = _owned_company(db, company_id, owner_id)

    projects = (
        db.query(Project)
        .filter(Project.company_id == company_id, Project.owner_id == owner_id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    tasks = db.query(Task).filter(Task.company_id == company_id).all()
    task_counts: dict[str, int] = {}
    for t in tasks:
        task_counts[t.status] = task_counts.get(t.status, 0) + 1

    approvals = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.company_id == company_id,
            ApprovalRequest.owner_id == owner_id,
            ApprovalRequest.status == "pending",
        )
        .order_by(ApprovalRequest.created_at.desc())
        .all()
    )
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.company_id == company_id, AgentRun.owner_id == owner_id)
        .order_by(AgentRun.created_at.desc())
        .limit(10)
        .all()
    )
    memories = (
        db.query(MemoryEntry)
        .filter(MemoryEntry.company_id == company_id, MemoryEntry.owner_id == owner_id)
        .order_by(MemoryEntry.updated_at.desc())
        .limit(12)
        .all()
    )
    brain = brand_brain_service.get_summary(db, company_id)

    return {
        "workspace": {
            "name": company.name,
            "type": company.company_type,
            "industry": getattr(company, "industry", None),
            "parent": company.parent.name if getattr(company, "parent", None) else None,
        },
        "projects": {
            "total": len(projects),
            "active": sum(1 for p in projects if p.status == "active"),
            "names": [p.name for p in projects[:8]],
        },
        "tasks": {"total": len(tasks), "by_status": task_counts},
        "pending_approvals": [
            {
                "capability": a.capability_name,
                "action": a.action_type,
                # The proposed call's own arguments are the best description of
                # what's waiting; truncated so a big payload can't dominate.
                "details": (a.payload_json or "")[:280],
            }
            for a in approvals[:8]
        ],
        "recent_ai_work": [
            {"objective": r.objective[:160], "status": r.status} for r in runs
        ],
        "memory": {
            "count": len(memories),
            "recent": [{"title": m.title, "kind": m.kind} for m in memories[:8]],
        },
        "brand_brain": {
            "connected": bool(brain.get("exists")),
            "products": brain.get("product_count", 0),
            "collections": brain.get("collection_count", 0),
            "last_synced": brain.get("last_synced_at"),
        },
    }


async def analyze(db: Session, *, owner_id: str, company_id: str, refresh: bool = False) -> dict:
    """The AI reading of this workspace, plus the signals it was based on."""
    cached = _cache.get(company_id)
    if cached and not refresh and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    signals = gather(db, owner_id=owner_id, company_id=company_id)
    context = brand_brain_service.brand_prompt_context(db, company_id, product_limit=20)

    provider = get_ai_provider()
    try:
        result = await provider.complete(
            messages=[
                Message(role="system", content=_SYSTEM + context),
                Message(
                    role="user",
                    content=f"Workspace signals (JSON):\n{json.dumps(signals, indent=1, default=str)}",
                ),
            ],
            # A full workspace reading is a long answer, and reasoning models
            # spend part of this budget before the first output token — too
            # small a cap and the response is cut off (or has no text at all),
            # which costs the recommendations at the end of the JSON. Observed
            # peak is ~3.4k output tokens against the capped signal set.
            max_tokens=6000,
            temperature=0.3,
        )
        data = _extract_json(result.text)
    except Exception:
        # Never leave the page empty: fall back to the raw signals with an
        # honest headline rather than a fabricated reading.
        data = {
            "headline": "Analysis unavailable — showing raw workspace signals.",
            "state_of_play": "The AI reading couldn't be generated. The signals below are live.",
            "signals": [],
            "risks": [],
            "recommendations": [],
        }

    analysis = {
        "company_id": company_id,
        "workspace_name": signals["workspace"]["name"],
        "headline": str(data.get("headline", "")),
        "state_of_play": str(data.get("state_of_play", "")),
        "signals": data.get("signals") or [],
        "risks": data.get("risks") or [],
        "recommendations": data.get("recommendations") or [],
        "evidence": signals,
        "generated_at": time.time(),
    }
    _cache[company_id] = (time.time(), analysis)
    return analysis
