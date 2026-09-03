from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.middleware import AuthenticationMiddleware
from app.auth.router import router as auth_router

from app.analyzer.router import router as analyzer_router
from app.api_mapper.router import router as api_mapper_router
from app.authflow.router import router as authflow_router
from app.copilot.router import router as copilot_router
from app.core.config import settings
from app.core.database import database_health, migrate_database
from app.core.encryption import encryption_health
from app.core.jobs import queue_health
from app.diff.router import router as diff_router
from app.evidence.router import router as evidence_router
from app.http.router import router as http_router
from app.history.router import router as history_router
from app.identities.router import router as identities_router
from app.investigations.router import router as investigations_router
from app.js_inspector.router import router as js_inspector_router
from app.parameters.router import router as parameters_router
from app.practice.router import router as practice_router
from app.projects.router import router as projects_router
from app.recon.router import router as recon_router
from app.reports.router import router as reports_router
from app.scopeguard.router import router as scopeguard_router
from app.skills.router import router as skills_router
from app.surface.router import router as surface_router
from app.workbench.router import router as workbench_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_database()
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-assisted professional bug bounty hunting workstation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthenticationMiddleware)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    queue = queue_health()
    database = database_health()
    encryption = encryption_health()
    healthy = queue.get("available") and database.get("reachable") and database.get("migrations") == "up_to_date" and encryption.get("ready")
    return {
        "status": "ok" if healthy else "degraded",
        "app": settings.app_name,
        "queue": queue,
        "database": database,
        "encryption": encryption,
    }


app.include_router(projects_router)
app.include_router(auth_router)
app.include_router(scopeguard_router)
app.include_router(surface_router)
app.include_router(recon_router)
app.include_router(http_router)
app.include_router(history_router)
app.include_router(identities_router)
app.include_router(js_inspector_router)
app.include_router(api_mapper_router)
app.include_router(parameters_router)
app.include_router(analyzer_router)
app.include_router(authflow_router)
app.include_router(diff_router)
app.include_router(workbench_router)
app.include_router(investigations_router)
app.include_router(evidence_router)
app.include_router(reports_router)
app.include_router(practice_router)
app.include_router(copilot_router)
app.include_router(skills_router)


# Optional: serve the built frontend at `/` so the desktop app runs the UI
# and API on one origin. Mounted last, so every `/api/*` route above wins.
if settings.static_dir:
    from pathlib import Path

    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.staticfiles import StaticFiles

    _static_root = Path(settings.static_dir).expanduser().resolve()
    if _static_root.is_dir():

        class _SPAStaticFiles(StaticFiles):
            """Serve index.html for client-side routes (e.g. /projects/5)."""

            async def get_response(self, path: str, scope):  # type: ignore[override]
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if exc.status_code == 404:
                        return await super().get_response("index.html", scope)
                    raise

        app.mount("/", _SPAStaticFiles(directory=str(_static_root), html=True), name="spa")
