from __future__ import annotations

import hmac
import re
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth.models import UserSession
from app.auth.security import token_hash
from app.core.config import settings
from app.core.database import SessionLocal
from app.projects.models import Project

PROJECT_PATH = re.compile(r"^/api/projects/(\d+)(?:/|$)")
PUBLIC_PREFIXES = ("/api/health", "/api/auth/login", "/api/auth/register", "/api/practice")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith("/api") or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        raw_token = request.cookies.get(settings.session_cookie_name, "")
        if not raw_token:
            return JSONResponse({"detail": "Authentication required."}, status_code=401)

        with SessionLocal() as db:
            session = db.query(UserSession).filter(UserSession.token_hash == token_hash(raw_token)).first()
            now = datetime.now(timezone.utc)
            if session is None or session.expires_at.replace(tzinfo=timezone.utc) <= now:
                if session is not None:
                    db.delete(session)
                    db.commit()
                return JSONResponse({"detail": "Session expired or invalid."}, status_code=401)

            if request.method not in SAFE_METHODS:
                header_token = request.headers.get("x-csrf-token", "")
                cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
                if not header_token or not hmac.compare_digest(header_token, cookie_token) or not hmac.compare_digest(header_token, session.csrf_token):
                    return JSONResponse({"detail": "CSRF validation failed."}, status_code=403)

            project_match = PROJECT_PATH.match(path)
            if project_match:
                project = db.get(Project, int(project_match.group(1)))
                if project is None or project.owner_id != session.user_id:
                    return JSONResponse({"detail": "Project not found."}, status_code=404)

            request.state.user_id = session.user_id
            request.state.session_id = session.id
            last_seen = session.last_seen_at.replace(tzinfo=timezone.utc)
            if now - last_seen >= timedelta(minutes=5):
                session.last_seen_at = now
                db.commit()
        return await call_next(request)
