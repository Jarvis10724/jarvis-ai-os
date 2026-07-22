"""
AI Command Center — routes any "Ask Jarvis" request to the right subsystem
automatically, so the user never picks a tool manually.

Routing is a small classification step over a DATA-DRIVEN destination catalog:
add a destination here and the Command Center can route to it — no rewiring.
Each destination declares how the frontend should act on it:

  * "studio"     — open an existing Quick Action workspace (/studio/<key>)
  * "chat"       — answer/act inline through the normal chat pipeline (which
                   already has the tools + the approval gate)
  * "navigate"   — take the user to the surface that answers the request
  * "work_queue" — multi-step: plan subtasks and run them in sequence

Nothing here executes anything itself: it only decides. Execution stays in the
existing subsystems, so every integration, approval gate, and workspace
isolation rule is preserved.
"""
import json

from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.core import brand_brain_service

# key -> how to act, where, the live status to show, and when to pick it.
DESTINATIONS: dict[str, dict] = {
    "web_builder": {"mode": "studio", "target": "web_builder", "label": "Website Builder", "status": "Building…",
                    "when": "build, redesign, or improve a website or landing page"},
    "logo_design": {"mode": "studio", "target": "logo_design", "label": "Logo Designer", "status": "Designing…",
                    "when": "create or design a logo, brand mark, or visual identity"},
    "product_creation": {"mode": "studio", "target": "product_creation", "label": "Product Creator", "status": "Designing…",
                         "when": "design, spec, or develop a new product"},
    "deep_research": {"mode": "studio", "target": "deep_research", "label": "Deep Research", "status": "Researching…",
                      "when": "research competitors, markets, suppliers, or any topic"},
    "code_writer": {"mode": "studio", "target": "code_writer", "label": "Code Writer", "status": "Building…",
                    "when": "write or debug code"},
    "automation": {"mode": "studio", "target": "automation", "label": "Automation", "status": "Planning…",
                   "when": "automate a repetitive task or workflow"},
    "task_manager": {"mode": "chat", "target": "/company/projects", "label": "Task Manager", "status": "Working…",
                     "when": "create, update, or complete a task or to-do"},
    "project_manager": {"mode": "chat", "target": "/company/projects", "label": "Project Manager", "status": "Working…",
                        "when": "start or manage a project"},
    "communications": {"mode": "chat", "target": "/approvals", "label": "Communications", "status": "Drafting…",
                       "when": "write, draft, or send an email or message"},
    "gmail": {"mode": "chat", "target": None, "label": "Gmail", "status": "Reading…",
              "when": "summarize, search, or triage email"},
    "calendar": {"mode": "chat", "target": None, "label": "Calendar", "status": "Scheduling…",
                 "when": "schedule, move, or check meetings and events"},
    "brand_brain": {"mode": "navigate", "target": "/company/brand-brain", "label": "Brand Brain", "status": "Analyzing…",
                    "when": "SEE the brand/product catalog itself — a full brand or workspace analysis, "
                            "or browsing products (not a question that can simply be answered)"},
    "executive_dashboard": {"mode": "navigate", "target": "/company/executive", "label": "Executive Dashboard",
                            "status": "Loading…",
                            "when": "SEE today's priorities, the workspace overview, status, or health"},
    "work_queue": {"mode": "work_queue", "target": "/company/work-queue", "label": "Work Queue", "status": "Planning…",
                   "when": "a multi-step request that needs several tools run in sequence"},
    "chat": {"mode": "chat", "target": None, "label": "Chat", "status": "Thinking…",
             "when": "a question, explanation, or anything that doesn't fit another destination"},
}

DEFAULT = "chat"


def _catalog_text() -> str:
    return "\n".join(f"- {k}: {v['when']}" for k, v in DESTINATIONS.items())


_SYSTEM = (
    "You are Jarvis's Command Center router. Decide which ONE destination should handle the user's "
    "request. Destinations:\n{catalog}\n\n"
    "Rules:\n"
    "- A QUESTION that can be answered in words goes to 'chat' — chat is already grounded in this "
    "workspace's Brand Brain, memory, and tools. Only route to a 'SEE'-style destination when the user "
    "wants to look at that surface.\n"
    "- Pick 'work_queue' only when the request clearly needs SEVERAL different tools run in sequence.\n"
    "- Ask a clarifying question ONLY if you genuinely cannot route without it — prefer routing with a "
    "sensible assumption.\n"
    'Respond with ONLY JSON: {{"destination":"<key>","explanation":"<one short sentence, first person, '
    'saying what you\'re doing>","clarifying_question":null}}'
)


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


def decision_for(key: str, *, explanation: str = "", clarifying_question: str | None = None) -> dict:
    meta = DESTINATIONS.get(key) or DESTINATIONS[DEFAULT]
    resolved = key if key in DESTINATIONS else DEFAULT
    return {
        "destination": resolved,
        "label": meta["label"],
        "mode": meta["mode"],
        "target": meta["target"],
        "status": meta["status"],
        "explanation": explanation or f"Routing this to {meta['label']}.",
        "clarifying_question": clarifying_question,
    }


async def route(
    db: Session, *, owner_id: str, company_id: str | None, request: str, history: list[dict] | None = None
) -> dict:
    """Classify a request to exactly one destination. Never raises for routing
    failures — falls back to chat so the Command Center always responds."""
    ctx = brand_brain_service.brand_prompt_context(db, company_id, product_limit=20) if company_id else ""
    convo = ""
    for m in (history or [])[-6:]:
        role = m.get("role", "user")
        convo += f"\n{role}: {str(m.get('content', ''))[:400]}"
    provider = get_ai_provider()
    try:
        result = await provider.complete(
            messages=[
                Message(role="system", content=_SYSTEM.format(catalog=_catalog_text()) + ctx),
                Message(
                    role="user",
                    content=(f"Recent conversation:{convo}\n\n" if convo else "") + f"Request: {request}",
                ),
            ],
            max_tokens=300,
            temperature=0.1,
        )
        data = _extract_json(result.text)
        return decision_for(
            str(data.get("destination", DEFAULT)),
            explanation=str(data.get("explanation", "")),
            clarifying_question=data.get("clarifying_question") or None,
        )
    except Exception:
        return decision_for(DEFAULT)
