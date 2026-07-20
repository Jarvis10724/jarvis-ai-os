"""
Coverage for the Build a Website pipeline
(app.core.website_builder + the /workspaces/{id}/website/build SSE endpoint).

The AI + image providers are monkeypatched so tests run offline and
deterministically. Verifies: the plan phase produces sitemap/layouts/copy/design
+ per-page tasks and stops at the approval gate; the approved major action
generates images (placeholders here), real React component files, and a runnable
preview assembled from those components; everything lands in state/artifacts/
Project-Manager tasks; the endpoint is company-isolated and owner-scoped.
"""
import json

import pytest

API = "/api/v1"


def _register_and_login(client, email, password="supersecret123"):
    client.post(f"{API}/auth/register", json={"email": email, "password": password})
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_company(client, headers, name):
    resp = client.post(f"{API}/companies", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


_PLAN = {
    "sitemap": [
        {"path": "/", "title": "Home", "purpose": "Landing", "sections": ["Hero"]},
        {"path": "/menu", "title": "Menu", "purpose": "Products", "sections": ["List"]},
    ],
    "layouts": {
        "/": {"sections": [{"name": "Hero", "type": "hero", "description": "Big hero"}]},
        "/menu": {"sections": [{"name": "List", "type": "grid", "description": "Menu grid"}]},
    },
    "copy": {
        "/": {"heading": "Fresh Coffee", "sections": [{"title": "Hero", "body": "Real hero copy."}]},
        "/menu": {"heading": "Our Menu", "sections": [{"title": "List", "body": "Real menu copy."}]},
    },
    "design": {
        "palette": [{"name": "Primary", "hex": "#0f766e"}],
        "typography": {"heading": "Inter", "body": "Inter"},
        "style_notes": "clean and warm",
    },
}

_COMPONENTS = {
    "files": [
        # App imports Navbar/Footer via a MULTI-LINE import and re-exports with a
        # bare `export default App;` — both must be stripped for the preview to run.
        {"path": "src/App.jsx", "language": "jsx",
         "content": (
             "import React from 'react';\n"
             "import {\n  Navbar,\n  Footer\n} from './components/Chrome.jsx';\n"
             "import './styles.css';\n"
             "function App(){return <div><Navbar/><h1>{window.__ASSETS['x']?'img':'Fresh Coffee'}</h1><Footer/></div>;}\n"
             "export default App;"
         )},
        {"path": "src/components/Chrome.jsx", "language": "jsx",
         "content": "import React from 'react';\nexport function Navbar(){return <nav>Nav</nav>;}\nexport function Footer(){return <footer>Foot</footer>;}"},
        {"path": "src/styles.css", "language": "css", "content": "body{font-family:Inter,sans-serif}"},
    ]
}


class _BuildProvider:
    supports_tools = False

    async def stream(self, *a, **k):  # pragma: no cover
        yield ""

    async def complete(self, messages, **k):
        from app.ai_providers.base import CompletionResult

        system = messages[0].content
        payload = _COMPONENTS if "React engineer" in system else _PLAN
        return CompletionResult(text=json.dumps(payload), model="fake", provider="fake")


@pytest.fixture
def build_provider(monkeypatch):
    from app.api.v1.endpoints import workspaces

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _BuildProvider())
    # Default: no image provider -> placeholder path.
    from app.core import website_builder

    monkeypatch.setattr(website_builder, "get_image_provider", lambda: None)


def _new_ws(client, headers, company=None):
    body = {"action": "web_builder"}
    if company:
        body["company_id"] = company
    return client.post(f"{API}/workspaces", json=body, headers=headers).json()


def test_plan_phase_stops_at_approval_gate(client, build_provider):
    headers = _register_and_login(client, "wb-plan@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    s = _new_ws(client, headers, company)

    resp = client.post(
        f"{API}/workspaces/{s['id']}/website/build",
        json={"approved": False, "brief": "A neighborhood coffee shop"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert '"stage": "plan"' in resp.text
    assert '"type": "awaiting_approval"' in resp.text
    # The major action did NOT run yet.
    assert '"stage": "components"' not in resp.text

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    assert len(full["state"]["sitemap"]) == 2
    assert "layouts" in full["state"] and "copy" in full["state"] and "design" in full["state"]
    # No components/images generated pre-approval.
    assert full["state"].get("components", {}).get("files", []) == []
    assert full["state"].get("images", []) == []
    # Per-page tasks landed in Project Manager.
    titles = [t["title"] for t in full["tasks"]]
    assert any("Page: Home" in t for t in titles) and any("Page: Menu" in t for t in titles)
    # Plan saved as an artifact.
    assert any(a["title"] == "Site plan" for a in full["artifacts"])


def test_approved_build_generates_components_images_preview(client, build_provider):
    headers = _register_and_login(client, "wb-build@example.com")
    company = _create_company(client, headers, "PrimalPenni")
    s = _new_ws(client, headers, company)
    # plan first
    client.post(
        f"{API}/workspaces/{s['id']}/website/build",
        json={"approved": False, "brief": "A neighborhood coffee shop"},
        headers=headers,
    )
    # approved major action
    resp = client.post(
        f"{API}/workspaces/{s['id']}/website/build", json={"approved": True}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    for marker in ('"stage": "images"', '"stage": "components"', '"stage": "preview"', '"type": "done"'):
        assert marker in resp.text, marker

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    st = full["state"]
    # Real React component files.
    files = st["components"]["files"]
    assert len(files) == 3 and any(f["path"] == "src/App.jsx" for f in files)
    # Images: one per page, placeholders (no image provider), real SVG data URIs.
    assert len(st["images"]) == 2
    assert all(im["status"] == "placeholder" for im in st["images"])
    assert all(im["data_url"].startswith("data:image/svg+xml") for im in st["images"])
    # Runnable preview assembled from the actual components, compiled with the
    # classic JSX runtime and with ALL module syntax stripped (a stray
    # import/export would blank the whole page).
    prev = st["preview_html"]
    assert "<!doctype html" in prev and "@babel/standalone" in prev
    assert "runtime: 'classic'" in prev
    assert "function App()" in prev and "function Navbar()" in prev
    src = prev.split('type="text/plain">', 1)[1].split("</script>", 1)[0]
    assert "import" not in src and "export" not in src

    # Artifacts: code files + images + preview.
    kinds = [a.get("kind") for a in full["artifacts"]]
    assert kinds.count("code") == 3 and kinds.count("image") == 2 and "document" in kinds
    # Project Manager tasks for the major deliverables.
    titles = [t["title"] for t in full["tasks"]]
    assert any("React components (3 files)" in t for t in titles)
    assert any("Images (2)" in t for t in titles)


def test_generated_images_when_provider_configured(client, monkeypatch):
    from app.api.v1.endpoints import workspaces
    from app.core import website_builder
    from app.ai_providers.base import ImageResult

    monkeypatch.setattr(workspaces, "get_ai_provider", lambda name=None: _BuildProvider())

    class _Img:
        async def generate_image(self, prompt, *, size="1024x1024", model=None):
            return ImageResult(b64_png="ZmFrZQ==", model="gpt-image-1", provider="fake", prompt=prompt)

    monkeypatch.setattr(website_builder, "get_image_provider", lambda: _Img())

    headers = _register_and_login(client, "wb-img@example.com")
    s = _new_ws(client, headers)
    client.post(f"{API}/workspaces/{s['id']}/website/build", json={"approved": False, "brief": "cafe"}, headers=headers)
    client.post(f"{API}/workspaces/{s['id']}/website/build", json={"approved": True}, headers=headers)

    full = client.get(f"{API}/workspaces/{s['id']}", headers=headers).json()
    imgs = full["state"]["images"]
    assert imgs and all(im["status"] == "generated" for im in imgs)
    assert all(im["data_url"].startswith("data:image/png;base64,") for im in imgs)


def test_strip_module_syntax_removes_all_module_statements():
    from app.core import website_builder as wb

    code = (
        "import React from 'react';\n"
        "import {\n  A,\n  B\n} from './x.jsx';\n"
        "import './styles.css';\n"
        "export default function App(){ return null; }\n"
        "export function Nav(){ return null; }\n"
        "const C = 1;\n"
        "export { C };\n"
        "export default App;"
    )
    out = wb._strip_module_syntax(code)
    assert "import" not in out
    assert "export" not in out
    assert "function App()" in out and "function Nav()" in out


def test_assemble_preview_is_runnable_and_module_free():
    from app.core import website_builder as wb

    files = _COMPONENTS["files"]
    imgs = [{"id": "img1", "data_url": "data:image/svg+xml;utf8,<svg/>"}]
    html = wb.assemble_preview(files, imgs)
    assert "<!doctype html" in html and "runtime: 'classic'" in html
    src = html.split('type="text/plain">', 1)[1].split("</script>", 1)[0]
    # No module syntax survives into the compiled source.
    assert "import" not in src and "export" not in src
    # Image asset is injected.
    assert "img1" in html


def test_build_rejected_for_non_web_builder(client, build_provider):
    headers = _register_and_login(client, "wb-wrong@example.com")
    s = _new_ws(client, headers)  # will change action below
    other = client.post(f"{API}/workspaces", json={"action": "logo_design"}, headers=headers).json()
    resp = client.post(f"{API}/workspaces/{other['id']}/website/build", json={"approved": False}, headers=headers)
    assert resp.status_code == 422, resp.text


def test_build_is_owner_scoped_and_company_isolated(client, build_provider):
    headers = _register_and_login(client, "wb-owner@example.com")
    a = _create_company(client, headers, "CoA")
    b = _create_company(client, headers, "CoB")
    sa = _new_ws(client, headers, a)
    client.post(f"{API}/workspaces/{sa['id']}/website/build", json={"approved": False, "brief": "cafe A"}, headers=headers)

    # Company B has no web_builder sessions with a plan.
    only_b = client.get(f"{API}/workspaces?company_id={b}&action=web_builder", headers=headers).json()
    assert all(x["company_id"] == b for x in only_b)
    assert all(x["id"] != sa["id"] for x in only_b)

    # A different user cannot build in this session.
    intruder = _register_and_login(client, "wb-intruder@example.com")
    resp = client.post(f"{API}/workspaces/{sa['id']}/website/build", json={"approved": True}, headers=intruder)
    assert resp.status_code == 404, resp.text
