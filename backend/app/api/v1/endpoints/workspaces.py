"""
Quick-Action workspaces — persistent, streaming "studio" applications
(Website, Logo, Product, Research, Code, Automation). Each session keeps its
own conversation history AND a structured, action-specific state (sitemap,
concepts, sources, launch checklist, ...), auto-attaches to a real Project,
auto-creates Tasks for its work, and records context into AI Memory — all
company-scoped and restorable after a restart (everything lives in
workspace_sessions).

The message endpoint streams the AI response live via Server-Sent Events and,
on completion, merges the model's ``jarvis-state`` block into the workspace's
structured state so the studio panels stay filled with real generated work.
"""
import json
from datetime import datetime, timezone
import time
from urllib.parse import urlparse

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai_providers.base import Message
from app.ai_providers.factory import get_ai_provider, get_image_provider
from app.auth.dependencies import CurrentUser
from app.core import brand_brain_service
from app.core import memory_service
from app.core import project_service
from app.core import search_service
from app.core import website_analyzer
from app.core import website_builder
from app.core.workspace_actions import WORKSPACE_ACTIONS, build_system_prompt, get_action
from app.core import workspace_state as ws
from app.db.models.client import Client
from app.db.models.company import Company
from app.db.models.project import Project
from app.db.models.task import Task
from app.db.models.workspace_session import WorkspaceSession
from app.db.session import SessionLocal, get_db
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
logger = get_logger(__name__)

MAX_HISTORY_TURNS = 24


# --- Schemas --------------------------------------------------------------


class WorkspaceCreate(BaseModel):
    action: str
    company_id: str | None = None
    title: str | None = None
    #: The Project this Quick Action should attach to. When omitted, the
    #: session attaches to the business's default project (get-or-create), so
    #: all Quick Actions in a business roll into the same shared Project instead
    #: of each minting its own.
    project_id: str | None = None
    #: Website Builder mode: "new" (default) | "improve" | "client".
    mode: str | None = None
    #: For "improve" mode — the existing site to crawl/analyze and improve.
    source_url: str | None = None
    #: For "client" mode — the Client this build belongs to.
    client_id: str | None = None


class WorkspaceUpdate(BaseModel):
    title: str | None = None
    status: str | None = None


class TurnsIn(BaseModel):
    """Turns to append to a conversation. Each carries its own timestamp so an
    imported history keeps its original ordering rather than collapsing to
    'whenever it was uploaded'."""

    turns: list[dict]


class MessageIn(BaseModel):
    content: str
    #: Optional stage the user is working in (e.g. "sitemap") — steers the
    #: turn toward that panel. Purely a hint; the model still owns the output.
    stage: str | None = None


class ArtifactIn(BaseModel):
    title: str
    content: str
    kind: str = "document"
    stage: str = ""


class AttachProjectIn(BaseModel):
    project_id: str


class TaskIn(BaseModel):
    title: str
    status: str = "backlog"


class ImageIn(BaseModel):
    prompt: str
    concept_id: str | None = None
    name: str | None = None
    size: str = "1024x1024"


# --- Helpers --------------------------------------------------------------


def _owned_session(db: Session, session_id: str, owner_id: str) -> WorkspaceSession:
    s = (
        db.query(WorkspaceSession)
        .filter(WorkspaceSession.id == session_id, WorkspaceSession.owner_id == owner_id)
        .first()
    )
    if not s:
        raise NotFoundError(f"Workspace '{session_id}' not found")
    return s


def _assert_company(db: Session, company_id: str | None, owner_id: str) -> None:
    if company_id is None:
        return
    exists = db.query(Company.id).filter(Company.id == company_id, Company.owner_id == owner_id).first()
    if not exists:
        raise NotFoundError(f"Company '{company_id}' not found")


def _serialize(db: Session, s: WorkspaceSession, *, full: bool) -> dict:
    action = get_action(s.action)
    messages = ws.load_json(s.messages_json, [])
    artifacts = ws.load_json(s.artifacts_json, [])
    state_obj = ws.load_json(s.state_json, {})
    data = {
        "id": s.id,
        "action": s.action,
        "action_label": action.label if action else s.action,
        "company_id": s.company_id,
        "client_id": s.client_id,
        "mode": state_obj.get("mode", "new") if s.action == "web_builder" else None,
        "source_url": state_obj.get("source_url") if s.action == "web_builder" else None,
        "title": s.title,
        "project_id": s.project_id,
        "status": s.status,
        "message_count": len(messages),
        "artifact_count": len(artifacts),
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    if full:
        data["messages"] = messages
        data["artifacts"] = artifacts
        data["state"] = ws.load_json(s.state_json, {})
        data["config"] = action.public() if action else None
        tasks = (
            db.query(Task).filter(Task.project_id == s.project_id).order_by(Task.created_at.asc()).all()
            if s.project_id
            else []
        )
        data["tasks"] = [
            {"id": t.id, "title": t.title, "status": t.status, "due_date": t.due_date} for t in tasks
        ]
    return data


def _session_event(db: Session, s: WorkspaceSession, *, kind: str, title: str, detail: str | None = None, ref_id: str | None = None) -> None:
    """Record a Timeline event on a session's project (best-effort — a session
    always has a project_id now, but stay defensive for legacy rows)."""
    if not s.project_id:
        return
    project = db.query(Project).filter(Project.id == s.project_id).first()
    if not project:
        return
    project_service.record_project_event(
        db, project=project, owner_id=s.owner_id, kind=kind, title=title,
        source=s.action, detail=detail, ref_id=ref_id,
    )


def _create_task(db: Session, *, owner_id, company_id, project_id, title, status) -> Task:
    task = Task(
        owner_id=owner_id,
        company_id=company_id,
        project_id=project_id,
        title=title[:255],
        status=status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# --- CRUD -----------------------------------------------------------------


@router.get("/actions")
def list_actions(current_user: CurrentUser):
    """The catalog of Quick Action studios (labels + their structured stages).

    "chat" is excluded deliberately. It is a workspace session so that the Ask
    Jarvis thread has a shared, backend-owned home — but it is a conversation,
    not a studio, and listing it here would add a Quick Action tile to the UI
    that nobody asked for.
    """
    return [a.public() for a in WORKSPACE_ACTIONS.values() if a.key != "chat"]


@router.get("/recent")
def recent_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = None,
    limit: int = 8,
):
    """Most-recently-touched sessions across ALL actions (for the "Recent"
    switcher). Company-scoped like everything else."""
    q = db.query(WorkspaceSession).filter(
        WorkspaceSession.owner_id == current_user.id, WorkspaceSession.status == "active"
    )
    if company_id == "none":
        q = q.filter(WorkspaceSession.company_id.is_(None))
    elif company_id:
        q = q.filter(WorkspaceSession.company_id == company_id)
    sessions = q.order_by(WorkspaceSession.updated_at.desc()).limit(min(limit, 50)).all()
    return [_serialize(db, s, full=False) for s in sessions]


@router.get("")
def list_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    company_id: str | None = None,
    action: str | None = None,
    status: str | None = "active",
):
    q = db.query(WorkspaceSession).filter(WorkspaceSession.owner_id == current_user.id)
    if action:
        q = q.filter(WorkspaceSession.action == action)
    if status and status != "all":
        q = q.filter(WorkspaceSession.status == status)
    if company_id == "none":
        q = q.filter(WorkspaceSession.company_id.is_(None))
    elif company_id:
        q = q.filter(WorkspaceSession.company_id == company_id)
    sessions = q.order_by(WorkspaceSession.updated_at.desc()).all()
    return [_serialize(db, s, full=False) for s in sessions]


@router.post("", status_code=201)
def create_session(payload: WorkspaceCreate, current_user: CurrentUser, db: Session = Depends(get_db)):
    action = get_action(payload.action)
    if action is None:
        raise ValidationError(f"Unknown workspace action '{payload.action}'.")
    _assert_company(db, payload.company_id, current_user.id)

    # Website Builder modes (only meaningful for web_builder). "client" mode
    # scopes the session + project to a Client; "improve" records the source URL.
    mode = "new"
    client = None
    if payload.action == "web_builder":
        mode = (payload.mode or "new").strip().lower()
        if mode not in ("new", "improve", "client"):
            raise ValidationError("mode must be 'new', 'improve', or 'client'.")
        if mode == "improve" and not (payload.source_url or "").strip():
            raise ValidationError("A source_url is required for 'improve' mode.")
        if mode == "client":
            if not payload.client_id:
                raise ValidationError("A client_id is required for 'client' mode.")
            client = (
                db.query(Client)
                .filter(Client.id == payload.client_id, Client.owner_id == current_user.id)
                .first()
            )
            if not client:
                raise NotFoundError(f"Client '{payload.client_id}' not found")

    title = (payload.title or "").strip()
    if not title:
        if client:
            title = f"{client.name} website"
        elif mode == "improve":
            host = urlparse(payload.source_url.strip()).netloc or payload.source_url.strip()
            title = f"Improve: {host}"[:80]
        else:
            title = f"New {action.label}"

    # Attach to the shared Project for this business instead of minting a
    # throwaway one per session. If the caller named an active project, use it
    # (validated as owned + same company/client); otherwise get-or-create the
    # business's default project. Client builds resolve the client's own
    # default project, keeping client work separate from the company's own.
    if payload.project_id:
        project = (
            db.query(Project)
            .filter(Project.id == payload.project_id, Project.owner_id == current_user.id)
            .first()
        )
        if not project:
            raise NotFoundError(f"Project '{payload.project_id}' not found")
        if project.company_id and payload.company_id and project.company_id != payload.company_id:
            raise ValidationError("Project belongs to a different business.")
    else:
        project = project_service.get_or_create_default_project(
            db,
            owner_id=current_user.id,
            company_id=payload.company_id,
            client_id=client.id if client else None,
        )

    initial_state: dict = {}
    if payload.action == "web_builder":
        initial_state["mode"] = mode
        if mode == "improve":
            initial_state["source_url"] = payload.source_url.strip()

    session = WorkspaceSession(
        owner_id=current_user.id,
        company_id=payload.company_id,
        client_id=client.id if client else None,
        action=payload.action,
        title=title,
        project_id=project.id,
        status="active",
        messages_json="[]",
        artifacts_json="[]",
        state_json=json.dumps(initial_state),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # A kick-off task so the workspace shows up as real, tracked work.
    _create_task(
        db,
        owner_id=current_user.id,
        company_id=payload.company_id,
        project_id=project.id,
        title=f"Define the {action.memory_noun} brief",
        status="backlog",
    )

    # Record the new session on the project's Timeline.
    project_service.record_project_event(
        db,
        project=project,
        owner_id=current_user.id,
        kind="session_created",
        title=f"Started {action.label}: {title}",
        source=payload.action,
        ref_id=session.id,
    )

    return _serialize(db, session, full=True)


@router.get("/{session_id}")
def get_session(session_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return _serialize(db, _owned_session(db, session_id, current_user.id), full=True)


@router.patch("/{session_id}")
def update_session(
    session_id: str, payload: WorkspaceUpdate, current_user: CurrentUser, db: Session = Depends(get_db)
):
    s = _owned_session(db, session_id, current_user.id)
    if payload.title is not None:
        s.title = payload.title.strip()[:255] or s.title
    if payload.status is not None:
        if payload.status not in ("active", "archived"):
            raise ValidationError("status must be 'active' or 'archived'.")
        s.status = payload.status
    db.commit()
    db.refresh(s)
    return _serialize(db, s, full=True)


@router.post("/{session_id}/turns")
def append_turns(
    session_id: str, payload: TurnsIn, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Append conversation turns and return the full stored thread.

    Persistence only — this never calls the model. The Ask Jarvis thread gets
    its reply from the command router, and both sides of the exchange are
    recorded here so every device reads one history.

    Appends are DEDUPLICATED by (role, content, ts). Two devices can send the
    same turn — the migration uploads overlapping history, and a retry after a
    dropped response repeats a turn — and neither should produce a duplicate
    message in the thread.
    """
    s = _owned_session(db, session_id, current_user.id)
    existing = json.loads(s.messages_json or "[]")
    seen = {(m.get("role"), m.get("content"), m.get("ts")) for m in existing}

    added = 0
    for turn in payload.turns:
        role = turn.get("role")
        content = turn.get("content")
        if not role or content is None:
            continue
        key = (role, content, turn.get("ts"))
        if key in seen:
            continue
        seen.add(key)
        existing.append({
            "role": role,
            "content": content,
            "ts": turn.get("ts") or datetime.now(timezone.utc).isoformat(),
        })
        added += 1

    # Oldest first, so a merged history from two devices reads in the order it
    # actually happened rather than the order it was uploaded.
    existing.sort(key=lambda m: m.get("ts") or "")
    s.messages_json = json.dumps(existing)
    db.commit()
    db.refresh(s)
    # Committing is what broadcasts "conversations" to every connected client
    # (app.db.sync_hooks) — there is no second sync path here.
    return {"id": s.id, "added": added, "messages": existing}


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    s = _owned_session(db, session_id, current_user.id)
    db.delete(s)
    db.commit()


# --- Attachments & artifacts ----------------------------------------------


@router.post("/{session_id}/artifacts")
def save_artifact(
    session_id: str, payload: ArtifactIn, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Explicitly save/export a deliverable as a versioned artifact (the model
    autosaves too; this is for the "Save this version" affordance)."""
    s = _owned_session(db, session_id, current_user.id)
    arts = ws.load_json(s.artifacts_json, [])
    artifact = ws.make_artifact(
        title=payload.title,
        content=payload.content,
        kind=payload.kind,
        stage=payload.stage,
        version=ws.next_version(arts, payload.title),
    )
    arts.append(artifact)
    s.artifacts_json = json.dumps(arts)
    db.commit()
    _session_event(db, s, kind="artifact_saved", title=f"Saved {payload.title}", ref_id=artifact["id"])
    return artifact


@router.post("/{session_id}/attach-project")
def attach_project(
    session_id: str, payload: AttachProjectIn, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Re-point this workspace at an existing Project the user owns (so its
    tasks/output land in that project instead of the auto-created one)."""
    s = _owned_session(db, session_id, current_user.id)
    project = (
        db.query(Project)
        .filter(Project.id == payload.project_id, Project.owner_id == current_user.id)
        .first()
    )
    if not project:
        raise NotFoundError(f"Project '{payload.project_id}' not found")
    s.project_id = project.id
    db.commit()
    db.refresh(s)
    return _serialize(db, s, full=True)


@router.post("/{session_id}/tasks", status_code=201)
def add_task(session_id: str, payload: TaskIn, current_user: CurrentUser, db: Session = Depends(get_db)):
    """Attach a new tracked Task to this workspace's project."""
    s = _owned_session(db, session_id, current_user.id)
    task = _create_task(
        db,
        owner_id=current_user.id,
        company_id=s.company_id,
        project_id=s.project_id,
        title=payload.title,
        status=payload.status,
    )
    _session_event(db, s, kind="task_created", title=f"Task: {payload.title}", ref_id=task.id)
    return {"id": task.id, "title": task.title, "status": task.status, "due_date": task.due_date}


# --- Logo image generation ------------------------------------------------


@router.get("/image/status")
def image_status(current_user: CurrentUser):
    """Whether real image generation is available (Logo Studio uses this to
    decide between generating a mark and recording the concept spec)."""
    provider = get_image_provider()
    return {"configured": provider is not None, "provider": provider.name if provider else None}


@router.post("/{session_id}/image")
async def generate_image(
    session_id: str, payload: ImageIn, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Generate a real logo concept image and store it as an artifact + into
    the workspace's `state.images`. If no image provider is configured this
    returns `configured: false` — it never fabricates an image."""
    s = _owned_session(db, session_id, current_user.id)
    prompt = payload.prompt.strip()
    if not prompt:
        raise ValidationError("An image prompt is required.")

    provider = get_image_provider()
    if provider is None:
        return {
            "configured": False,
            "message": "Image generation isn't configured — set OPENAI_API_KEY to enable the Logo Studio's generation seam. The concept spec is saved and can be handed to a designer.",
        }

    result = await provider.generate_image(prompt, size=payload.size)
    data_url = f"data:image/png;base64,{result.b64_png}"

    # Store the image bytes as an artifact (so it survives + versions), and a
    # lightweight record (data URL) into structured state for the panel.
    arts = ws.load_json(s.artifacts_json, [])
    title = payload.name or f"Logo concept {len(arts) + 1}"
    artifact = ws.make_artifact(
        title=title, content=data_url, kind="image", stage="images",
        version=ws.next_version(arts, title),
    )
    arts.append(artifact)
    s.artifacts_json = json.dumps(arts)

    state = ws.load_json(s.state_json, {})
    images = list(state.get("images") or [])
    images.append({
        "id": artifact["id"],
        "concept_id": payload.concept_id,
        "name": title,
        "prompt": prompt,
        "data_url": data_url,
        "model": result.model,
        "ts": time.time(),
    })
    state["images"] = images
    s.state_json = json.dumps(state)
    db.commit()
    _session_event(db, s, kind="image_generated", title=f"Generated image: {title}", ref_id=artifact["id"])

    return {"configured": True, "image": {**artifact, "concept_id": payload.concept_id}}


# --- Research web-search seam ---------------------------------------------


@router.get("/search/status")
def search_status(current_user: CurrentUser):
    """Whether live web search is wired for the Research Desk. When a provider
    is configured (SEARCH_PROVIDER + its key), Deep Research retrieves real
    pages and cites them; otherwise it reasons from model knowledge and marks
    sources as derived — reported honestly either way."""
    from app.search.factory import get_search_provider

    provider = get_search_provider()
    if provider is None:
        return {
            "configured": False,
            "provider": None,
            "message": "Live web search isn't configured. Research runs from model knowledge; sources are marked derived and no URLs are fabricated. Set SEARCH_PROVIDER (+ the provider's key) to enable live retrieval.",
        }
    return {
        "configured": True,
        "provider": provider.name,
        "message": f"Live web search enabled via '{provider.name}'. Deep Research retrieves and cites real sources (cached to avoid re-billing).",
    }


# --- Website build pipeline -----------------------------------------------


class WebsiteBuildIn(BaseModel):
    #: False = run the (safe) plan stages and stop at the approval gate.
    #: True = the approved major action: generate images + React components + preview.
    approved: bool = False
    brief: str | None = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/{session_id}/website/build")
async def build_website(
    session_id: str, payload: WebsiteBuildIn, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Run the Build a Website pipeline as live-progress SSE.

    Phase 1 (always): plan the site — sitemap, layouts, copy, design — and stop
    at an approval gate. Phase 2 (only when ``approved``): the major action —
    generate images (real or labelled placeholders), real React component files,
    and a runnable preview assembled from those components. Everything is saved
    to the workspace state + versioned artifacts + Project Manager tasks as each
    stage completes, so progress survives a disconnect."""
    session = _owned_session(db, session_id, current_user.id)
    if session.action != "web_builder":
        raise ValidationError("The build pipeline only applies to the Website Studio.")

    owner_id = current_user.id
    company_id = session.company_id
    project_id = session.project_id
    approved = payload.approved
    brief = (payload.brief or "").strip()
    company_name = ""
    if company_id:
        company = db.query(Company).filter(Company.id == company_id).first()
        company_name = company.name if company else ""

    # Website Builder mode: the build is for the client (client mode), for an
    # existing site to improve (improve mode), or a fresh company site (new).
    init_state = ws.load_json(session.state_json, {})
    mode = init_state.get("mode", "new")
    source_url = init_state.get("source_url")
    directive = ""
    if session.client_id:
        client = db.query(Client).filter(Client.id == session.client_id).first()
        if client:
            company_name = client.name  # tailor the site to the client
            directive = f"This website is being built for the client '{client.name}'" + (
                f" (existing site: {client.website})." if client.website else "."
            )

    def _stage(stage, label, status, detail=""):
        return _sse({"type": "stage", "stage": stage, "label": label, "status": status, "detail": detail})

    async def event_stream():
        provider = get_ai_provider()
        wdb = SessionLocal()
        try:
            s = wdb.query(WorkspaceSession).filter(WorkspaceSession.id == session_id).first()
            state = ws.load_json(s.state_json, {})

            def save_state():
                s.state_json = json.dumps(state)
                wdb.commit()

            def add_artifact(title, content, kind, stage):
                arts = ws.load_json(s.artifacts_json, [])
                arts.append(
                    ws.make_artifact(
                        title=title, content=content, kind=kind, stage=stage,
                        version=ws.next_version(arts, title),
                    )
                )
                s.artifacts_json = json.dumps(arts)
                wdb.commit()

            # --- Improve mode: crawl & analyze the existing site first ---
            analysis = state.get("source_analysis")
            need_plan = not state.get("sitemap") or bool(brief)
            if mode == "improve" and source_url and need_plan and not analysis:
                yield _stage("analyze", "Analyzing existing website", "running", source_url)
                try:
                    analysis = await website_analyzer.analyze(source_url)
                    state["source_analysis"] = analysis
                    save_state()
                    add_artifact("Existing site analysis", json.dumps(analysis, indent=2)[:8000], "document", "analyze")
                    yield _stage(
                        "analyze", "Analyzing existing website", "done",
                        f"{analysis.get('fetched', 0)} page(s), brand: {analysis.get('brand') or 'n/a'}",
                    )
                except ValidationError as exc:
                    yield _stage("analyze", "Analyzing existing website", "error", str(exc))
                    yield _sse({"type": "error", "message": str(exc)})
                    return

            # --- Phase 1: plan (safe) ---
            if need_plan:
                yield _stage("plan", "Planning sitemap, layouts & copy", "running")
                default_seed = (
                    "Redesign and improve this existing website." if mode == "improve"
                    else "Build a marketing website for this business."
                )
                seed = brief or state.get("requirements") or default_seed
                plan = await website_builder.plan_site(
                    provider, seed, company_name, state, analysis=analysis, directive=directive
                )
                if not plan.get("sitemap"):
                    yield _stage("plan", "Planning sitemap, layouts & copy", "error", "The planner returned no pages.")
                    yield _sse({"type": "error", "message": "Planning failed — check the AI provider/key and try again."})
                    return
                for k in ("sitemap", "layouts", "copy", "design"):
                    if plan.get(k):
                        state[k] = plan[k]
                if brief:
                    state["requirements"] = brief
                save_state()
                add_artifact("Site plan", json.dumps(plan, indent=2)[:8000], "document", "plan")
                pages = state.get("sitemap") or []
                for p in pages:
                    _create_task(
                        wdb, owner_id=owner_id, company_id=company_id, project_id=project_id,
                        title=f"Page: {p.get('title') or p.get('path')}", status="review",
                    )
                yield _stage("plan", "Planning sitemap, layouts & copy", "done", f"{len(pages)} pages")

            pages = state.get("sitemap") or []

            # --- Approval gate before the major action ---
            if not approved:
                yield _sse(
                    {
                        "type": "awaiting_approval",
                        "summary": f"Plan ready — {len(pages)} pages. Approve to generate images, React components, and a live preview.",
                        "major_actions": [
                            f"Generate {len(pages)} image(s) / placeholders",
                            f"Generate React components for {len(pages)} page(s)",
                            "Assemble a runnable preview",
                        ],
                    }
                )
                # awaiting_approval IS the terminal event for the plan phase;
                # no `done` follows, so the client's approval gate stays up.
                return

            # --- Phase 2: the approved major action ---
            pal = (state.get("design") or {}).get("palette") or []
            palette_bg = pal[0]["hex"] if pal and isinstance(pal[0], dict) and pal[0].get("hex") else "#0b1220"

            # Images (real or labelled placeholders) — components reference them.
            yield _stage("images", "Generating images", "running")
            imgs: list[dict] = []
            any_generated = False
            async for rec, generated in website_builder.generate_images(state, company_name, palette_bg=palette_bg):
                imgs.append(rec)
                any_generated = any_generated or generated
                add_artifact(f"{rec['role']} — {rec['page']}", rec["data_url"], "image", "images")
                yield _stage("images", "Generating images", "running", f"{len(imgs)}/{len(pages)} · {rec['status']}")
            state["images"] = imgs
            save_state()
            _create_task(
                wdb, owner_id=owner_id, company_id=company_id, project_id=project_id,
                title=f"Images ({len(imgs)})", status="review",
            )
            yield _stage("images", "Generating images", "done", f"{len(imgs)} ({'generated' if any_generated else 'placeholders'})")

            # React components (real files).
            yield _stage("components", "Generating React components", "running")
            comp = await website_builder.generate_components(provider, state, company_name)
            files = comp.get("files") or []
            if not files:
                yield _stage("components", "Generating React components", "error", "No files returned.")
                yield _sse({"type": "error", "message": "Component generation failed — check the AI provider/key and try again."})
                return
            state["components"] = comp
            for f in files:
                add_artifact(f.get("path") or "component.jsx", f.get("content") or "", "code", "components")
            save_state()
            _create_task(
                wdb, owner_id=owner_id, company_id=company_id, project_id=project_id,
                title=f"React components ({len(files)} files)", status="review",
            )
            yield _stage("components", "Generating React components", "done", f"{len(files)} files")

            # Runnable preview assembled from the actual components.
            yield _stage("preview", "Assembling runnable preview", "running")
            preview_html = website_builder.assemble_preview(files, imgs)
            state["preview_html"] = preview_html
            save_state()
            add_artifact("Preview (index.html)", preview_html, "document", "preview")
            yield _stage("preview", "Assembling runnable preview", "done")

            try:
                await memory_service.record_memory(
                    wdb, owner_id=owner_id, kind="decision",
                    title=f"Website Studio: built site for {company_name or 'the business'}",
                    content=(
                        f"Built a {len(pages)}-page React site. Pages: "
                        + ", ".join(p.get("title") or p.get("path") for p in pages)
                        + f". Components: {len(files)} files. Images: {len(imgs)}."
                    ),
                    scope="company" if company_id else "organization",
                    company_id=company_id, project_id=project_id, source="workspace",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("website_build_memory_failed", error=str(exc))

            if project_id:
                try:
                    built_project = wdb.query(Project).filter(Project.id == project_id).first()
                    if built_project:
                        project_service.record_project_event(
                            wdb, project=built_project, owner_id=owner_id,
                            kind="website_built", source="web_builder",
                            title=f"Built {len(pages)}-page site for {company_name or 'the business'}",
                            detail=f"{len(files)} component files, {len(imgs)} images.",
                            ref_id=session_id,
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.error("website_build_timeline_failed", error=str(exc))

            yield _sse({"type": "done", "phase": "build", "pages": len(pages), "files": len(files), "images": len(imgs)})
        except Exception as exc:  # noqa: BLE001
            logger.error("website_build_failed", session_id=session_id, error=str(exc))
            yield _sse({"type": "error", "message": "The website build failed — check the AI provider/key."})
        finally:
            wdb.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- Streaming message ----------------------------------------------------


async def _structure_state(action, request_text: str, deliverable_text: str) -> dict | None:
    """Fallback structuring pass: when a turn's prose didn't carry a parseable
    ``jarvis-state`` block (e.g. a long research report that ran past it), ask
    the model to extract the structured state from its own deliverable so the
    studio panels still populate. Returns a state patch or None; never raises."""
    if not action.state_schema:
        return None
    schema_lines = "\n".join(f"- {k}: {v}" for k, v in action.state_schema.items())
    system = (
        "You convert a finished deliverable into structured workspace state. "
        "Return ONLY a single JSON object — no prose, no markdown fence. Use ONLY "
        "these keys, and include only the ones the deliverable actually supports "
        "(omit any you'd have to invent):\n" + schema_lines
    )
    user = (
        f"Original request:\n{request_text}\n\nDeliverable produced:\n{deliverable_text}\n\n"
        "Return the JSON state object now."
    )
    try:
        provider = get_ai_provider()
        result = await provider.complete(
            messages=[Message(role="system", content=system), Message(role="user", content=user)],
            max_tokens=4096,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("workspace_structure_fallback_failed", error=str(exc))
        return None
    return ws.parse_loose_json(result.text)


@router.post("/{session_id}/message")
async def send_message(
    session_id: str, payload: MessageIn, current_user: CurrentUser, db: Session = Depends(get_db)
):
    """Append the user's message, then stream Jarvis's response token-by-token
    as SSE. On completion the assistant turn is saved (minus its jarvis-state
    block), that block is merged into the workspace's structured state, a
    versioned deliverable artifact is stored, the turn's Task is advanced, and
    context is written to AI Memory — so nothing is lost if the browser closes
    mid-stream (the user turn + task are persisted before streaming begins)."""
    content = payload.content.strip()
    if not content:
        raise ValidationError("Message content is required.")

    session = _owned_session(db, session_id, current_user.id)
    action = get_action(session.action)
    if action is None:
        raise ValidationError(f"Unknown workspace action '{session.action}'.")

    # Persist the user turn immediately (survives a mid-stream disconnect).
    history = ws.load_json(session.messages_json, [])
    stage_note = f"\n\n(Working in the '{payload.stage}' stage.)" if payload.stage else ""
    history.append({"role": "user", "content": content})
    session.messages_json = json.dumps(history)
    if session.title.startswith("New "):
        session.title = content[:80]  # first message names the session
    db.commit()

    # Track this turn as a real Task.
    turn_task = _create_task(
        db,
        owner_id=current_user.id,
        company_id=session.company_id,
        project_id=session.project_id,
        title=content[:120],
        status="in_progress",
    )

    owner_id = current_user.id
    company_id = session.company_id
    project_id = session.project_id
    task_id = turn_task.id
    stage = payload.stage or ""
    current_state = ws.load_json(session.state_json, {})

    # Live web search for Deep Research: retrieve real pages, attach them to the
    # session state now (so the Sources panel shows real, cited sources), and
    # ground the model in them. When search isn't configured this is a no-op and
    # Deep Research keeps its honest model-knowledge mode (sources marked derived).
    retrieved_block = ""
    if action.key == "deep_research":
        try:
            sr = await search_service.search(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("workspace_search_failed", session_id=session_id, error=str(exc))
            sr = {"configured": False, "results": []}
        if sr.get("configured") and sr.get("results"):
            sources = search_service.to_sources(sr["results"])
            current_state = ws.deep_merge(current_state, {"sources": sources})
            session.state_json = json.dumps(current_state)
            db.commit()
            src_lines = "\n".join(
                f"[{s['id']}] {s['title']} — {s['url']}\n    {s['note']}" for s in sources
            )
            cached = " (served from cache)" if sr.get("cached") else ""
            retrieved_block = (
                f"\n\n## Retrieved web sources{cached}\n"
                "These are REAL pages retrieved by a live web search for this query. Ground "
                "every factual claim in them, add a `citations` entry mapping each claim to the "
                'source id it came from, and keep these `sources` with "derived": false. Do not '
                "invent other sources, URLs, or figures beyond what these support.\n" + src_lines
            )

    # Company context for the system prompt — including the Brand Brain (the
    # workspace's real store), so Quick Actions like Website Builder generate
    # from actual products/pricing rather than invented data.
    company_line = ""
    if company_id:
        company = db.query(Company).filter(Company.id == company_id).first()
        if company:
            company_line = f"\n\nActive company: {company.name!r}. Tailor everything to this business."
            company_line += brand_brain_service.brand_prompt_context(db, company_id)

    provider = get_ai_provider()
    system_prompt = build_system_prompt(action, company_line=company_line, state=current_state)
    if retrieved_block:
        system_prompt += retrieved_block
    convo = [Message(role=m["role"], content=m["content"]) for m in history[-MAX_HISTORY_TURNS:]]
    if stage_note and convo:
        convo[-1] = Message(role=convo[-1].role, content=convo[-1].content + stage_note)
    provider_messages = [Message(role="system", content=system_prompt)] + convo

    async def _persist(full_text: str, errored: bool) -> None:
        """Save the assistant turn, merge structured state, store a versioned
        artifact, advance the task, and write memory. Runs from the generator's
        `finally`, so even a mid-stream client disconnect saves whatever was
        generated. Uses a fresh session (the request's db is closing)."""
        saved = not errored and bool(full_text.strip())
        known_keys = list(action.state_schema)
        visible, patch = ws.extract_state_block(full_text, known_keys) if saved else (full_text, None)
        # If the model didn't emit a usable state block — missing, unparseable,
        # or an empty {} (common for long prose deliverables like a research
        # report) — recover the structured state with a lightweight second pass
        # so the studio panels still fill.
        if saved and not patch:
            patch = await _structure_state(action, content, visible)
        write_db = SessionLocal()
        try:
            s = write_db.query(WorkspaceSession).filter(WorkspaceSession.id == session_id).first()
            if s and saved:
                msgs = ws.load_json(s.messages_json, [])
                msgs.append({"role": "assistant", "content": visible})
                s.messages_json = json.dumps(msgs)

                arts = ws.load_json(s.artifacts_json, [])
                art_title = content[:80]
                arts.append(
                    ws.make_artifact(
                        title=art_title, content=visible, kind="document", stage=stage,
                        version=ws.next_version(arts, art_title),
                    )
                )
                s.artifacts_json = json.dumps(arts)

                if patch:
                    merged = ws.deep_merge(ws.load_json(s.state_json, {}), patch)
                    s.state_json = json.dumps(merged)
                write_db.commit()

            t = write_db.query(Task).filter(Task.id == task_id).first()
            if t:
                t.status = "review" if saved else "backlog"
                write_db.commit()

            if saved:
                try:
                    await memory_service.record_memory(
                        write_db,
                        owner_id=owner_id,
                        kind=action.memory_kind,
                        title=f"{action.label}: {content[:100]}",
                        content=f"Request: {content}\n\n{action.memory_noun.title()}:\n{visible}",
                        scope="company" if company_id else "organization",
                        company_id=company_id,
                        project_id=project_id,
                        source="workspace",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("workspace_memory_write_failed", error=str(exc))
        finally:
            write_db.close()

    async def event_stream():
        full_text = ""
        errored = False
        persisted = False
        streamer = ws.VisibleStreamer()
        try:
            try:
                # Studio turns are deliverables (a full sitemap + copy, a set of
                # logo concepts, a research report) plus a structured-state block,
                # so they need a much larger budget than a chat reply — otherwise
                # the trailing jarvis-state fence gets truncated.
                async for chunk in provider.stream(messages=provider_messages, max_tokens=8192):
                    full_text += chunk
                    visible_chunk = streamer.feed(chunk)
                    if visible_chunk:
                        yield _sse({"type": "token", "text": visible_chunk})
            except Exception as exc:  # noqa: BLE001
                errored = True
                logger.error("workspace_stream_failed", session_id=session_id, error=str(exc))
                yield _sse({"type": "error", "message": "The AI provider stream failed — check the API key in .env."})
            else:
                tail = streamer.flush()
                if tail:
                    yield _sse({"type": "token", "text": tail})
                # Persist BEFORE signaling done — including the structuring
                # fallback, which can add a couple seconds — so the client's
                # refetch-on-done always sees the saved structured state.
                await _persist(full_text, errored=False)
                persisted = True
                visible, _ = ws.extract_state_block(full_text, list(action.state_schema))
                yield _sse({"type": "done", "task_id": task_id, "text": visible})
        finally:
            # Covers client disconnect / provider error mid-stream: persist
            # whatever we have so nothing is lost. Skipped if we already
            # persisted on normal completion above.
            if not persisted:
                await _persist(full_text, errored)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
