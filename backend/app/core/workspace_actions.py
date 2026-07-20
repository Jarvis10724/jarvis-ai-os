"""
Registry for the six Quick-Action workspaces. Each entry defines how that
workspace behaves: its human label, the studio system prompt, the ordered
*stages* that make it a real application (not a chat box), the structured
`state` keys the model maintains, and the noun used when it auto-creates
Tasks/Memory. Adding a workspace is one entry here — nothing else in the
workspace machinery is action-specific.

These `key`s intentionally match the builtin plugin names so a workspace and
its corresponding plugin stay aligned.

## The structured-state contract

Every workspace turn streams normal prose for the chat column, and — when it
has structured work to record — ends with a single fenced block:

    ```jarvis-state
    { "sitemap": [...], "design": { ... } }
    ```

`app.api.v1.endpoints.workspaces` extracts that block, deep-merges it into the
session's `state_json`, and strips it from the visible message. The current
state is fed back into the system prompt each turn, so the model always builds
on what's already there. This keeps every panel (sitemap, concepts, sources,
launch checklist, ...) filled with real, AI-generated content — never mock
data.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkspaceStage:
    """One tab/section of a workspace application (e.g. "Sitemap")."""
    key: str
    label: str
    #: The `state_json` key this stage renders from (may be empty for a stage
    #: that is purely conversational, like the opening requirements chat).
    state_key: str = ""
    hint: str = ""


@dataclass(frozen=True)
class WorkspaceAction:
    key: str
    label: str
    #: The studio persona/system prompt. Kept concrete and output-shaped so
    #: streamed responses read like deliverables, not chat.
    system_prompt: str
    #: Noun for auto-created memory entries (e.g. "website plan").
    memory_noun: str
    #: MemoryEntry.kind for context stored from this workspace.
    memory_kind: str
    #: Ordered stages the UI renders as the workspace's structured panels.
    stages: list[WorkspaceStage] = field(default_factory=list)
    #: Documentation of each structured-state key, injected into the system
    #: prompt so the model knows exactly what shape to emit in ``jarvis-state``.
    state_schema: dict[str, str] = field(default_factory=dict)
    #: True if this workspace can generate real images (Logo Studio) via the
    #: image-generation seam. Never fabricates images when unconfigured.
    supports_images: bool = False

    def public(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "supports_images": self.supports_images,
            "stages": [
                {"key": s.key, "label": s.label, "state_key": s.state_key, "hint": s.hint}
                for s in self.stages
            ],
            "state_keys": list(self.state_schema),
        }


def _state_prompt(schema: dict[str, str]) -> str:
    """Render the structured-state contract for a given action's schema."""
    lines = "\n".join(f"  - {key}: {desc}" for key, desc in schema.items())
    return (
        "\n\n## Structured workspace state\n"
        "This request runs inside a persistent studio with structured panels. "
        "After your prose answer, when (and only when) you have produced or "
        "changed structured work, append EXACTLY ONE fenced block labelled "
        "`jarvis-state` containing a JSON object. Only include the keys you are "
        "adding or changing — it is deep-merged into the existing state, so you "
        "never need to repeat unchanged data. Do not wrap it in commentary. "
        "The available keys are:\n" + lines + "\n\n"
        "Populate every key your answer actually covers — the block is what fills "
        "the studio panels, so a substantive deliverable should carry real "
        "structured data, not an empty object. If you genuinely have no structured "
        "update this turn, omit the block entirely rather than emitting an empty "
        "one. Keep the prose readable on its own; the JSON is for the panels, not a "
        "substitute for explaining your work. Never invent data you don't have — "
        "leave a key out instead of filling it with placeholders."
    )


WORKSPACE_ACTIONS: dict[str, WorkspaceAction] = {
    "web_builder": WorkspaceAction(
        key="web_builder",
        label="Website Studio",
        system_prompt=(
            "You are Jarvis's Website Studio — a senior web strategist, copywriter, and "
            "React engineer. You take a business from a thin brief to a buildable React site "
            "through distinct stages: clarify requirements, propose a sitemap, define page "
            "layouts, write real page copy, set a design direction, then generate real React "
            "components. Use clear markdown headings and bullet lists in chat. Be specific to "
            "the business; never return placeholder lorem ipsum. If the brief is thin, make "
            "reasonable, clearly-stated assumptions and proceed rather than asking a wall of "
            "questions. Tell the user they can click 'Build Website' to run the full "
            "sitemap → layouts → copy → React components → images → preview pipeline."
        ),
        memory_noun="website plan",
        memory_kind="decision",
        stages=[
            WorkspaceStage("requirements", "Requirements", "requirements", "Goals, audience, pages, must-haves"),
            WorkspaceStage("analysis", "Analysis", "source_analysis", "Existing site analysis (Improve mode)"),
            WorkspaceStage("sitemap", "Sitemap", "sitemap", "Pages and their sections"),
            WorkspaceStage("layouts", "Layouts", "layouts", "Section structure per page"),
            WorkspaceStage("copy", "Copy", "copy", "Draft copy per page"),
            WorkspaceStage("design", "Design", "design", "Palette, type, style direction"),
            WorkspaceStage("components", "Components", "components", "Generated React components"),
            WorkspaceStage("images", "Images", "images", "Generated images / placeholders"),
            WorkspaceStage("preview", "Preview", "preview_html", "Rendered site preview"),
        ],
        state_schema={
            "requirements": "string (markdown) — the agreed brief: goals, audience, tone, required pages.",
            "source_analysis": "object {brand, description, palette, fonts, nav, pages} — crawl of the existing site (Improve mode).",
            "sitemap": "array of {path, title, purpose, sections:[string]} — one entry per page.",
            "layouts": "object keyed by page path -> {sections:[{name, type, description}]} — the structural layout per page.",
            "copy": "object keyed by page path -> {heading, sections:[{title, body}]} of real draft copy.",
            "design": "object {palette:[{name,hex}], typography:{heading,body}, style_notes}.",
            "components": "object {files:[{path, language, content, description}]} — real React component files.",
            "images": "array of {id, page, role, alt, prompt, data_url, status} — generated images or labeled placeholders.",
            "code": "object {files:[{path, language, content}]} — legacy starter HTML (superseded by components).",
            "preview_html": "string — a single self-contained HTML document that renders the site.",
        },
    ),
    "logo_design": WorkspaceAction(
        key="logo_design",
        label="Logo Studio",
        system_prompt=(
            "You are Jarvis's Logo Studio — a brand identity director. You move from brand "
            "discovery to a creative brief, then to multiple distinct concept directions, "
            "then to real generated concept images, then revisions, then export-ready records. "
            "For each concept give the idea, imagery, color palette (hex), typography, and "
            "rationale — precise enough that a designer or an image model could execute it. "
            "Each concept must include a vivid `image_prompt` suitable for an image generator. "
            "Use markdown headings."
        ),
        memory_noun="logo direction",
        memory_kind="decision",
        supports_images=True,
        stages=[
            WorkspaceStage("discovery", "Discovery", "discovery", "Brand personality, audience"),
            WorkspaceStage("brief", "Creative Brief", "brief", "The distilled brief"),
            WorkspaceStage("concepts", "Concepts", "concepts", "Multiple directions"),
            WorkspaceStage("images", "Images", "images", "Generated concept marks"),
            WorkspaceStage("revisions", "Revisions", "revisions", "Revision history"),
            WorkspaceStage("exports", "Exports", "exports", "Export-ready records"),
        ],
        state_schema={
            "discovery": "string (markdown) — what we learned about the brand.",
            "brief": "object {brand_name, audience, tone, values:[string], keywords:[string]}.",
            "concepts": "array of {id, name, idea, imagery, palette:[{name,hex}], typography, rationale, image_prompt}.",
            "revisions": "array of {ts, concept_id, note} — appended as directions are refined.",
            "exports": "array of {concept_id, name, formats:[string]} — records of what's export-ready.",
        },
    ),
    "product_creation": WorkspaceAction(
        key="product_creation",
        label="Product Studio",
        system_prompt=(
            "You are Jarvis's Product Studio — a product and go-to-market lead. You take a "
            "product from concept through customer/market positioning, formula/specification "
            "notes, packaging, pricing & margin planning, manufacturer requirements, and a "
            "launch checklist. Be numbers-specific where you can (costs, prices, margins) and "
            "flag assumptions. Use markdown headings."
        ),
        memory_noun="product spec",
        memory_kind="product",
        stages=[
            WorkspaceStage("concept", "Concept", "concept", "What the product is"),
            WorkspaceStage("positioning", "Positioning", "positioning", "Customer & market"),
            WorkspaceStage("spec", "Spec", "spec", "Formula / specification"),
            WorkspaceStage("packaging", "Packaging", "packaging", "Packaging direction"),
            WorkspaceStage("pricing", "Pricing", "pricing", "Pricing & margin"),
            WorkspaceStage("manufacturing", "Manufacturing", "manufacturing", "Manufacturer requirements"),
            WorkspaceStage("launch", "Launch", "launch_checklist", "Launch checklist"),
        ],
        state_schema={
            "concept": "string (markdown) — the product concept and value proposition.",
            "positioning": "object {target_customer, market, differentiation, competitors:[string]}.",
            "spec": "object {summary, specifications:[{name, value}]} — formula/spec notes.",
            "packaging": "string (markdown) — packaging format, materials, label direction.",
            "pricing": "object {unit_cost, price, margin_pct, tiers:[{name, price, note}]}.",
            "manufacturing": "object {requirements:[string], moq, lead_time, notes}.",
            "launch_checklist": "array of {item, done:boolean, owner} — concrete launch steps.",
        },
    ),
    "deep_research": WorkspaceAction(
        key="deep_research",
        label="Research Desk",
        system_prompt=(
            "You are Jarvis's Research Desk — a rigorous analyst. You work a question through "
            "a research plan, a collected source list, running progress, cited findings, "
            "working notes, and a final structured report. Be explicit about certainty vs. "
            "speculation. Use markdown headings. IMPORTANT: unless a web-search tool result is "
            "provided to you, you are reasoning from your own knowledge — mark every source in "
            "the source library with \"derived\": true and never fabricate a URL or present a "
            "guessed citation as a real retrieved page."
        ),
        memory_noun="research briefing",
        memory_kind="fact",
        stages=[
            WorkspaceStage("plan", "Plan", "plan", "Research plan"),
            WorkspaceStage("sources", "Sources", "sources", "Source library"),
            WorkspaceStage("progress", "Progress", "progress", "Live progress"),
            WorkspaceStage("citations", "Citations", "citations", "Cited findings"),
            WorkspaceStage("notes", "Notes", "notes", "Working notes"),
            WorkspaceStage("report", "Report", "report", "Final report"),
        ],
        state_schema={
            "plan": "array of {step, status} — the research plan; status in todo|doing|done.",
            "sources": "array of {id, title, kind, url, note, derived:boolean} — the source library.",
            "progress": "array of {ts, note} — appended log of what was investigated.",
            "citations": "array of {claim, source_id} — findings tied to a source in the library.",
            "notes": "string (markdown) — running analyst notes.",
            "report": "string (markdown) — the final structured briefing.",
        },
    ),
    "code_writer": WorkspaceAction(
        key="code_writer",
        label="Code Studio",
        system_prompt=(
            "You are Jarvis's Code Studio — a senior engineer. You take a spec through "
            "requirements, a proposed file tree, generated code files, a test plan/status, "
            "and versioned artifacts. Produce working, well-structured code with a brief "
            "explanation of the approach, then the code in fenced blocks with the language "
            "annotated. Prefer complete, runnable examples over fragments, and keep the "
            "file tree and generated files in sync."
        ),
        memory_noun="code deliverable",
        memory_kind="other",
        stages=[
            WorkspaceStage("requirements", "Requirements", "requirements", "What to build"),
            WorkspaceStage("tree", "File Tree", "file_tree", "Project structure"),
            WorkspaceStage("files", "Files", "files", "Generated code"),
            WorkspaceStage("tests", "Tests", "test_status", "Test status"),
        ],
        state_schema={
            "requirements": "string (markdown) — the agreed spec and constraints.",
            "file_tree": "array of strings — repo-relative paths, in tree order.",
            "files": "array of {path, language, content} — the actual generated source.",
            "test_status": "object {framework, status, summary, cases:[{name, status}]}. status in passing|failing|unknown.",
        },
    ),
    "automation": WorkspaceAction(
        key="automation",
        label="Automation Studio",
        system_prompt=(
            "You are Jarvis's Automation Studio — an operations/workflow designer. You define "
            "an automation's goal, its trigger, ordered actions, conditions, which steps need "
            "human approval, a safe test-mode dry run, an activity history, and an enabled/"
            "disabled state. Any action that writes to the outside world must be marked "
            "requires_approval and, in this build, is intended to route through Jarvis's "
            "Approval Center rather than firing directly. Use markdown headings and numbered "
            "steps."
        ),
        memory_noun="automation design",
        memory_kind="other",
        stages=[
            WorkspaceStage("goal", "Goal", "goal", "What it should accomplish"),
            WorkspaceStage("trigger", "Trigger", "trigger", "What starts it"),
            WorkspaceStage("actions", "Actions", "actions", "Ordered steps"),
            WorkspaceStage("conditions", "Conditions", "conditions", "Guards & rules"),
            WorkspaceStage("test", "Test Mode", "test_runs", "Dry-run history"),
            WorkspaceStage("activity", "Activity", "activity", "Run history"),
        ],
        state_schema={
            "goal": "string (markdown) — the outcome this automation produces.",
            "trigger": "object {type, detail} — type in schedule|event|manual|webhook.",
            "actions": "array of {order, action, tool, inputs, requires_approval:boolean}.",
            "conditions": "array of {when, then} — guard rules.",
            "requires_approval": "boolean — whether a run needs human approval before side effects.",
            "enabled": "boolean — whether the automation is active.",
            "test_runs": "array of {ts, input, outcome} — appended dry-run results (no side effects).",
            "activity": "array of {ts, event} — appended real run/log history.",
        },
    ),
}


def get_action(key: str) -> WorkspaceAction | None:
    return WORKSPACE_ACTIONS.get(key)


def build_system_prompt(action: WorkspaceAction, *, company_line: str, state: dict) -> str:
    """The full system prompt for a turn: persona + company context + the
    structured-state contract + the current state so the model builds on what
    already exists instead of starting over each turn."""
    import json

    parts = [action.system_prompt + company_line, _state_prompt(action.state_schema)]
    if state:
        parts.append(
            "\n\n## Current workspace state\n"
            "Here is the structured work already saved. Build on it; only emit the keys you "
            "change.\n```json\n" + json.dumps(state, indent=2)[:6000] + "\n```"
        )
    return "".join(parts)
