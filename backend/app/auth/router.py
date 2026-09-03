from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.auth.models import AuthEvent, User, UserSession
from app.auth.schemas import AuthEventOut, Credentials, SessionOut, UserOut
from app.auth.security import hash_password, new_token, token_hash, verify_password
from app.core.config import settings
from app.core.database import get_db
from app.projects.models import Project

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = settings.session_lifetime_hours * 3600
    response.set_cookie(
        settings.session_cookie_name, session_token, max_age=max_age, httponly=True,
        secure=settings.secure_cookies, samesite="strict", path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name, csrf_token, max_age=max_age, httponly=False,
        secure=settings.secure_cookies, samesite="strict", path="/",
    )


def _client_ip(request: Request) -> str:
    return request.client.host[:64] if request.client else ""


def _record_event(db: Session, request: Request, event_type: str, success: bool, email: str = "", user_id: int | None = None) -> None:
    db.add(AuthEvent(
        user_id=user_id, email=email[:320], event_type=event_type, success=success,
        ip_address=_client_ip(request),
    ))


def _create_session(db: Session, user: User, response: Response, request: Request) -> None:
    raw_token, csrf_token = new_token(), new_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_lifetime_hours)
    db.add(UserSession(
        user_id=user.id, token_hash=token_hash(raw_token), csrf_token=csrf_token, expires_at=expires,
        ip_address=_client_ip(request), user_agent=request.headers.get("user-agent", "")[:500],
    ))
    db.commit()
    _set_cookies(response, raw_token, csrf_token)


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: Credentials, response: Response, request: Request, db: Session = Depends(get_db)) -> User:
    email = payload.email.lower().strip()
    if not settings.allow_registration and db.query(User.id).first() is not None:
        raise HTTPException(status_code=403, detail="New account registration is disabled.")
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    # Preserve local pre-auth installations: the first account claims only
    # legacy projects that have no owner, never another user's projects.
    db.query(Project).filter(Project.owner_id.is_(None)).update({Project.owner_id: user.id}, synchronize_session=False)
    db.commit()
    db.refresh(user)
    _record_event(db, request, "register", True, email=email, user_id=user.id)
    db.commit()
    _create_session(db, user, response, request)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: Credentials, response: Response, request: Request, db: Session = Depends(get_db)) -> User:
    email = payload.email.lower().strip()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.login_attempt_window_minutes)
    recent_failures = db.query(AuthEvent).filter(
        AuthEvent.event_type == "login", AuthEvent.success.is_(False), AuthEvent.email == email,
        AuthEvent.ip_address == _client_ip(request), AuthEvent.created_at >= cutoff,
    ).count()
    if recent_failures >= settings.login_attempt_limit:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        _record_event(db, request, "login", False, email=email, user_id=user.id if user else None)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _record_event(db, request, "login", True, email=email, user_id=user.id)
    db.commit()
    _create_session(db, user, response, request)
    return user


@router.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)) -> User:
    user = db.get(User, request.state.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    session = db.get(UserSession, request.state.session_id)
    if session is not None:
        _record_event(db, request, "logout", True, user_id=session.user_id)
        db.delete(session)
        db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(request: Request, db: Session = Depends(get_db)) -> list[SessionOut]:
    sessions = db.query(UserSession).filter(UserSession.user_id == request.state.user_id).order_by(UserSession.last_seen_at.desc()).all()
    return [SessionOut(
        id=item.id, created_at=item.created_at, last_seen_at=item.last_seen_at, expires_at=item.expires_at,
        ip_address=item.ip_address, user_agent=item.user_agent, current=item.id == request.state.session_id,
    ) for item in sessions]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: int, request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != request.state.user_id:
        raise HTTPException(status_code=404, detail="Session not found.")
    current = session.id == request.state.session_id
    _record_event(db, request, "session_revoked", True, user_id=session.user_id)
    db.delete(session); db.commit()
    if current:
        response.delete_cookie(settings.session_cookie_name, path="/")
        response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.get("/events", response_model=list[AuthEventOut])
def list_auth_events(request: Request, db: Session = Depends(get_db)) -> list[AuthEvent]:
    return db.query(AuthEvent).filter(AuthEvent.user_id == request.state.user_id).order_by(AuthEvent.created_at.desc()).limit(50).all()
