"""
Jarvis's AI Agent framework.

An Agent is an autonomous, role-scoped operator (CEO, Marketing, Finance,
Research, Operations) that pursues an objective inside ONE workspace using a
declared subset of the shared tool registry (app.core.agent_tools). It:

  * has persistent memory — every run and its full decision log is stored in
    `agent_runs`, and it reads/writes AI Memory via the memory tools;
  * accesses only the active workspace — every company-scoped tool call is
    forced to the run's company_id; it is never handed another workspace's id;
  * creates Tasks/Projects via the create_task/create_project tools;
  * requests approval before important (external-effecting) actions — those
    only ever go through the propose_* tools, which create a pending
    ApprovalRequest instead of doing anything (capability_service);
  * logs every decision and streams its reasoning + progress as it runs;
  * runs in the foreground (streamed) or the background (persisted, pollable).

Future integrations (Shopify, Drive, Amazon, QuickBooks, Gmail, Calendar,
Printify) plug in by registering a tool in agent_tools.TOOL_REGISTRY and adding
its name to the relevant agent's `tools` list below — nothing in this runner is
integration-specific. Read actions can be added directly; anything that writes
to an external service should be a propose_* tool so the approval gate applies.
"""
import json
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider
from app.core import brand_brain_service
from app.core import memory_service
from app.core.agent_tools import TOOL_REGISTRY
from app.db.models.agent_run import AgentRun
from app.db.models.company import Company
from app.db.session import SessionLocal
from app.exceptions import JarvisError
from app.logging_config import get_logger

logger = get_logger(__name__)

MAX_ITERATIONS = 8

# Tools whose company_id must be pinned to the run's workspace (isolation) —
# the agent never gets to choose which company these touch.
_COMPANY_SCOPED_TOOLS = {
    "create_task",
    "list_products",
    "remember",
    "search_memory",
    "propose_update_product",
    "propose_update_company_section",
    "list_gmail_messages",
    "summarize_gmail",
    "draft_gmail",
    "propose_send_email",
    "list_calendar_events",
    "propose_create_calendar_event",
    "list_drive_files",
    "read_drive_document",
}

# Read/memory/creation tools every agent gets.
_BASE_TOOLS = ["search_memory", "remember", "list_products", "create_project", "create_task"]


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    label: str
    role: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)

    def tool_names(self) -> list[str]:
        # De-dup while preserving order; skip any tool not actually registered.
        seen: list[str] = []
        for name in [*_BASE_TOOLS, *self.tools]:
            if name in TOOL_REGISTRY and name not in seen:
                seen.append(name)
        return seen


_APPROVAL_RULE = (
    "You operate inside a single workspace and must never reference or act on any other. "
    "Anything that would affect the outside world (sending an email, changing a product, "
    "editing a company section, creating a calendar event) is IMPORTANT and must go through "
    "its propose_* tool, which only creates a pending approval for the human to approve — it "
    "never executes immediately. Internal planning — creating Projects and Tasks, saving to "
    "memory — you may do directly. Search memory before assuming; save durable decisions to "
    "memory. When done, give a concise summary of what you did, what you created, and what is "
    "now pending approval."
)

AGENTS: dict[str, AgentDefinition] = {
    "ceo": AgentDefinition(
        key="ceo",
        label="CEO Agent",
        role="Chief Executive — strategy, prioritization, delegation",
        system_prompt=(
            "You are the CEO Agent for a small business — the strategic operator. Given an "
            "objective, form a plan, prioritize, and set the work up: break it into Projects and "
            "Tasks, capture decisions to memory, and delegate concretely. Think in outcomes and "
            "trade-offs. " + _APPROVAL_RULE
        ),
        tools=[
            "list_companies",
            "run_project_management",
            "run_deep_research",
            "propose_update_company_section",
        ],
    ),
    "marketing": AgentDefinition(
        key="marketing",
        label="Marketing Agent",
        role="Growth, brand, content, and launches",
        system_prompt=(
            "You are the Marketing Agent. Given an objective, produce concrete marketing work: "
            "positioning, campaigns, content plans, brand/website/product assets (via the studio "
            "tools), and a tracked task list to execute it. " + _APPROVAL_RULE
        ),
        tools=[
            "run_web_builder",
            "run_logo_design",
            "run_product_creation",
            "run_deep_research",
            "run_automation",
        ],
    ),
    "finance": AgentDefinition(
        key="finance",
        label="Finance Agent",
        role="Financial analysis, pricing, unit economics",
        system_prompt=(
            "You are the Finance Agent. Given an objective, analyze the numbers you can see "
            "(products: cost, price, margin, inventory), model pricing/unit-economics, flag risks, "
            "and turn recommendations into tracked tasks. Propose product changes for approval "
            "rather than applying them. Live accounting (QuickBooks) is not connected yet — say so "
            "if a figure would require it. " + _APPROVAL_RULE
        ),
        tools=["propose_update_product"],
    ),
    "research": AgentDefinition(
        key="research",
        label="Research Agent",
        role="Market/competitive/analytical research",
        system_prompt=(
            "You are the Research Agent. Given a question, run structured research, synthesize "
            "findings with explicit certainty levels, save key facts to memory, and create "
            "follow-up tasks for anything actionable. You reason from knowledge (no live web "
            "access yet) — flag claims that would need current data. " + _APPROVAL_RULE
        ),
        tools=["run_deep_research"],
    ),
    "operations": AgentDefinition(
        key="operations",
        label="Operations Agent",
        role="Process, workflows, execution, logistics",
        system_prompt=(
            "You are the Operations Agent. Given an objective, design the process to run it: "
            "workflows (via automation), SOPs, and a sequenced, assigned task list. Keep the "
            "business running smoothly. Propose company-section changes for approval. " + _APPROVAL_RULE
        ),
        tools=["run_automation", "run_project_management", "propose_update_company_section"],
    ),
}


def get_agent(key: str) -> AgentDefinition | None:
    return AGENTS.get(key)


# Event emitted during a run — streamed to the client and appended to the log.
AgentEvent = dict
EventSink = Callable[[AgentEvent], Awaitable[None]] | None


class _NullUser:
    """Minimal stand-in so tool handlers (which expect `current_user.id`) work
    when the runner drives them from a background task."""

    def __init__(self, user_id: str):
        self.id = user_id


async def _emit(sink: EventSink, log: list, event: AgentEvent) -> None:
    log.append(event)
    if sink is not None:
        await sink(event)


class AgentRunner:
    """Executes an agent's tool-using reasoning loop, scoped to one workspace."""

    def __init__(self, db: Session):
        self.db = db

    def create_run(self, *, owner_id: str, company_id: str | None, agent_key: str, objective: str) -> AgentRun:
        run = AgentRun(
            owner_id=owner_id,
            company_id=company_id,
            agent_key=agent_key,
            objective=objective,
            status="queued",
            reasoning_log_json="[]",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    async def execute(self, run_id: str, *, sink: EventSink = None) -> None:
        """Run the agent to completion, persisting status + the full decision
        log, streaming each step through `sink` if provided."""
        run = self.db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run is None:
            return
        agent = get_agent(run.agent_key)
        if agent is None:
            run.status = "failed"
            run.result = f"Unknown agent '{run.agent_key}'."
            self.db.commit()
            return

        user = _NullUser(run.owner_id)
        company_id = run.company_id
        log: list = json.loads(run.reasoning_log_json or "[]")

        run.status = "running"
        self.db.commit()
        await _emit(sink, log, {"type": "status", "status": "running", "agent": agent.label})

        # Workspace context in the system prompt (the agent never enumerates
        # other companies unless it's the CEO agent with list_companies).
        company_line = ""
        if company_id:
            company = self.db.query(Company).filter(Company.id == company_id).first()
            if company:
                company_line = (
                    f"\n\nActive workspace: company {company.name!r} (id={company.id}). "
                    "Use this company_id for every company-scoped tool."
                )
                # Ground the agent in the workspace's real store (Brand Brain).
                company_line += brand_brain_service.brand_prompt_context(self.db, company_id)

        tool_defs = [TOOL_REGISTRY[n].definition for n in agent.tool_names()]
        provider = get_ai_provider()
        messages = [
            Message(role="system", content=agent.system_prompt + company_line),
            Message(role="user", content=run.objective),
        ]

        final_text = ""
        try:
            for _ in range(MAX_ITERATIONS):
                result = await provider.complete(messages=messages, tools=tool_defs)
                if result.text:
                    final_text = result.text
                    await _emit(sink, log, {"type": "reasoning", "text": result.text})
                if not result.tool_calls:
                    break

                messages.append(Message(role="assistant", content=result.content_blocks))
                tool_result_blocks = []
                for call in result.tool_calls:
                    tool_input = dict(call.input)
                    if call.name in _COMPANY_SCOPED_TOOLS and not tool_input.get("company_id") and company_id:
                        tool_input["company_id"] = company_id
                    await _emit(sink, log, {"type": "tool_call", "tool": call.name, "input": tool_input})
                    output, is_error = await self._run_tool(call.name, tool_input, user)
                    await _emit(
                        sink, log, {"type": "tool_result", "tool": call.name, "output": output, "is_error": is_error}
                    )
                    tool_result_blocks.append(
                        {"type": "tool_result", "tool_use_id": call.id, "content": output, "is_error": is_error}
                    )
                messages.append(Message(role="user", content=tool_result_blocks))

            run.status = "completed"
            run.result = final_text
        except Exception as exc:  # noqa: BLE001
            logger.error("agent_run_failed", run_id=run_id, error=str(exc))
            run.status = "failed"
            run.result = "The agent hit an error — check the AI provider key in .env."
            await _emit(sink, log, {"type": "error", "message": run.result})

        run.reasoning_log_json = json.dumps(log)
        self.db.commit()

        # Persist the outcome into AI Memory so the next run has continuity.
        if run.status == "completed" and final_text.strip():
            try:
                await memory_service.record_memory(
                    self.db,
                    owner_id=run.owner_id,
                    kind="decision",
                    title=f"{agent.label}: {run.objective[:100]}",
                    content=f"Objective: {run.objective}\n\nOutcome:\n{final_text}",
                    scope="company" if company_id else "organization",
                    company_id=company_id,
                    project_id=run.project_id,
                    source="agent",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("agent_memory_write_failed", error=str(exc))

        await _emit(sink, log, {"type": "done", "run_id": run_id, "status": run.status, "result": run.result})
        # Re-persist so the final "done" event is in the stored log too.
        run.reasoning_log_json = json.dumps(log)
        self.db.commit()

    async def _run_tool(self, name: str, tool_input: dict, user) -> tuple[str, bool]:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            return f"Unknown tool '{name}'.", True
        try:
            output = await tool.handler(user, self.db, **tool_input)
            return output, False
        except JarvisError as exc:
            return exc.message, True
        except Exception as exc:  # noqa: BLE001
            logger.error("agent_tool_failed", tool=name, error=str(exc))
            return f"Tool '{name}' failed: {exc}", True


async def run_agent_background(run_id: str) -> None:
    """Entry point for background execution — opens its own DB session so it
    survives past the request that scheduled it."""
    db = SessionLocal()
    try:
        await AgentRunner(db).execute(run_id)
    finally:
        db.close()
