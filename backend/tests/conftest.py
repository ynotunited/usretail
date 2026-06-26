import sys
from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AUTH_DISABLED", "true")

from app.main import app
from app.auth.dependencies import get_current_user


class _FakeCursor:
    def __init__(self):
        self.description = []
        self._rows = []
        self._count = 0

    def execute(self, query, params=None):
        text = " ".join(query.split()).lower()
        if "count(*)" in text and "from analysis_runs" in text:
            self.description = [("count",)]
            self._rows = []
            self._count = 0
        elif "count(*)" in text and "from audit_log" in text:
            self.description = [("count",)]
            self._rows = []
            self._count = 0
        elif "from analysis_runs" in text:
            self.description = [
                ("id",), ("analyst_id",), ("city_name",), ("run_status",),
                ("partial_reason",), ("error_message",), ("started_at",),
                ("completed_at",), ("created_at",), ("weights",), ("dataset_snapshot",),
            ]
            self._rows = []
            self._count = 0
        elif "from audit_log" in text:
            self.description = [
                ("id",), ("event_type",), ("entity_type",), ("entity_id",),
                ("actor_id",), ("payload",), ("ip_address",), ("created_at",),
            ]
            self._rows = []
            self._count = 0
        else:
            self.description = []
            self._rows = []
            self._count = 0

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        if self.description and self.description[0][0] == "count":
            return (self._count,)
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def cursor(self):
        return _FakeCursor()

    def commit(self):
        return None

    def rollback(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(scope="session")
def client():
    import app.main as main_mod
    import app.api.analyses as analyses_mod
    import app.api.audit as audit_mod
    from datetime import datetime, timezone
    from types import SimpleNamespace

    def fake_run_analysis(**kwargs):
        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            run_id="00000000-0000-0000-0000-000000000001",
            status="complete",
            sites=[],
            dataset_snapshot={},
            weights=kwargs.get("weights", {}),
            analyst_id=kwargs.get("analyst_id", "system"),
            city_name=kwargs.get("city_name", "Austin"),
            started_at=now,
            completed_at=now,
            partial_reason=None,
        )

    main_mod.init_pool = lambda: None
    main_mod.close_pool = lambda: None
    analyses_mod.get_conn = lambda: _FakeConn()
    audit_mod.get_conn = lambda: _FakeConn()
    analyses_mod.run_analysis = fake_run_analysis
    app.dependency_overrides[get_current_user] = lambda: {"username": "dev-admin", "role": "admin"}

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
