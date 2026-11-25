"""Database initialisation + seed data (sample TechNova Academy knowledge base).

Run:  python -m app.seed            (creates tables, loads KB if empty)
      python -m app.seed --reset    (DELETES the database file first)
"""
import sys
from pathlib import Path

from sqlalchemy import func, select

from .config import DATA_DIR, get_settings
from .database import Base, SessionLocal, engine
from .models import KnowledgeDocument
from .services import rag

KB_DIR = DATA_DIR / "knowledge"


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def seed_knowledge(force: bool = False) -> int:
    with SessionLocal() as db:
        count = db.execute(select(func.count(KnowledgeDocument.id))).scalar_one()
        if count and not force:
            return 0
        n = 0
        for path in sorted(KB_DIR.glob("*.txt")):
            rag.ingest_document(db, path.name, "text/plain", path.read_bytes())
            n += 1
        return n


def main() -> None:
    if "--reset" in sys.argv:
        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            p = Path(url.replace("sqlite:///", ""))
            for suffix in ("", "-wal", "-shm"):
                q = Path(str(p) + suffix)
                if q.exists():
                    q.unlink()
            print(f"Deleted {p}")
    init_db()
    n = seed_knowledge()
    print(f"Database ready. Loaded {n} knowledge documents.")


if __name__ == "__main__":
    main()
