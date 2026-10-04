import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets its own throwaway SQLite file — never touches app.db."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    # config too, so anything calling init_db() without a URL (e.g. the API's
    # startup) stays on the throwaway database.
    monkeypatch.setattr(config, "DATABASE_URL", url)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_SessionLocal", None)
    db.init_db(url)
    yield
    db._engine.dispose()
