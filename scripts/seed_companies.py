"""
One-off, idempotent seed script for the two real companies:

  1. Renames the existing "Primal Penni" company (created during Shopify
     recovery work) to "Primal Penni Collective" and sets its website.
  2. Creates "Greener Capitol Solutions LLC" if it doesn't already exist.
     GCS's core business IS consulting (industry="Consulting"), so
     "Consulting" is deliberately NOT one of its divisions_json tags —
     the other four (Side Hustles, Investing, Taxes, Future Ventures) are
     side lines run underneath the core consulting practice.

Safe to run more than once — both steps check for existing state first.

Run from the project root after migrating:
    python scripts/seed_companies.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models.company import Company  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

GREENER_CAPITOL_DIVISIONS = [
    "Side Hustles",
    "Investing",
    "Taxes",
    "Future Ventures",
]

PRIMAL_PENNI_WEBSITE = "https://primalpennicollective.com"


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            print("No user found — register a Jarvis account first, then re-run this script.")
            return

        # --- 1. Rename Primal Penni -> Primal Penni Collective ---
        primal_penni = (
            db.query(Company)
            .filter(Company.owner_id == user.id, Company.name == "Primal Penni")
            .first()
        )
        if primal_penni:
            primal_penni.name = "Primal Penni Collective"
            primal_penni.website = PRIMAL_PENNI_WEBSITE
            db.commit()
            print(f"Updated company: {primal_penni.name} ({primal_penni.website})")
        else:
            existing = (
                db.query(Company)
                .filter(Company.owner_id == user.id, Company.name == "Primal Penni Collective")
                .first()
            )
            if existing:
                print("Primal Penni Collective already exists — nothing to rename.")
            else:
                print("No 'Primal Penni' company found to rename — skipping.")

        # --- 2. Create Greener Capitol Solutions LLC if missing ---
        greener_capitol = (
            db.query(Company)
            .filter(Company.owner_id == user.id, Company.name == "Greener Capitol Solutions LLC")
            .first()
        )
        if greener_capitol:
            print("Greener Capitol Solutions LLC already exists — leaving it as-is.")
        else:
            from app.api.v1.endpoints.company import DEFAULT_CHECKLISTS, DEFAULT_OWNERS, DEFAULT_SECTIONS

            greener_capitol = Company(
                owner_id=user.id,
                name="Greener Capitol Solutions LLC",
                tagline="Consulting & advisory services",
                industry="Consulting",
                divisions_json=json.dumps(GREENER_CAPITOL_DIVISIONS),
                sections_json=json.dumps(DEFAULT_SECTIONS),
                owners_json=json.dumps(DEFAULT_OWNERS),
                checklists_json=json.dumps(DEFAULT_CHECKLISTS),
            )
            db.add(greener_capitol)
            db.commit()
            print(f"Created company: {greener_capitol.name} — divisions: {', '.join(GREENER_CAPITOL_DIVISIONS)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
