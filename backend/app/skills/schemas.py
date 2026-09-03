from pydantic import BaseModel


class SkillSignalOut(BaseModel):
    label: str
    count: int
    points: int


class SkillOut(BaseModel):
    key: str
    label: str
    blurb: str
    score: int
    level: int
    band: str
    signals: list[SkillSignalOut]
    next_step: str


class SkillActivity(BaseModel):
    projects: int
    recon_jobs: int
    http_requests: int
    endpoint_shapes: int
    js_files: int
    investigations: int
    findings: int
    reports: int
    evidence_files: int
    labs_completed: int


class SkillMapOut(BaseModel):
    skills: list[SkillOut]
    activity: SkillActivity
    strengths: list[str]
    growth_areas: list[str]
    headline: str
    note: str
