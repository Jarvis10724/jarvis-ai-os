"""
Website build pipeline for the Build a Website Quick Action.

Turns a brief into a buildable React site through real, sequential stages:
plan (sitemap + layouts + copy + design) -> images (generated or labelled SVG
placeholders) -> React components (real .jsx files) -> a runnable preview
assembled from those actual components. Each stage returns structured data the
endpoint persists into the workspace's state/artifacts/tasks and streams
progress for.

Kept separate from the HTTP endpoint so the stages are unit-testable and the
prompts live in one place. Uses only the existing AI + image provider seams.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import uuid

from app.ai_providers.base import Message
from app.ai_providers.factory import get_image_provider
from app.core import workspace_state as ws
from app.logging_config import get_logger

logger = get_logger(__name__)

MAX_PAGES = 5


async def _complete_json(provider, system: str, user: str, *, max_tokens: int = 8192) -> dict:
    """One structured-JSON model call, parsed leniently. Returns {} on failure."""
    result = await provider.complete(
        messages=[Message(role="system", content=system), Message(role="user", content=user)],
        max_tokens=max_tokens,
        temperature=0.5,
    )
    return ws.parse_loose_json(result.text) or {}


# --- Stage 1: plan -------------------------------------------------------------

_PLAN_SYS = (
    "You are a senior web architect and conversion copywriter. Given a business brief, "
    "produce a complete, buildable plan for a focused marketing website (max %d pages). "
    "Return ONLY a JSON object with these keys:\n"
    '{"sitemap":[{"path":"/","title":"Home","purpose":"...","sections":["..."]}],'
    ' "layouts":{"/":{"sections":[{"name":"Hero","type":"hero","description":"..."}]}},'
    ' "copy":{"/":{"heading":"...","sections":[{"title":"...","body":"..."}]}},'
    ' "design":{"palette":[{"name":"Primary","hex":"#0f766e"}],'
    ' "typography":{"heading":"...","body":"..."},"style_notes":"..."}}\n'
    "Write REAL copy specific to the business — never lorem ipsum. Every page in sitemap "
    "must have a matching layouts and copy entry keyed by its path. Include a Hero section "
    "on the home page. Keep it tasteful and modern."
) % MAX_PAGES


async def plan_site(provider, brief: str, company_name: str, state: dict) -> dict:
    context = ""
    existing = {k: state.get(k) for k in ("sitemap", "requirements") if state.get(k)}
    if existing:
        context = "\n\nExisting workspace context (build on it):\n" + json.dumps(existing)[:2000]
    user = f"Business: {company_name or 'the business'}\n\nBrief:\n{brief}{context}"
    plan = await _complete_json(provider, _PLAN_SYS, user)
    # Trim to a sane page count.
    if isinstance(plan.get("sitemap"), list):
        plan["sitemap"] = plan["sitemap"][:MAX_PAGES]
    return plan


# --- Stage 2: images (real or placeholder) -------------------------------------


def placeholder_svg(width: int, height: int, label: str, bg: str = "#0b1220", fg: str = "#5eead4") -> str:
    """A real, self-contained SVG asset used when image generation isn't
    configured. Not mock data — a valid, labelled placeholder image."""
    safe = (label or "Image").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    font = max(16, width // 26)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="{bg}"/>'
        f'<rect x="8" y="8" width="{width-16}" height="{height-16}" fill="none" '
        f'stroke="{fg}" stroke-opacity="0.35" stroke-dasharray="10 8"/>'
        f'<text x="50%" y="50%" fill="{fg}" font-family="system-ui,sans-serif" '
        f'font-size="{font}" text-anchor="middle" dominant-baseline="middle">{safe}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def image_slots(state: dict) -> list[dict]:
    """One hero image slot per page, derived from the sitemap/layouts."""
    slots: list[dict] = []
    for page in ws.load_json(json.dumps(state.get("sitemap") or []), []):
        if not isinstance(page, dict):
            continue
        path = page.get("path", "/")
        title = page.get("title") or path
        purpose = page.get("purpose") or ""
        slots.append(
            {
                "id": f"img_{uuid.uuid4().hex[:8]}",
                "page": path,
                "role": "hero",
                "alt": f"{title} hero image",
                "prompt": f"Hero image for the '{title}' page of {state.get('_company','a business')}. {purpose}. "
                "Modern, on-brand, high quality, no text.",
            }
        )
    return slots


async def generate_images(state: dict, company_name: str, *, palette_bg: str = "#0b1220"):
    """Yield (image_record, generated_bool) per slot. Real image when a provider
    is configured, otherwise a labelled SVG placeholder — never a fake photo."""
    provider = get_image_provider()
    state = {**state, "_company": company_name}
    for slot in image_slots(state):
        record = {**slot, "status": "placeholder", "data_url": None}
        if provider is not None:
            try:
                result = await provider.generate_image(slot["prompt"], size="1024x1024")
                record["data_url"] = f"data:image/png;base64,{result.b64_png}"
                record["status"] = "generated"
                record["model"] = result.model
                yield record, True
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("website_image_failed", error=str(exc))
        record["data_url"] = placeholder_svg(1200, 630, f"{slot['alt']}", bg=palette_bg)
        yield record, False


# --- Stage 3: React components -------------------------------------------------

_COMPONENTS_SYS = (
    "You are a senior React engineer. Given a site plan (sitemap, layouts, copy, design) "
    "and a list of available images, generate a real, clean, COMPACT single-page React site.\n"
    "Return ONLY a JSON object: {\"files\":[{\"path\":\"src/App.jsx\",\"language\":\"jsx\","
    "\"content\":\"...\",\"description\":\"...\"}]}.\n"
    "Keep it small enough to fit in one response — aim for AT MOST 6 files and keep each "
    "component focused (~15-45 lines). Do not repeat large blocks.\n"
    "Requirements:\n"
    "- src/App.jsx renders <Navbar/>, one <Section/> per page as anchored sections, and "
    "<Footer/> (single-page site with anchor nav). Define each page's section as a small "
    "component either inside App.jsx or in one src/components/Sections.jsx file — do NOT create "
    "a separate file per page.\n"
    "- Also include src/components/Navbar.jsx, src/components/Footer.jsx, and a single "
    "src/styles.css applying the palette/typography via className selectors.\n"
    "- Use hoistable `function Name(props){...}` declarations (NOT const arrow components) so "
    "they work when concatenated. Use `export default function App(){...}` for App and a named "
    "`function` for others with a matching `export`. Import React at the top of each file.\n"
    "- Use the REAL copy provided (condense long copy rather than dropping files).\n"
    "- For images, reference `window.__ASSETS['<image id>']` as the src, with a solid-color "
    "fallback; use the provided image ids and alt text.\n"
    "- No external UI/component libraries and no routing library — plain React + CSS only."
)


async def generate_components(provider, state: dict, company_name: str) -> dict:
    # Condense copy so the input (and thus the model's echo of it) stays small,
    # keeping the whole JSON response comfortably within the token budget.
    plan = {
        "sitemap": state.get("sitemap"),
        "layouts": state.get("layouts"),
        "copy": state.get("copy"),
        "design": state.get("design"),
    }
    images = [
        {"id": im.get("id"), "page": im.get("page"), "role": im.get("role"), "alt": im.get("alt")}
        for im in (state.get("images") or [])
    ]
    user = (
        f"Business: {company_name or 'the business'}\n\nSite plan (JSON):\n"
        + json.dumps(plan)[:7000]
        + "\n\nAvailable images (reference by id via window.__ASSETS):\n"
        + json.dumps(images)
    )
    # Extra headroom so a multi-file site never truncates mid-JSON.
    out = await _complete_json(provider, _COMPONENTS_SYS, user, max_tokens=16000)
    files = out.get("files") if isinstance(out, dict) else None
    return {"files": files if isinstance(files, list) else []}


# --- Stage 4: runnable preview (assembled from the actual components) -----------

# Strip every import — single-line, multi-line specifier lists, and bare
# side-effect imports (`import './styles.css';`). Babel's react preset does NOT
# transform ES module `import`, so any survivor is a runtime SyntaxError.
_IMPORT_RE = re.compile(
    r"^[ \t]*import\b[\s\S]*?(?:from[ \t]*['\"][^'\"]+['\"]|['\"][^'\"]+['\"])[ \t]*;?",
    re.MULTILINE,
)
_EXPORT_DEFAULT_FUNC_RE = re.compile(r"export\s+default\s+function", re.MULTILINE)
_EXPORT_KW_RE = re.compile(r"^\s*export\s+(?=(function|const|let|var|class)\b)", re.MULTILINE)
_EXPORT_BLOCK_RE = re.compile(r"^\s*export\s*\{[^}]*\}\s*;?\s*$", re.MULTILINE)
# Any remaining `export ...` line (e.g. `export default Navbar;`) — the symbol
# is already defined in the shared scope, so drop the re-export entirely.
_EXPORT_LEFTOVER_RE = re.compile(r"^\s*export\s+.+$", re.MULTILINE)


def _strip_module_syntax(code: str) -> str:
    """Turn an ES-module React component file into global-scope JSX suitable for
    in-browser Babel: drop imports/exports (components share one scope + React
    global). Relies on components being hoistable `function` declarations.

    Order matters: convert `export default function X` to a plain declaration
    first, strip the `export` keyword off other declarations, then remove any
    leftover `export` statement (bare default re-exports like `export default X;`
    and `export { ... }`) — a single stray `export` is a syntax error that would
    blank the whole Babel-compiled preview."""
    code = _IMPORT_RE.sub("", code)
    code = _EXPORT_DEFAULT_FUNC_RE.sub("function", code)
    code = _EXPORT_KW_RE.sub("", code)
    code = _EXPORT_BLOCK_RE.sub("", code)
    code = _EXPORT_LEFTOVER_RE.sub("", code)
    return code


def assemble_preview(files: list[dict], images: list[dict]) -> str:
    """Build a single runnable HTML document from the ACTUAL generated component
    files: React 18 + Babel standalone via CDN, styles inlined, images provided
    through window.__ASSETS, and <App/> mounted. Rendered in a sandboxed iframe."""
    css = ""
    scripts: list[dict] = []
    for f in files:
        path = (f.get("path") or "").lower()
        content = f.get("content") or ""
        if path.endswith(".css"):
            css += "\n" + content
        elif path.endswith((".jsx", ".tsx", ".js")):
            scripts.append(f)

    # App.jsx last so its references to other components are defined (functions
    # are hoisted, but keep ordering sane for any const helpers).
    scripts.sort(key=lambda f: 1 if "app." in (f.get("path") or "").lower() else 0)
    body = "\n\n".join(_strip_module_syntax(f.get("content") or "") for f in scripts)

    assets = {im["id"]: im.get("data_url") for im in images if im.get("id") and im.get("data_url")}
    assets_json = json.dumps(assets)

    # The component source is stored in a text/plain block and compiled by an
    # explicit bootstrap with the CLASSIC JSX runtime — NOT the `text/babel`
    # auto-runner, which defaults to the automatic runtime and injects
    # `import {jsx} from 'react/jsx-runtime'` (a bare import fails when eval'd).
    # Any compile/runtime error is shown in the preview instead of a blank page.
    source = (
        "const {useState, useEffect} = React;\n"
        f"{body}\n"
        "const __root = ReactDOM.createRoot(document.getElementById('root'));\n"
        "__root.render(React.createElement(App));\n"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<script crossorigin src='https://unpkg.com/react@18/umd/react.production.min.js'></script>"
        "<script crossorigin src='https://unpkg.com/react-dom@18/umd/react-dom.production.min.js'></script>"
        "<script src='https://unpkg.com/@babel/standalone/babel.min.js'></script>"
        f"<style>{css}</style></head><body><div id='root'></div>"
        f"<script>window.__ASSETS = {assets_json};</script>"
        '<script id="__src" type="text/plain">\n' + source + "</script>\n"
        "<script>\n"
        "try {\n"
        "  var __code = Babel.transform(document.getElementById('__src').textContent,"
        " { presets: [['react', { runtime: 'classic' }]] }).code;\n"
        "  (0, eval)(__code);\n"
        "} catch (e) {\n"
        "  document.getElementById('root').innerHTML ="
        " '<pre style=\"color:#b91c1c;padding:16px;white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace\">'"
        " + 'Preview build error:\\n' + (e && e.message ? e.message : String(e)) + '</pre>';\n"
        "}\n"
        "</script></body></html>"
    )
