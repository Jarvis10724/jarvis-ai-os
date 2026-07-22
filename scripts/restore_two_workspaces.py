"""
Restore the two top-level workspaces to one workspace selector.

Both companies already exist and neither is nested inside the other. The reason
only one shows up is simpler: they are owned by two different LOGIN accounts,
and the switcher lists the companies belonging to whoever is logged in.

So this re-points ownership of the SPN Group LLC workspace to the primary
account (nickdan287@), which already owns Greener Capitol Solutions LLC. That's
all it does:

  * every row keeps its id, its company_id, and its contents,
  * no rows are created, deleted, merged, or copied between companies,
  * the two workspaces stay completely separate — each keeps its own Gmail and
    Calendar connections, memory, documents, projects, tasks, Brand Brain,
    Shopify connection, inventory, approvals and integrations, because all of
    those are scoped by company_id, which this does not touch.

Run from the repo root:  ./.venv/bin/python scripts/restore_two_workspaces.py
Back up data/jarvis.db first. Prints a before/after table and exits non-zero if
any count moved.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text  # noqa: E402

import app.db.models  # noqa: E402,F401  (registers every table)
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

PRIMARY_EMAIL = "nickdan287@gmail.com"
MOVING_EMAIL = "hello@primalpennicollective.com"
MOVING_COMPANY_NAME = "SPN Group LLC"
KEEP_COMPANY_NAME = "Greener Capitol Solutions LLC"


def main() -> int:
    db = SessionLocal()
    primary = db.execute(text("SELECT id FROM users WHERE email=:e"), {"e": PRIMARY_EMAIL}).scalar()
    previous = db.execute(text("SELECT id FROM users WHERE email=:e"), {"e": MOVING_EMAIL}).scalar()
    moving = db.execute(text("SELECT id FROM companies WHERE name=:n"), {"n": MOVING_COMPANY_NAME}).scalar()
    keeping = db.execute(text("SELECT id FROM companies WHERE name=:n"), {"n": KEEP_COMPANY_NAME}).scalar()
    if not all([primary, previous, moving, keeping]):
        print("Could not resolve both accounts and both companies — nothing changed.")
        return 1

    tables = [t for t in Base.metadata.sorted_tables if "company_id" in t.c and "owner_id" in t.c]

    def counts(company_id):
        return {t.name: db.execute(
            text(f"SELECT COUNT(*) FROM {t.name} WHERE company_id=:c"), {"c": company_id}
        ).scalar() for t in tables}

    moving_before, keeping_before = counts(moving), counts(keeping)

    # Ownership only. company_id is deliberately never touched, so no data
    # crosses between the two workspaces.
    db.execute(text("UPDATE companies SET owner_id=:p WHERE id=:c"), {"p": primary, "c": moving})
    for t in tables:
        db.execute(
            text(f"UPDATE {t.name} SET owner_id=:p WHERE company_id=:c AND owner_id=:o"),
            {"p": primary, "c": moving, "o": previous},
        )
    # Neither workspace sits inside the other — both are top level.
    db.execute(text("UPDATE companies SET parent_company_id=NULL WHERE id IN (:a,:b)"),
               {"a": moving, "b": keeping})
    db.commit()

    moving_after, keeping_after = counts(moving), counts(keeping)
    stranded = {t.name: db.execute(
        text(f"SELECT COUNT(*) FROM {t.name} WHERE company_id=:c AND owner_id=:o"),
        {"c": moving, "o": previous},
    ).scalar() for t in tables}

    print("RESTORE VERIFICATION — ownership re-pointed; nothing merged, created, or deleted\n")
    print(f"{'table':24} {'SPN before':>10} {'SPN after':>10} {'GCS before':>11} {'GCS after':>10}   ok")
    ok = True
    for t in tables:
        n = t.name
        row_ok = (moving_before[n] == moving_after[n]
                  and keeping_before[n] == keeping_after[n]
                  and stranded[n] == 0)
        ok &= row_ok
        print(f"{n:24} {moving_before[n]:>10} {moving_after[n]:>10} "
              f"{keeping_before[n]:>11} {keeping_after[n]:>10}   {'YES' if row_ok else 'NO'}")

    print(f"\nEvery count unchanged on both sides: {ok}")
    print("\nWorkspaces per login now:")
    for row in db.execute(text(
        "SELECT u.email, c.name, c.company_type, c.parent_company_id "
        "FROM companies c JOIN users u ON u.id=c.owner_id "
        "WHERE u.email IN (:a,:b) ORDER BY u.email, c.name"
    ), {"a": PRIMARY_EMAIL, "b": MOVING_EMAIL}).fetchall():
        print(f"   {row[0]:34} -> {row[1]:32} ({row[2]}) parent={row[3]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
