from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.js_inspector.models import JsFile
from app.js_inspector.schemas import AnalyzeJsPayload, JsFileOut
from app.js_inspector.service import ScopeBlockedError, fetch_and_analyze_js
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/js", tags=["js_inspector"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/analyze", response_model=JsFileOut, status_code=201)
async def analyze_js(project_id: int, payload: AnalyzeJsPayload, db: Session = Depends(get_db)) -> JsFile:
    project = _get_project_or_404(db, project_id)
    try:
        return await fetch_and_analyze_js(db, project, payload.url)
    except ScopeBlockedError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Vajra ScopeGuard blocked this request ({exc.decision.value}): {exc.reason}",
        ) from exc


@router.get("/files", response_model=list[JsFileOut])
def list_js_files(project_id: int, db: Session = Depends(get_db)) -> list[JsFile]:
    _get_project_or_404(db, project_id)
    return (
        db.query(JsFile)
        .filter(JsFile.project_id == project_id)
        .order_by(JsFile.fetched_at.desc())
        .limit(100)
        .all()
    )


@router.get("/files/{file_id}", response_model=JsFileOut)
def get_js_file(project_id: int, file_id: int, db: Session = Depends(get_db)) -> JsFile:
    _get_project_or_404(db, project_id)
    js_file = db.get(JsFile, file_id)
    if js_file is None or js_file.project_id != project_id:
        raise HTTPException(status_code=404, detail="JS file not found")
    return js_file
