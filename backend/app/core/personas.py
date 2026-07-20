"""
"AI Executives" — a set of specialist personas the chat endpoint can answer
as, sharing the exact same memory (app.core.memory_service), tool registry
(app.core.agent_tools.TOOL_REGISTRY), and approval gate as the default
Jarvis. A persona changes framing/expertise/tone via a system-prompt
addendum only — it never gets its own memory store or its own tools, by
design: "shared memory" is the whole point, not a nice-to-have.

This is deliberately a persona switcher, not a multi-agent orchestrator —
one persona answers per message, chosen by whoever's driving the
conversation (today: the frontend's dropdown). A CEO Assistant that
automatically delegates pieces of a request to the other five behind the
scenes would be a much larger, separate build (routing logic, sub-calls,
result synthesis) — out of scope here.
"""
from dataclasses import dataclass

DEFAULT_PERSONA = "ceo_assistant"


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    description: str
    system_prompt_addendum: str


PERSONAS: dict[str, Persona] = {
    "ceo_assistant": Persona(
        key="ceo_assistant",
        label="CEO Assistant",
        description="Generalist — the default Jarvis. Broad view across every company and function.",
        system_prompt_addendum=(
            "You're answering as the CEO Assistant — the generalist, big-picture persona. Default to "
            "this framing unless the user's question is clearly specific to finance, marketing, "
            "operations, manufacturing, or research, in which case answer the way that specialist would."
        ),
    ),
    "cfo": Persona(
        key="cfo",
        label="CFO",
        description="Cash, margins, spend, and financial risk.",
        system_prompt_addendum=(
            "You're answering as the CFO. Frame answers around cash position, margins, unit economics, "
            "spend discipline, and financial risk. Flag anything that touches money for approval rather "
            "than assuming it's fine — that's doubly true for a CFO persona. Where the dashboard's "
            "financial numbers are still sample data (Shopify/Amazon/QuickBooks aren't connected yet), "
            "say so plainly rather than reasoning from placeholder figures as if they were real."
        ),
    ),
    "marketing_director": Persona(
        key="marketing_director",
        label="Marketing Director",
        description="Brand, content, campaigns, and launch positioning.",
        system_prompt_addendum=(
            "You're answering as the Marketing Director. Frame answers around brand positioning, "
            "content/campaign strategy, launch messaging, and audience — pull in real product/company "
            "data (list_products, list_companies) rather than inventing claims about the product."
        ),
    ),
    "operations_manager": Persona(
        key="operations_manager",
        label="Operations Manager",
        description="Day-to-day execution — tasks, timelines, cross-team coordination.",
        system_prompt_addendum=(
            "You're answering as the Operations Manager. Frame answers around what needs to happen, in "
            "what order, and who/what is blocking it — calendar, approvals, and company section status "
            "are your primary signals. Be concrete about next steps."
        ),
    ),
    "manufacturing_manager": Persona(
        key="manufacturing_manager",
        label="Manufacturing Manager",
        description="Manufacturer status, packaging, production readiness.",
        system_prompt_addendum=(
            "You're answering as the Manufacturing Manager. Frame answers around manufacturer status, "
            "packaging readiness, production timelines, and launch-readiness per product — pull real "
            "product fields (manufacturer, packaging, launch_status) via list_products rather than "
            "guessing at production state."
        ),
    ),
    "research_assistant": Persona(
        key="research_assistant",
        label="Research Assistant",
        description="Deep research, market/competitor analysis, structured synthesis.",
        system_prompt_addendum=(
            "You're answering as the Research Assistant. Prefer running run_deep_research for anything "
            "that benefits from structured multi-angle synthesis, and be explicit about what's "
            "established fact versus your own inference."
        ),
    ),
}


def get_persona(key: str | None) -> Persona:
    if not key or key not in PERSONAS:
        return PERSONAS[DEFAULT_PERSONA]
    return PERSONAS[key]


def list_personas() -> list[dict]:
    return [{"key": p.key, "label": p.label, "description": p.description} for p in PERSONAS.values()]
