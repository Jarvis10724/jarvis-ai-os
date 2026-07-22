"""
Direct chat with Jarvis's default (or a chosen) AI provider — the
conversational front door, separate from running a specific plugin directly.

When the active provider supports tool calling (Anthropic today), this is
also where Jarvis actually *does* things instead of just talking: the model
can call any tool in `app.core.agent_tools.TOOL_REGISTRY` — running a plugin
or reading/writing real business data — and the result is fed back to it so
it can keep going until it has a final answer.
"""
from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.auth.dependencies import CurrentUser
from app.core import brand_brain_service, memory_service
from app.core.agent_tools import TOOL_REGISTRY
from app.core.personas import get_persona, list_personas
from app.db.models.company import Company
from app.db.session import get_db
from app.exceptions import JarvisError
from app.logging_config import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)

JARVIS_SYSTEM_PROMPT_BASE = """You are Jarvis, an AI operating system and long-term \
Chief Operating Officer for a small business. Be direct, concrete, and practical.

You have tools that actually take action — run one of Jarvis's plugins (building \
websites, designing logos, creating products, deep research, writing code, project \
management, automation), read real business data (list a user's companies, list a \
company's products), or propose a change to it (propose_update_product, \
propose_update_company_section). Prefer calling a tool over describing what you would \
do. If a request needs a company_id or product_id you don't have, call list_companies \
or list_products first rather than guessing. Nothing that changes business data, \
sends anything, spends anything, or posts anything ever happens immediately — every \
such action only ever creates a pending approval request for the user to approve from \
the Approvals page first. After a tool call finishes, tell the user plainly what \
happened, and if something is now pending approval, say so explicitly rather than \
implying it already happened.

NEVER FABRICATE BUSINESS DATA. This system runs real companies, so an invented \
product, price, stock level, email, customer, or number is worse than no answer — it \
gets acted on. Product, pricing, inventory, and collection facts come from \
`store_catalog` / `store_product` (the live Shopify catalog) or the Brand Brain block \
below; email from the Gmail tools; nothing else is a source. If a tool returns nothing, \
the integration isn't connected, or you simply don't know, SAY THAT explicitly — \
"I don't have that" or "this workspace has no Gmail connected" — and offer how to get \
it. Never fill a gap with a plausible-sounding example, and never carry a product name \
from earlier conversation into a factual answer without confirming it exists in the \
catalog. To change the store, call `propose_store_change`, which prepares the change \
for approval — say plainly that nothing has changed yet.

You also have long-term memory — every conversation is already being recorded \
automatically, so you don't need to save small talk. But use the `remember` tool \
proactively whenever something durable comes up: a decision, a manufacturer/supplier \
quote, a meeting outcome, a contact, a fact about how the business runs. Use \
`search_memory` whenever the user references something from before ("what did that \
supplier quote us", "what did we decide about...") or when it would help to check \
before answering rather than guessing. Every memory has a scope (global, organization, \
company, project, or personal) — see the `remember` tool's description for the full \
classification rules, including when it's actually worth asking the user instead of \
just picking one.

If Gmail, Google Calendar, or Google Drive are connected (check Integrations if unsure \
— a tool call will fail with a clear "not connected" message otherwise), you can read \
mail (list_gmail_messages, summarize_gmail), draft replies (draft_gmail — never sends), \
read the calendar (list_calendar_events), and search/read Drive files (list_drive_files, \
read_drive_document) directly. Drive is one shared account isolated by folder per \
company (a folder named exactly like the active company) rather than a separate \
connection per company — list_drive_files defaults to the active company's folder; \
pass all_drive=true only when the user explicitly asks for their whole/entire Drive. \
Sending an email or creating a calendar event \
(propose_send_email, propose_create_calendar_event) only ever proposes the action for a \
human to approve — it's never sent/created immediately. Always tell the user plainly \
when something is pending approval rather than implying it already happened."""

# Hard ceiling on how many times we'll go back to the model after tool
# results before giving up and returning whatever text we have — prevents
# a runaway loop if the model keeps calling tools forever.
MAX_TOOL_ITERATIONS = 5

# Tools that read/write memory or a company-scoped integration get a default
# company_id filled in when the model doesn't supply one, so scoping "just
# works" for the common case without every tool call needing to reason
# about which company is active.
_COMPANY_SCOPED_TOOLS = {
    "remember",
    "search_memory",
    "list_gmail_messages",
    "summarize_gmail",
    "draft_gmail",
    "propose_send_email",
    "list_calendar_events",
    "propose_create_calendar_event",
    "list_drive_files",
    "read_drive_document",
    "propose_update_product",
    "propose_update_company_section",
    # Store tools: the active workspace decides WHICH store, so they must be
    # scoped like every other company-scoped tool — never left to the model.
    "store_catalog",
    "store_product",
    "store_collections",
    "sync_store",
    "propose_store_change",
}


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn]
    provider: str | None = None
    model: str | None = None
    # Whatever company is active in the UI when this message is sent — used
    # both to default memory-tool scoping and to record each exchange as a
    # conversation memory scoped the same way. None means "no active
    # company" (global/personal context).
    company_id: str | None = None
    # Which "AI Executive" is answering (see app.core.personas) — changes
    # framing/expertise/tone via a system-prompt addendum only. All
    # personas share the exact same memory and tools; None/unknown falls
    # back to the CEO Assistant.
    persona: str | None = None


class ToolCallLog(BaseModel):
    name: str
    input: dict
    output: str
    is_error: bool = False


class ChatResponse(BaseModel):
    text: str
    provider: str
    model: str
    tool_calls: list[ToolCallLog] = []


def _build_system_prompt(current_user, db: Session, company_id: str | None, persona_key: str | None) -> str:
    prompt = JARVIS_SYSTEM_PROMPT_BASE
    if not company_id:
        prompt += "\n\nNo company is currently active — treat this as global/personal context."
    else:
        company = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
        if company:
            prompt += (
                f"\n\nCurrently active company: {company.name!r} (id={company.id}). Default company_id for "
                "memory tools and business-data tools to this unless told otherwise."
            )
            # Brand Brain — the workspace's authoritative store catalog (read-only
            # mirror of Shopify), shared with Quick Actions + agents so every AI
            # surface answers from the same source of truth. Absent → "".
            prompt += brand_brain_service.brand_prompt_context(db, company.id)
    persona = get_persona(persona_key)
    return prompt + "\n\n" + persona.system_prompt_addendum


async def _execute_tool(
    name: str, tool_input: dict, current_user, db: Session, default_company_id: str | None
) -> tuple[str, bool]:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return f"Unknown tool '{name}'.", True
    if name in _COMPANY_SCOPED_TOOLS and tool_input.get("company_id") is None and default_company_id:
        tool_input = {**tool_input, "company_id": default_company_id}
    try:
        output = await tool.handler(current_user, db, **tool_input)
        return output, False
    except JarvisError as exc:
        return exc.message, True
    except Exception as exc:  # noqa: BLE001
        logger.error("tool_execution_failed", tool=name, error=str(exc))
        return f"Tool '{name}' failed: {exc}", True


async def _capture_conversation_memory(
    db: Session, owner_id: str, company_id: str | None, last_user_message: str, response_text: str
) -> None:
    """Best-effort conversation auto-capture, run as a background task so the
    embedding call (a real network round-trip to OpenAI when configured)
    never delays the chat response the user — often mid voice conversation —
    is waiting on."""
    try:
        await memory_service.record_memory(
            db,
            owner_id=owner_id,
            kind="conversation",
            title=last_user_message[:120],
            content=f"User: {last_user_message}\n\nJarvis: {response_text}",
            scope="company" if company_id else "organization",
            company_id=company_id,
            source="chat",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("conversation_memory_write_failed", error=str(exc))


@router.get("/personas")
async def personas(current_user: CurrentUser):
    return list_personas()


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    provider = get_ai_provider(payload.provider)
    system_prompt = _build_system_prompt(current_user, db, payload.company_id, payload.persona)
    messages = [Message(role="system", content=system_prompt)] + [
        Message(role=m.role, content=m.content) for m in payload.messages
    ]

    tool_defs = [tool.definition for tool in TOOL_REGISTRY.values()] if provider.supports_tools else None
    tool_log: list[ToolCallLog] = []

    result = await provider.complete(messages=messages, model=payload.model, tools=tool_defs)

    iterations = 0
    while result.tool_calls and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        # Replay the assistant's tool_use turn verbatim, then answer it with
        # a tool_result turn — this is the shape Anthropic's API requires
        # for a multi-turn tool-calling conversation.
        messages.append(Message(role="assistant", content=result.content_blocks))

        tool_result_blocks = []
        for call in result.tool_calls:
            output, is_error = await _execute_tool(call.name, call.input, current_user, db, payload.company_id)
            tool_log.append(ToolCallLog(name=call.name, input=call.input, output=output, is_error=is_error))
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": output,
                    "is_error": is_error,
                }
            )
        messages.append(Message(role="user", content=tool_result_blocks))

        result = await provider.complete(messages=messages, model=payload.model, tools=tool_defs)

    # Auto-capture every exchange into memory — this is what makes memory
    # Jarvis's actual conversation record instead of something that only
    # exists in the browser's local state. Runs after the response is sent
    # (see _capture_conversation_memory) so voice/chat latency isn't paying
    # for an embeddings API round-trip on every single turn.
    last_user_message = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    if last_user_message and result.text:
        # Passive auto-capture doesn't reason about content the way the
        # `remember` tool does, so it can't detect "this is actually
        # cross-company" — it just uses a simple, deterministic default:
        # tied to whatever company is active, else organization-level.
        background_tasks.add_task(
            _capture_conversation_memory,
            db,
            current_user.id,
            payload.company_id,
            last_user_message,
            result.text,
        )

    return ChatResponse(text=result.text, provider=result.provider, model=result.model, tool_calls=tool_log)
