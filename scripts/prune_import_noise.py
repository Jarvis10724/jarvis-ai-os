"""
Remove the noise the first import pass swept in.

The first run had two bugs: it matched "sign" inside "sign-in", turning every
Shopify login alert into a fake signature request, and it imported platform
chatter (security notices, marketing blasts) as business information. Both are
fixed in workspace_import_service; this clears what the buggy pass already
wrote so the knowledge base isn't polluted by it.

Only touches rows this importer created (source LIKE 'import:%' and tasks whose
description carries the importer's marker). Nothing a human wrote is examined,
let alone removed.

    ./.venv/bin/python scripts/prune_import_noise.py [--apply]

Without --apply it prints what it would remove and changes nothing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text  # noqa: E402

import app.db.models  # noqa: E402,F401
from app.core.workspace_import_service import flag_attention, is_relevant_email  # noqa: E402
from app.db.models.memory import MemoryEntry  # noqa: E402
from app.db.models.task import Task  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main(apply: bool) -> int:
    db = SessionLocal()
    company_id = db.execute(
        text("SELECT id FROM companies WHERE name = 'SPN Group LLC'")
    ).scalar()
    if not company_id:
        print("SPN Group LLC not found — nothing done.")
        return 1

    drop_entries, drop_tasks = [], []

    for entry in (
        db.query(MemoryEntry)
        .filter(MemoryEntry.company_id == company_id, MemoryEntry.source == "import:gmail")
        .all()
    ):
        # Rebuild the decision from what was stored about the message.
        extra = json.loads(entry.extra_json) if entry.extra_json else {}
        sender = extra.get("from", "")
        snippet = ""
        for line in (entry.content or "").splitlines():
            if line.startswith("Snippet: "):
                snippet = line[len("Snippet: "):]
        if not is_relevant_email(sender, entry.title, snippet):
            drop_entries.append(entry)

    for task in (
        db.query(Task)
        .filter(Task.company_id == company_id, Task.description.like("%Flagged from%"))
        .all()
    ):
        # Keep only flags the corrected rules still raise.
        subject = task.title.split(": ", 1)[-1]
        if flag_attention(subject) is None:
            drop_tasks.append(task)

    print(f"Imported Gmail entries that are NOT business information: {len(drop_entries)}")
    for e in drop_entries[:8]:
        print(f"   - {e.title[:74]}")
    print(f"\nSuggested tasks the corrected rules no longer raise: {len(drop_tasks)}")
    for t in drop_tasks[:8]:
        print(f"   - {t.title[:74]}")

    if not apply:
        print("\n(dry run — pass --apply to remove)")
        return 0

    for e in drop_entries:
        db.delete(e)
    for t in drop_tasks:
        db.delete(t)
    db.commit()

    remaining = (
        db.query(MemoryEntry)
        .filter(MemoryEntry.company_id == company_id, MemoryEntry.source.like("import:%"))
        .count()
    )
    kept_tasks = (
        db.query(Task)
        .filter(Task.company_id == company_id, Task.description.like("%Flagged from%"))
        .count()
    )
    print(f"\nRemoved. Knowledge base now holds {remaining} imported items; "
          f"{kept_tasks} flagged task(s) remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
