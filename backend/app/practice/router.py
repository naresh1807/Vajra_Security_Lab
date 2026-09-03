from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from app.practice import labs
from app.practice.schemas import LabOut

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _to_lab_out(lab: labs.LabInfo) -> LabOut:
    return LabOut(
        id=lab.id,
        title=lab.title,
        concept_category=lab.concept_category,
        mini_lesson_title=lab.mini_lesson_title,
        mini_lesson=lab.mini_lesson,
        try_it_steps=lab.try_it_steps,
        base_path=f"/api/practice/{lab.id}",
        title_te=lab.title_te,
        mini_lesson_title_te=lab.mini_lesson_title_te,
        mini_lesson_te=lab.mini_lesson_te,
        try_it_steps_te=lab.try_it_steps_te,
    )


@router.get("/labs", response_model=list[LabOut])
def list_labs() -> list[LabOut]:
    return [_to_lab_out(lab) for lab in labs.CATALOG]


@router.get("/labs/{lab_id}", response_model=LabOut)
def get_lab(lab_id: str) -> LabOut:
    lab = labs.CATALOG_BY_ID.get(lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Practice lab not found")
    return _to_lab_out(lab)


# --- IDOR / BOLA lab --------------------------------------------------------


@router.get("/idor/orders/{order_id}")
def idor_get_order(order_id: int, authorization: str = Header(default="")) -> dict:
    identity = labs.resolve_practice_identity(authorization)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid or missing practice token. Send 'Authorization: Bearer practice-token-alice' "
                "or 'Authorization: Bearer practice-token-bob'."
            ),
        )
    order = labs.get_fake_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    # Deliberately vulnerable: no check that order["owner"] == identity - that
    # missing check is the concept this lab exists to teach.
    return order


# --- CORS lab ----------------------------------------------------------------


@router.get("/cors/me")
def cors_me(request: Request, x_practice_origin: str | None = Header(default=None)) -> JSONResponse:
    # Browsers prevent frontend JavaScript from forging the Origin header.
    # X-Practice-Origin is therefore a lab-only input that lets the local UI
    # demonstrate the same vulnerable reflection behavior. curl/proxy users
    # can continue to send a real Origin header.
    origin = x_practice_origin or request.headers.get("origin", "*")
    return JSONResponse(
        {"user": "practice-user", "note": "This endpoint reflects your Origin header with credentials allowed."},
        headers={"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"},
    )


# --- Insecure cookie lab ------------------------------------------------------


@router.get("/cookies/login")
def cookie_login() -> Response:
    return Response(
        content='{"message": "Logged in (practice) - check the Set-Cookie header for missing flags."}',
        media_type="application/json",
        headers={"Set-Cookie": labs.INSECURE_COOKIE_HEADER},
    )


# --- Missing security headers lab --------------------------------------------


@router.get("/headers/plain")
def headers_plain() -> dict:
    return {"message": "This response has no security headers set."}


@router.get("/headers/hardened")
def headers_hardened() -> JSONResponse:
    return JSONResponse({"message": "This response has all five security headers set."}, headers=labs.HARDENED_SECURITY_HEADERS)


# --- Information exposure lab -------------------------------------------------


@router.get("/errors/crash")
def errors_crash() -> PlainTextResponse:
    return PlainTextResponse(labs.FAKE_STACK_TRACE, status_code=500)
