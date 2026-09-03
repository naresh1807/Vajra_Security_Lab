"""
Vajra Practice Bridge (Sections 29-30) - real, self-contained, deliberately
vulnerable practice endpoints, not scripted/canned responses. They run
in-process against fixed in-memory fake data, never touch a network, and
are entirely separate from any real target or project scope - there is
nothing here for ScopeGuard to gate because nothing here is a real target.

Scope decision, stated honestly: the spec's tech stack (Section 46) lists
Docker for labs, implying real isolated containers per concept. This
build has no container orchestration, so "isolated lab" means an
in-process fake data set instead of a separate sandboxed service. The
vulnerability itself is still genuine and independently reproducible
through the same HTTP mechanics as a real target - only the deployment
model is simplified.

Pure logic lives here (unit-testable without spinning up FastAPI);
`router.py` only wires HTTP onto it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- IDOR / BOLA lab -------------------------------------------------------

FAKE_ORDERS: dict[int, dict] = {
    1: {"id": 1, "owner": "alice", "item": "Laptop", "total": 1200},
    2: {"id": 2, "owner": "alice", "item": "Mouse", "total": 25},
    3: {"id": 3, "owner": "bob", "item": "Keyboard", "total": 75},
    4: {"id": 4, "owner": "bob", "item": "Monitor", "total": 300},
}

FAKE_TOKENS: dict[str, str] = {
    "practice-token-alice": "alice",
    "practice-token-bob": "bob",
}


def resolve_practice_identity(authorization_header: str) -> str | None:
    token = authorization_header.removeprefix("Bearer ").strip()
    return FAKE_TOKENS.get(token)


def get_fake_order(order_id: int) -> dict | None:
    """Deliberately vulnerable: the caller of this function is expected to
    NOT check that the order belongs to the resolved identity - that
    missing check is the concept being practiced. See router.py."""
    return FAKE_ORDERS.get(order_id)


# --- Insecure cookie lab ----------------------------------------------------

INSECURE_COOKIE_HEADER = "practice_session=insecure-demo-value; Path=/"


# --- Missing security headers lab ------------------------------------------

HARDENED_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": "default-src 'self'",
    "Strict-Transport-Security": "max-age=63072000",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


# --- Information exposure lab -----------------------------------------------

FAKE_STACK_TRACE = (
    "Traceback (most recent call last):\n"
    '  File "/srv/app/orders/views.py", line 142, in get_order\n'
    "    order = Order.objects.get(pk=order_id)\n"
    "django.db.utils.OperationalError: could not connect to server: "
    "Connection refused\n"
    "  Is the server running on host \"db-primary.internal\" (10.0.4.12) and accepting\n"
    "  TCP/IP connections on port 5432?"
)


@dataclass
class LabInfo:
    id: str
    title: str
    concept_category: str
    mini_lesson_title: str
    mini_lesson: str
    try_it_steps: list[str] = field(default_factory=list)
    title_te: str = ""
    mini_lesson_title_te: str = ""
    mini_lesson_te: str = ""
    try_it_steps_te: list[str] = field(default_factory=list)


CATALOG: list[LabInfo] = [
    LabInfo(
        id="idor",
        title="Broken Object Level Authorization (IDOR)",
        concept_category="api",
        mini_lesson_title="60-second concept: BOLA / IDOR",
        mini_lesson=(
            "A Broken Object Level Authorization (IDOR is the classic case) occurs when an API exposes "
            "an object identifier and fails to verify the current caller is actually authorized to "
            "access that specific object."
        ),
        try_it_steps=[
            "Send GET /api/practice/idor/orders/1 with header Authorization: Bearer practice-token-alice - it's Alice's own order, so this should work.",
            "Now send GET /api/practice/idor/orders/3 with the SAME Alice token - order 3 belongs to Bob. Notice it still succeeds.",
            "Compare the two requests in Vajra Diff - it's the same identity (same token), so Diff will correctly call this 'Inconclusive - same identity used'. Repeat step 2 with practice-token-bob instead to get a real different-identity comparison.",
        ],
        title_te="బ్రోకెన్ ఆబ్జెక్ట్ లెవల్ ఆథరైజేషన్ (IDOR)",
        mini_lesson_title_te="60 సెకన్ల భావన: BOLA / IDOR",
        mini_lesson_te="API ఒక ఆబ్జెక్ట్ గుర్తింపును బయటపెట్టి, ప్రస్తుత వినియోగదారునికి ఆ నిర్దిష్ట ఆబ్జెక్ట్‌ను చూడటానికి అనుమతి ఉందో లేదో తనిఖీ చేయనప్పుడు BOLA లేదా IDOR లోపం ఏర్పడుతుంది.",
        try_it_steps_te=["Alice టోకెన్‌తో ఆమెకు చెందిన order 1ను అభ్యర్థించి సాధారణ ఫలితాన్ని గమనించండి.", "అదే Alice టోకెన్‌తో Bobకు చెందిన order 3ను అభ్యర్థించండి. అది కూడా విజయవంతం కావడం లోపం.", "రెండు అభ్యర్థనల గుర్తింపులు, ఆబ్జెక్ట్ యాజమాన్యం మరియు ప్రతిస్పందనలను పోల్చి ఆధారాన్ని నమోదు చేయండి."],
    ),
    LabInfo(
        id="cors",
        title="Permissive CORS with Credentials",
        concept_category="cors",
        mini_lesson_title="60-second concept: CORS Origin Reflection",
        mini_lesson=(
            "When a server echoes back whatever Origin header it receives - instead of checking it "
            "against an allowlist - and also sets Access-Control-Allow-Credentials: true, any site can "
            "read this API's authenticated responses on a victim's behalf."
        ),
        try_it_steps=[
            "Send GET /api/practice/cors/me with header Origin: https://evil.example.",
            "Look at the response headers - Access-Control-Allow-Origin reflects the exact value you sent, with Access-Control-Allow-Credentials: true.",
            "Run Vajra Analyzer on this request - it should flag this as a CORS potential finding, the same logic used on real targets.",
        ],
        title_te="క్రెడెన్షియల్స్‌తో అనుమతిలేని CORS",
        mini_lesson_title_te="60 సెకన్ల భావన: CORS Origin Reflection",
        mini_lesson_te="సర్వర్ Origin విలువను allowlistతో తనిఖీ చేయకుండా తిరిగి పంపి, credentialsను కూడా అనుమతిస్తే, దాడిచేసే వెబ్‌సైట్ బాధితుడి authenticated API ప్రతిస్పందనను చదవగలదు.",
        try_it_steps_te=["నమ్మలేని Origin విలువతో CORS అభ్యర్థనను పంపండి.", "Access-Control-Allow-Origin మరియు Access-Control-Allow-Credentials ప్రతిస్పందన హెడర్లను పరిశీలించండి.", "Origin నిజంగా అనుమతించబడకూడదని నిర్ధారించి మాత్రమే findingగా నమోదు చేయండి."],
    ),
    LabInfo(
        id="cookies",
        title="Insecure Session Cookie",
        concept_category="cookies",
        mini_lesson_title="60-second concept: Cookie Security Flags",
        mini_lesson=(
            "HttpOnly blocks JavaScript from reading a cookie (mitigating XSS theft), Secure requires "
            "HTTPS, and SameSite limits when the cookie is sent on cross-site requests (mitigating "
            "CSRF). A session cookie missing all three is exposed on every one of those fronts."
        ),
        try_it_steps=[
            "Send GET /api/practice/cookies/login.",
            "Inspect the Set-Cookie header - notice it has none of HttpOnly, Secure, or SameSite.",
            "Run Vajra Analyzer on this request to see it flagged automatically.",
        ],
        title_te="అసురక్షిత సెషన్ కుకీ",
        mini_lesson_title_te="60 సెకన్ల భావన: కుకీ భద్రతా ఫ్లాగ్లు",
        mini_lesson_te="HttpOnly JavaScript ద్వారా కుకీ చదవడాన్ని అడ్డుకుంటుంది, Secure దాన్ని HTTPSకే పరిమితం చేస్తుంది, SameSite cross-site అభ్యర్థనలను నియంత్రిస్తుంది. సెషన్ కుకీలో ఇవి లేకపోతే ప్రమాదం పెరుగుతుంది.",
        try_it_steps_te=["Practice login అభ్యర్థనను పంపండి.", "Set-Cookie హెడర్‌లో HttpOnly, Secure, SameSite ఉన్నాయో చూడండి.", "కుకీ ఉపయోగం మరియు program policy ఆధారంగా ప్రభావాన్ని ధృవీకరించండి."],
    ),
    LabInfo(
        id="headers",
        title="Missing Security Headers",
        concept_category="security_headers",
        mini_lesson_title="60-second concept: Security Headers",
        mini_lesson=(
            "Content-Security-Policy, Strict-Transport-Security, X-Frame-Options, X-Content-Type-Options, "
            "and Referrer-Policy each mitigate a different class of attack. Their absence isn't a "
            "vulnerability by itself, but it removes a layer of defense against other findings."
        ),
        try_it_steps=[
            "Send GET /api/practice/headers/plain and GET /api/practice/headers/hardened.",
            "Compare the two in Vajra Diff - same endpoint pattern, same identity (no auth on either), so it'll score as inconclusive for access control, but look at the raw response headers side by side.",
            "Run Vajra Analyzer on the 'plain' request to see every missing header flagged; run it on 'hardened' to see a clean result.",
        ],
        title_te="లేని సెక్యూరిటీ హెడర్లు",
        mini_lesson_title_te="60 సెకన్ల భావన: సెక్యూరిటీ హెడర్లు",
        mini_lesson_te="CSP, HSTS, X-Frame-Options, X-Content-Type-Options మరియు Referrer-Policy వేర్వేరు దాడులను తగ్గిస్తాయి. అవి లేకపోవడం ఒక్కటే vulnerability కాకపోయినా రక్షణ పొరను తగ్గిస్తుంది.",
        try_it_steps_te=["Plain మరియు hardened ప్రతిస్పందనలను పంపండి.", "రెండింటి response headersను పక్కపక్కన పోల్చండి.", "లేని header యొక్క వాస్తవ ప్రభావాన్ని సందర్భంతో పరిశీలించండి; ఆటోమేటిక్‌గా vulnerabilityగా భావించవద్దు."],
    ),
    LabInfo(
        id="info-exposure",
        title="Verbose Error / Information Exposure",
        concept_category="info_exposure",
        mini_lesson_title="60-second concept: Information Exposure",
        mini_lesson=(
            "A verbose error message can hand an attacker internal file paths, database hostnames, "
            "framework/library versions, or logic they'd otherwise have to guess at - reconnaissance "
            "for free."
        ),
        try_it_steps=[
            "Send GET /api/practice/errors/crash.",
            "Look at the response body - a realistic-looking stack trace revealing an internal hostname and framework.",
            "Run Vajra Analyzer on this request to see it flagged as a potential information-exposure finding.",
        ],
        title_te="వివరమైన లోప సందేశం / సమాచారం బహిర్గతం",
        mini_lesson_title_te="60 సెకన్ల భావన: సమాచారం బహిర్గతం",
        mini_lesson_te="వివరమైన error సందేశం అంతర్గత file paths, database hostnames, framework వివరాలు లేదా application logicను దాడిచేసేవారికి తెలియజేయవచ్చు.",
        try_it_steps_te=["Practice crash endpointకు అభ్యర్థన పంపండి.", "Response bodyలో బయటపడిన internal hostname, path మరియు framework cluesను గుర్తించండి.", "బయటపడిన సమాచారం దాడికి నిజంగా ఉపయోగపడుతుందో విశ్లేషించి ఆధారాన్ని నమోదు చేయండి."],
    ),
]

CATALOG_BY_ID: dict[str, LabInfo] = {lab.id: lab for lab in CATALOG}
