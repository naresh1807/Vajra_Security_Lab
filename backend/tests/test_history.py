from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.history.service import build_hunt_history
from app.http.models import HttpTransaction
from app.investigations.models import Investigation
from app.js_inspector.models import JsFile
from app.recon.models import Asset, ReconJob, ReconJobStatus, ReconStage
from app.scopeguard.models import ScopeAuditLog, ScopeDecision


class _Query(list):
    def filter(self, *args):
        return self

    def all(self):
        return list(self)


class _Session:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return _Query(self.rows.get(model, []))


def test_history_is_sorted_and_filterable():
    now = datetime.now(timezone.utc)
    scope = SimpleNamespace(id=1, decision=ScopeDecision.ALLOWED, operation="manual_check", normalized_target="api.example.com", target_input="api.example.com", reason="in scope", created_at=now)
    recon = SimpleNamespace(id=2, stage=ReconStage.DONE, error=None, status=ReconJobStatus.COMPLETED, started_at=now, completed_at=now + timedelta(minutes=1))
    session = _Session({ScopeAuditLog: [scope], ReconJob: [recon], Asset: [], HttpTransaction: [], JsFile: [], Investigation: []})

    result = build_hunt_history(session, 1, None, 100, 0)
    assert [event.category for event in result.events] == ["recon", "scope"]
    assert result.categories == {"recon": 1, "scope": 1}

    filtered = build_hunt_history(session, 1, "scope", 100, 0)
    assert filtered.total == 1
    assert filtered.events[0].status == "allowed"


def test_history_limit_and_offset_apply_after_sorting():
    now = datetime.now(timezone.utc)
    rows = [SimpleNamespace(id=i, decision=ScopeDecision.BLOCKED, operation="http", normalized_target=f"{i}.example.com", target_input="", reason="blocked", created_at=now + timedelta(seconds=i)) for i in range(3)]
    session = _Session({ScopeAuditLog: rows, ReconJob: [], Asset: [], HttpTransaction: [], JsFile: [], Investigation: []})
    result = build_hunt_history(session, 1, None, 1, 1)
    assert result.total == 3
    assert result.events[0].id == "scope-1"
