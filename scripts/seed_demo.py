"""
Idempotent demo seed for the Thursday Yacht Workshop demo.

Creates a self-contained, clearly-labeled DEMO workspace under a dedicated demo
login — it never touches production data, never connects Shopify, and never
sends email (registration only stores a local hashed password).

  Login:    hello@primalpennicollective.com  /  <DEMO_PASSWORD below>
  Company:  SNP Group LLC   (first DBA: "Primal Penni")
  Projects: "Primal Penni Product Landing Page"  <- reliable, completed build
            + a couple more so active-project switching is demonstrable
  Plus:     realistic products, AI memories, a company Daily Brief, an approved
            approval record, and project timeline events.

Safe to run repeatedly — every step checks for existing state first.

Run from the repo root (see the DB cwd gotcha) after migrating:
    python scripts/seed_demo.py
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth.security import hash_password  # noqa: E402
from app.core import project_service  # noqa: E402
from app.db.models.capability import ApprovalRequest  # noqa: E402
from app.db.models.company import Company, Product  # noqa: E402
from app.db.models.memory import MemoryEntry  # noqa: E402
from app.db.models.project import Project  # noqa: E402
from app.db.models.task import Task  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.models.workspace_session import WorkspaceSession  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

DEMO_EMAIL = "hello@primalpennicollective.com"
DEMO_PASSWORD = "changeme-demo-password"
COMPANY_NAME = "SNP Group LLC"
DBA = "Primal Penni"
SHOWCASE_PROJECT = "Primal Penni Product Landing Page"

# --- The completed website-build state the Studio panels + preview render -----

PREVIEW_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Primal Penni — Copper Glow Serum</title>
<style>
:root{--ink:#2b2118;--paper:#faf5ee;--copper:#b06a3b;--copper-dk:#8a4f28;--sage:#6f7d5f;--muted:#7a6f63}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Georgia',serif;color:var(--ink);background:var(--paper);line-height:1.6}
.wrap{max-width:1000px;margin:0 auto;padding:0 24px}
header{display:flex;justify-content:space-between;align-items:center;padding:22px 24px;max-width:1000px;margin:0 auto}
.brand{font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:15px;color:var(--copper-dk)}
nav a{margin-left:22px;color:var(--muted);text-decoration:none;font-size:14px}
.hero{text-align:center;padding:72px 24px 64px;background:radial-gradient(120% 90% at 50% 0,#f3e3d3 0,var(--paper) 60%)}
.hero h1{font-size:46px;line-height:1.1;margin-bottom:14px}
.hero p{max-width:560px;margin:0 auto 26px;color:var(--muted);font-size:18px}
.btn{display:inline-block;background:var(--copper);color:#fff;padding:14px 30px;border-radius:999px;text-decoration:none;font-family:sans-serif;font-weight:600;letter-spacing:.03em;box-shadow:0 8px 24px rgba(176,106,59,.28)}
.btn:hover{background:var(--copper-dk)}
.pill{display:inline-block;font-family:sans-serif;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--sage);margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;padding:56px 0}
.card{background:#fff;border:1px solid #ece0d2;border-radius:16px;padding:24px}
.card h3{font-size:19px;margin-bottom:8px;color:var(--copper-dk)}
.card p{color:var(--muted);font-size:15px}
.product{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:center;padding:48px 0}
.shot{aspect-ratio:1;border-radius:20px;background:linear-gradient(140deg,#e8cdb3,#c98d5f);display:flex;align-items:center;justify-content:center;color:#fff;font-family:sans-serif;letter-spacing:.1em}
.quote{text-align:center;padding:56px 24px;background:#f3e3d3;font-size:22px;font-style:italic;color:var(--ink)}
.cta{text-align:center;padding:64px 24px}
footer{text-align:center;padding:28px;color:var(--muted);font-size:13px;font-family:sans-serif}
@media(max-width:720px){.grid{grid-template-columns:1fr}.product{grid-template-columns:1fr}.hero h1{font-size:34px}nav{display:none}}
</style></head><body>
<header><div class="brand">Primal Penni</div><nav><a href="#">Shop</a><a href="#">Ritual</a><a href="#">About</a><a href="#">Contact</a></nav></header>
<section class="hero"><div class="pill">Small-batch · Copper-infused</div>
<h1>Copper Glow Serum</h1>
<p>A featherlight, copper-peptide serum that revives tired skin overnight — clean, cruelty-free, and made in small batches.</p>
<a class="btn" href="#">Shop the Ritual — $48</a></section>
<div class="wrap"><section class="grid">
<div class="card"><h3>Copper Peptides</h3><p>Supports natural collagen for firmer, brighter skin by morning.</p></div>
<div class="card"><h3>Clean &amp; Kind</h3><p>Vegan, cruelty-free, and free of parabens, sulfates, and synthetic fragrance.</p></div>
<div class="card"><h3>Small-Batch</h3><p>Hand-poured in limited runs so every bottle is fresh and potent.</p></div>
</section>
<section class="product"><div class="shot">PRODUCT SHOT</div>
<div><div class="pill">The hero</div><h1 style="font-size:30px;margin-bottom:12px">Wake up to a Primal glow</h1>
<p style="color:var(--muted)">Three drops before bed. In the morning, skin looks rested, even, and lit from within. Dermatologist-tested for all skin types.</p>
<p style="margin-top:18px"><a class="btn" href="#">Add to bag</a></p></div></section></div>
<section class="quote">"The only serum that survived my whole skincare-minimalism phase." — Verified buyer</section>
<section class="cta"><div class="pill">Ready when you are</div><h1 style="font-size:32px;margin-bottom:14px">Start your evening ritual</h1>
<a class="btn" href="#">Shop Copper Glow Serum</a></section>
<footer>© Primal Penni, a DBA of SNP Group LLC · Demo preview</footer>
</body></html>"""

HERO_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='500'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='%23e8cdb3'/><stop offset='1' stop-color='%23c98d5f'/>"
    "</linearGradient></defs><rect width='800' height='500' fill='url(%23g)'/>"
    "<text x='50%25' y='50%25' fill='white' font-family='sans-serif' font-size='28' "
    "text-anchor='middle' letter-spacing='4'>PRIMAL PENNI — HERO</text></svg>"
)


def _components() -> dict:
    return {
        "files": [
            {"path": "src/App.jsx", "language": "jsx", "description": "Page shell + section composition",
             "content": "export default function App(){return <main><Hero/><Features/><Product/><CTA/></main>}"},
            {"path": "src/components/Hero.jsx", "language": "jsx", "description": "Above-the-fold hero + primary CTA",
             "content": "export function Hero(){return <section className='hero'><h1>Copper Glow Serum</h1></section>}"},
            {"path": "src/components/Features.jsx", "language": "jsx", "description": "Three product benefit cards",
             "content": "export function Features(){return <section className='features'/>}"},
            {"path": "src/components/Product.jsx", "language": "jsx", "description": "Product spotlight + add-to-bag",
             "content": "export function Product(){return <section className='product'/>}"},
            {"path": "src/components/CTA.jsx", "language": "jsx", "description": "Closing call-to-action band",
             "content": "export function CTA(){return <section className='cta'/>}"},
        ]
    }


def _build_state() -> dict:
    return {
        "mode": "new",
        "_company": "Primal Penni",
        "requirements": {
            "business": "Primal Penni — small-batch, copper-infused clean skincare (DBA of SNP Group LLC)",
            "goal": "A single-page product landing page for the Copper Glow Serum that converts.",
            "audience": "Skincare-minimalist millennials who value clean, cruelty-free products.",
            "tone": "Warm, earthy, premium.",
        },
        "sitemap": [
            {"path": "/", "title": "Copper Glow Serum", "purpose": "Convert visitors on the hero product",
             "sections": ["Hero", "Benefits", "Product spotlight", "Testimonial", "Closing CTA"]},
        ],
        "layouts": {
            "/": {"sections": [
                {"name": "Hero", "type": "hero", "description": "Full-bleed hero with product name + primary CTA"},
                {"name": "Benefits", "type": "feature-grid", "description": "Three benefit cards"},
                {"name": "Product spotlight", "type": "split", "description": "Product shot beside copy + add-to-bag"},
                {"name": "Testimonial", "type": "quote", "description": "Single verified-buyer quote band"},
                {"name": "Closing CTA", "type": "cta", "description": "Final shop CTA"},
            ]}
        },
        "copy": {
            "/": {
                "heading": "Copper Glow Serum",
                "sections": [
                    {"title": "Hero", "body": "A featherlight, copper-peptide serum that revives tired skin overnight."},
                    {"title": "Copper Peptides", "body": "Supports natural collagen for firmer, brighter skin by morning."},
                    {"title": "Clean & Kind", "body": "Vegan, cruelty-free, free of parabens, sulfates, and synthetic fragrance."},
                    {"title": "Small-Batch", "body": "Hand-poured in limited runs so every bottle is fresh and potent."},
                ],
            }
        },
        "design": {
            "palette": [
                {"name": "Copper", "hex": "#b06a3b"},
                {"name": "Copper Dark", "hex": "#8a4f28"},
                {"name": "Paper", "hex": "#faf5ee"},
                {"name": "Sage", "hex": "#6f7d5f"},
                {"name": "Ink", "hex": "#2b2118"},
            ],
            "typography": {"headings": "Georgia / serif", "body": "Georgia / serif", "ui": "system sans-serif"},
        },
        "images": [
            {"id": "img-hero", "page": "/", "role": "hero", "alt": "Copper Glow Serum hero",
             "prompt": "Warm copper-lit skincare hero", "data_url": HERO_SVG, "status": "placeholder"},
        ],
        "components": _components(),
        "preview_html": PREVIEW_HTML,
    }


def _messages() -> list[dict]:
    now = time.time()
    return [
        {"role": "user", "content": "Build a one-page product landing page for Primal Penni's Copper Glow Serum.", "ts": now - 600},
        {"role": "assistant", "content": "Planned a single-page site: hero, benefits, product spotlight, testimonial, and a closing CTA — with a warm copper/earthy palette. Review the plan and approve to generate.", "ts": now - 580},
        {"role": "assistant", "content": "Approved — generated the React components, a hero image placeholder, and a runnable preview. The finished landing page is in the Preview tab.", "ts": now - 400},
    ]


def _get_or_create(db, model, defaults=None, **filters):
    obj = db.query(model).filter_by(**filters).first()
    if obj:
        return obj, False
    obj = model(**filters, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def main() -> None:
    db = SessionLocal()
    created = []
    try:
        # 1) Demo login (no email sent — just a local hashed password).
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD), full_name="Primal Penni Collective")
            db.add(user)
            db.flush()
            created.append(f"user {DEMO_EMAIL}")

        # 2) SNP Group LLC company with Primal Penni as its first DBA.
        company = db.query(Company).filter(Company.owner_id == user.id, Company.name == COMPANY_NAME).first()
        if not company:
            company = Company(
                owner_id=user.id,
                name=COMPANY_NAME,
                tagline="Clean, small-batch consumer brands — DEMO workspace",
                industry="Consumer Goods",
                website="https://primalpennicollective.com",
                divisions_json=json.dumps([DBA]),
            )
            db.add(company)
            db.flush()
            created.append(f"company {COMPANY_NAME} (DBA {DBA})")
        else:
            divs = json.loads(company.divisions_json or "[]")
            if DBA not in divs:
                company.divisions_json = json.dumps([DBA, *divs])

        # 3) Realistic Primal Penni products.
        products = [
            {"name": "Copper Glow Serum", "sku": "PP-CGS-30", "price": 48.0, "cogs": 11.5, "inventory": 320,
             "launch_status": "launched", "notes": "DEMO — hero product for the landing page."},
            {"name": "Renewal Night Cream", "sku": "PP-RNC-50", "price": 54.0, "cogs": 13.0, "inventory": 210,
             "launch_status": "launched", "notes": "DEMO"},
            {"name": "Gentle Copper Cleanser", "sku": "PP-GCC-150", "price": 28.0, "cogs": 6.5, "inventory": 140,
             "launch_status": "ready", "notes": "DEMO"},
        ]
        for p in products:
            _, was_new = _get_or_create(db, Product, defaults={k: v for k, v in p.items() if k != "name"},
                                        company_id=company.id, name=p["name"])
            if was_new:
                created.append(f"product {p['name']}")

        # Ensure the company's default project exists.
        project_service.get_or_create_default_project(db, owner_id=user.id, company_id=company.id, commit=False)

        # 4) The showcase project — a *completed* website build.
        showcase = db.query(Project).filter(
            Project.owner_id == user.id, Project.company_id == company.id, Project.name == SHOWCASE_PROJECT
        ).first()
        if not showcase:
            showcase = Project(
                owner_id=user.id, company_id=company.id, name=SHOWCASE_PROJECT,
                description="DEMO project — completed one-page landing page for the Copper Glow Serum (Primal Penni DBA).",
                status="active",
            )
            db.add(showcase)
            db.flush()
            created.append(f"project {SHOWCASE_PROJECT}")

            # Completed web_builder session with full state + artifacts.
            state = _build_state()
            arts = [{"id": f["path"], "kind": "code", "title": f["path"], "content": f["content"],
                     "stage": "components", "version": 1, "ts": time.time()} for f in state["components"]["files"]]
            arts.append({"id": "preview", "kind": "document", "title": "Preview (index.html)",
                         "content": PREVIEW_HTML, "stage": "preview", "version": 1, "ts": time.time()})
            session = WorkspaceSession(
                owner_id=user.id, company_id=company.id, action="web_builder",
                title="Copper Glow Serum landing page", project_id=showcase.id, status="active",
                messages_json=json.dumps(_messages()),
                artifacts_json=json.dumps(arts),
                state_json=json.dumps(state),
            )
            db.add(session)
            db.flush()

            # Tasks (tagged to the Primal Penni DBA), an approved approval, timeline.
            for title, status in [("Define the Copper Glow brief", "done"),
                                  ("Plan sitemap + copy", "done"),
                                  ("Approve build (images + components + preview)", "done"),
                                  ("React components (5 files)", "review"),
                                  ("Launch on primalpennicollective.com", "backlog")]:
                db.add(Task(owner_id=user.id, company_id=company.id, project_id=showcase.id,
                            title=title, status=status, division=DBA))

            db.add(ApprovalRequest(
                owner_id=user.id, company_id=company.id, project_id=showcase.id,
                capability_name="web_builder", action_type="build_site",
                payload_json=json.dumps({"summary": "Generate images, React components, and a runnable preview.",
                                         "major_actions": ["1 hero image", "5 component files", "runnable preview"]}),
                status="approved", requested_by=user.id, decided_by=user.id,
                decided_at=datetime.now(timezone.utc),
            ))

            for kind, title, detail in [
                ("session_created", f"Started Website Studio: {SHOWCASE_PROJECT}", None),
                ("approval_decided", "Approval approved: web_builder · build_site", "Images + components + preview"),
                ("website_built", "Built 1-page site for Primal Penni", "5 component files, 1 image, runnable preview"),
            ]:
                project_service.record_project_event(
                    db, project=showcase, owner_id=user.id, kind=kind, title=title,
                    source="web_builder", detail=detail, ref_id=session.id, commit=False,
                )

        # 5) A couple more projects so active-project switching is demonstrable.
        for name, desc in [
            ("Primal Penni Brand Refresh", "DEMO project — brand palette + logo exploration for Primal Penni."),
            ("Spring Launch Campaign", "DEMO project — go-to-market plan for the spring skincare drop."),
        ]:
            proj = db.query(Project).filter(
                Project.owner_id == user.id, Project.company_id == company.id, Project.name == name
            ).first()
            if not proj:
                proj = Project(owner_id=user.id, company_id=company.id, name=name, description=desc, status="active")
                db.add(proj)
                db.flush()
                project_service.record_project_event(
                    db, project=proj, owner_id=user.id, kind="note",
                    title=f"Created {name}", source="demo", commit=False,
                )
                created.append(f"project {name}")

        # 6) Company Daily Brief (company-scoped).
        has_brief = db.query(MemoryEntry).filter(
            MemoryEntry.owner_id == user.id, MemoryEntry.company_id == company.id,
            MemoryEntry.source == "daily_briefing",
        ).first()
        if not has_brief:
            db.add(MemoryEntry(
                owner_id=user.id, company_id=company.id, scope="company", kind="fact",
                source="daily_briefing", title=f"Daily Briefing — {datetime.now(timezone.utc).date().isoformat()}",
                content=(
                    "Good morning — SNP Group LLC (Primal Penni)\n\n"
                    "• Copper Glow Serum landing page is built and ready to review in Projects → "
                    "Primal Penni Product Landing Page.\n"
                    "• Inventory healthy: Copper Glow Serum 320 units, Renewal Night Cream 210.\n"
                    "• 1 approval was completed for the website build.\n"
                    "• Next: schedule the Spring Launch Campaign and finalize the brand refresh.\n\n"
                    "(Demo workspace — no live Shopify or email connected.)"
                ),
            ))
            created.append("company daily brief")

        # 7) A few AI memories (company-scoped).
        memories = [
            ("decision", "Landing page palette locked", "Chose a warm copper/sage/paper palette for the Copper Glow Serum page."),
            ("product", "Copper Glow Serum is the hero SKU", "$48 retail, ~76% margin, 320 units on hand. Lead product for the demo."),
            ("goal", "Q2 goal: launch spring skincare drop", "Primal Penni to release the spring line with a dedicated landing page + campaign."),
        ]
        for kind, title, content in memories:
            exists = db.query(MemoryEntry).filter(
                MemoryEntry.owner_id == user.id, MemoryEntry.company_id == company.id, MemoryEntry.title == title
            ).first()
            if not exists:
                db.add(MemoryEntry(owner_id=user.id, company_id=company.id, scope="company",
                                   kind=kind, title=title, content=content, source="manual"))
                created.append(f"memory '{title}'")

        # 8) Pending approvals — so the Notification Center + Approvals page show
        #    polished, real content during the demo (labeled demo actions; none
        #    are ever executed against a live service).
        pending = [
            ("email", "send", {
                "to": "list@primalpennicollective.com",
                "subject": "Copper Glow Serum is live 🎉",
                "body": "DEMO — Announce the Copper Glow Serum launch to the newsletter.",
            }),
            ("google_calendar", "create_event", {
                "title": "Spring drop planning",
                "start": "2026-07-24T15:00:00Z",
                "notes": "DEMO — kickoff for the Spring Launch Campaign.",
            }),
        ]
        for cap, act, payload in pending:
            exists = db.query(ApprovalRequest).filter(
                ApprovalRequest.owner_id == user.id, ApprovalRequest.company_id == company.id,
                ApprovalRequest.capability_name == cap, ApprovalRequest.action_type == act,
                ApprovalRequest.status == "pending",
            ).first()
            if not exists:
                db.add(ApprovalRequest(
                    owner_id=user.id, company_id=company.id, project_id=showcase.id,
                    capability_name=cap, action_type=act,
                    payload_json=json.dumps(payload), status="pending", requested_by=user.id,
                ))
                created.append(f"pending approval {cap}·{act}")

        db.commit()
        print("Demo seed complete.")
        print(f"  Login:    {DEMO_EMAIL}  /  {DEMO_PASSWORD}")
        print(f"  Company:  {COMPANY_NAME}  (DBA: {DBA})")
        print(f"  Showcase: {SHOWCASE_PROJECT}")
        if created:
            print("  Created this run:")
            for c in created:
                print(f"    - {c}")
        else:
            print("  Nothing new — already seeded (idempotent).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
