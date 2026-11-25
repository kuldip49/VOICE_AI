import os
import sys
import tempfile
from pathlib import Path

# Isolated test database + deterministic demo mode BEFORE the app is imported.
_TMP = tempfile.mkdtemp(prefix="salespilot-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ADMIN_API_KEY"] = ""
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import reset_rate_limits  # noqa: E402
from app.seed import seed_knowledge  # noqa: E402
from app.services import llm, rag  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rag.invalidate_index()
    seed_knowledge(force=True)
    llm.set_provider_override("demo")
    reset_rate_limits()
    yield
    llm.set_provider_override(None)
    get_settings.cache_clear()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def say(client, cid, text):
    r = client.post(f"/api/conversations/{cid}/messages", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def start(client, language="en", **kw):
    r = client.post("/api/conversations", json={"language": language, "channel": "voice", **kw})
    assert r.status_code == 200, r.text
    return r.json()
