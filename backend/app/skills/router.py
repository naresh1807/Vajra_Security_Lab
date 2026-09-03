from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.skills.schemas import SkillMapOut
from app.skills.service import build_skill_map

# User-level, not project-scoped: Section 39's "personal learning" is about
# the hunter across every project they own.
router = APIRouter(prefix="/api/skills", tags=["skill_map"])


@router.get("", response_model=SkillMapOut)
def get_skill_map(request: Request, db: Session = Depends(get_db)) -> SkillMapOut:
    return SkillMapOut(**build_skill_map(db, request.state.user_id))
