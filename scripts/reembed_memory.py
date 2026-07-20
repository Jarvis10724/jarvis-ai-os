"""
Re-embeds every memory entry for every user with whatever embedding method
is currently active (see app.core.embeddings). Run this once after adding
OPENAI_API_KEY to .env for the first time — existing memory entries were
embedded with the dependency-free local fallback and won't compare well
against new OpenAI-embedded entries until they're upgraded.

Safe to run any time; it's just a refresh, not a one-way migration.

Run from the project root:
    python scripts/reembed_memory.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.memory_service import reembed_all  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


async def main() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("No users found.")
            return
        total = 0
        for user in users:
            count = await reembed_all(db, owner_id=user.id)
            print(f"Re-embedded {count} memory entries for {user.email}")
            total += count
        print(f"Done. {total} entries re-embedded total.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
