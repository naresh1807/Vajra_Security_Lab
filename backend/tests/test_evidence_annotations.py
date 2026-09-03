"""
Screenshot annotation / markup (Section 32 "Annotate").

Annotations are non-destructive shapes stored on the attachment; the
image file is only rewritten by "Flatten & replace", which clears them.
The evidence bundle flags any screenshot whose redactions aren't baked in.
"""
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base
from app.evidence.annotations import AnnotationError, validate_annotations
from app.evidence.export import build_evidence_bundle, remove_bundle
from app.evidence.service import replace_attachment_file, save_attachment, to_attachment_out, update_attachment
from app.investigations.models import Investigation
from app.projects.models import Project

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001" "0d0a2db40000000049454e44ae426082"
)


# --- validator ---------------------------------------------------------

def test_validator_normalizes_a_redact_box_and_defaults_color():
    out = validate_annotations([{"type": "redact", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.05}])
    assert out == [{"type": "redact", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.05, "color": "#f43f5e"}]


def test_validator_keeps_arrow_endpoints_and_truncates_label_text():
    out = validate_annotations([
        {"type": "arrow", "x": 0, "y": 0, "x2": 1, "y2": 1, "color": "#00aaff"},
        {"type": "label", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "text": "x" * 500},
    ])
    assert out[0]["x2"] == 1.0 and out[0]["y2"] == 1.0
    assert len(out[1]["text"]) == 200


def test_validator_rejects_bad_input():
    with pytest.raises(AnnotationError):
        validate_annotations([{"type": "scribble", "x": 0, "y": 0, "w": 0.1, "h": 0.1}])
    with pytest.raises(AnnotationError):
        validate_annotations([{"type": "redact", "x": 5, "y": 0, "w": 0.1, "h": 0.1}])
    with pytest.raises(AnnotationError):
        validate_annotations([{"type": "redact", "x": 0, "y": 0, "w": 0.1, "h": 0.1, "color": "red"}])
    with pytest.raises(AnnotationError):
        validate_annotations("nope")


# --- service ----------------------------------------------------------

@pytest.fixture
def evidence_db(monkeypatch):
    tmp = Path(__file__).resolve().parent / ".runtime" / uuid.uuid4().hex
    tmp.mkdir(parents=True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp / "uploads"))
    monkeypatch.setattr(settings, "max_evidence_export_bytes", 10 * 1024 * 1024)
    monkeypatch.setattr(settings, "max_evidence_export_attachments", 10)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            yield db
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _seed(db: Session) -> tuple[Project, Investigation]:
    project = Project(name="P", target="example.com", allowed_domains=["example.com"])
    db.add(project)
    db.commit()
    inv = Investigation(project_id=project.id, title="T", linked_transaction_ids=[])
    db.add(inv)
    db.commit()
    return project, inv


def test_update_and_flatten_lifecycle(evidence_db):
    project, inv = _seed(evidence_db)
    attachment = save_attachment(evidence_db, project.id, inv.id, "shot.png", "image/png", _PNG, "before")

    updated = update_attachment(
        evidence_db, attachment, caption="after",
        annotations=validate_annotations([{"type": "redact", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1}]),
    )
    assert updated.caption == "after"
    assert to_attachment_out(updated)["annotations"][0]["type"] == "redact"
    old_path = updated.file_path

    baked = replace_attachment_file(evidence_db, updated, "shot-flat.png", "image/png", _PNG + b"\x00")
    assert baked.annotations == []                       # markup is now in the pixels
    assert baked.filename == "shot-flat.png"
    assert not Path(old_path).exists()                   # old file cleaned up


def test_bundle_warns_about_unbaked_redactions(evidence_db):
    project, inv = _seed(evidence_db)
    attachment = save_attachment(evidence_db, project.id, inv.id, "shot.png", "image/png", _PNG, "cap")
    update_attachment(
        evidence_db, attachment,
        annotations=validate_annotations([{"type": "redact", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.1}]),
    )

    artifact = build_evidence_bundle(evidence_db, project, inv)
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            manifest = archive.read("manifest.json").decode()
    finally:
        remove_bundle(artifact.path)

    assert '"has_unbaked_annotations": true' in manifest
    assert "NOT baked into the exported image file" in manifest
    assert "1 redaction box" in manifest
