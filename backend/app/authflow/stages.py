"""
Vajra Authentication Flow Analyzer (Section 18) - pure stage mapping.

Section 18 asks Vajra to *map* the auth flow -

    registration -> verification -> login -> session creation -> account
    -> password change -> password reset -> logout

- and then "highlight places worthy of manual review" without ever
attacking accounts automatically. This module holds the canonical stages,
why each matters, the manual-review checks for each, and the rule that
assigns an observed path to a stage. No I/O, no vulnerability claims.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageSpec:
    key: str
    title: str
    why: str
    review_checks: tuple[str, ...]
    # Substrings matched against a lowercased request path. Order of the
    # STAGES list is the precedence order - a path is assigned to the first
    # stage it matches, so "password/reset" lands in password_reset, not
    # password_change or login.
    keywords: tuple[str, ...] = field(default_factory=tuple)


STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        key="password_reset",
        title="Password reset",
        why=(
            "Reset flows mint a credential out-of-band. Weak token generation, tokens that don't expire "
            "or aren't single-use, host-header-influenced reset links, or user enumeration on the request "
            "step all have outsized impact here."
        ),
        review_checks=(
            "How is the reset token generated - is it long, random, and unpredictable?",
            "Is the token single-use and short-lived, and invalidated once the password changes?",
            "Does the reset link's host come from the request (Host / X-Forwarded-Host) or from server config?",
            "Does the request step reveal whether an email is registered (different response / timing)?",
            "Are all existing sessions invalidated after a successful reset?",
        ),
        keywords=(
            "forgot-password", "forgot_password", "forgotpassword", "forgot",
            "reset-password", "reset_password", "resetpassword", "password/reset",
            "password-reset", "password_reset", "recover", "recovery",
        ),
    ),
    StageSpec(
        key="password_change",
        title="Password change",
        why=(
            "An authenticated password change should require the current password and should not be reachable "
            "cross-user. It is also a sensitive account event that should refresh session state."
        ),
        review_checks=(
            "Is the current password required, and actually verified server-side?",
            "Can the target account be influenced by a parameter (user id / email) rather than the session?",
            "Are other active sessions invalidated after the change?",
            "Is there rate limiting on current-password attempts?",
        ),
        keywords=(
            "change-password", "change_password", "changepassword", "password/change",
            "update-password", "update_password", "password-change", "password_change",
            "set-password", "new-password",
        ),
    ),
    StageSpec(
        key="registration",
        title="Registration",
        why=(
            "Account creation defines who can get in and with what attributes. Watch for mass-assignment of "
            "role/verified flags, missing rate limiting, and whether an account is usable before verification."
        ),
        review_checks=(
            "Can the registration payload set fields it shouldn't (role, is_admin, email_verified, tenant)?",
            "Is registration rate-limited / CAPTCHA-gated against bulk account creation?",
            "Is a newly registered, unverified account able to perform sensitive actions?",
            "Does registering an already-taken email disclose that the account exists?",
        ),
        keywords=(
            "register", "registration", "signup", "sign-up", "sign_up",
            "create-account", "create_account", "createaccount", "join", "onboarding",
        ),
    ),
    # MFA is checked before email verification: a "/2fa/verify" path should
    # land here, not in email verification just because it contains "verify".
    StageSpec(
        key="mfa",
        title="Multi-factor authentication",
        why=(
            "A second factor is only as strong as its weakest path. Look for endpoints that complete login "
            "without the MFA step, unlimited code attempts, or codes that don't expire or bind to the session."
        ),
        review_checks=(
            "Is there a parallel endpoint that issues a full session without the MFA step?",
            "Are verification-code attempts rate-limited and lockout-protected?",
            "Does the code expire, and is it bound to the specific login attempt / session?",
            "Can MFA enrollment be disabled or reset without re-authentication?",
        ),
        keywords=(
            "mfa", "2fa", "two-factor", "two_factor", "twofactor", "otp", "totp",
            "authenticator", "verify-code", "verify_code", "challenge",
        ),
    ),
    StageSpec(
        key="email_verification",
        title="Email / account verification",
        why=(
            "Verification links prove control of an address. Predictable or non-expiring verification tokens, "
            "or flows that verify an address chosen after the link was issued, undermine that guarantee."
        ),
        review_checks=(
            "Is the verification token random, single-use, and expiring?",
            "Can the address being verified be swapped after the link is generated?",
            "Is verification actually enforced before privileged functionality?",
            "Does re-sending verification allow enumeration or spamming a third party?",
        ),
        keywords=(
            "verify-email", "verify_email", "verifyemail", "email/verify", "email-verify",
            "verify", "verification", "confirm-email", "confirm_email", "confirmemail",
            "activate", "activation", "/confirm",
        ),
    ),
    StageSpec(
        key="logout",
        title="Logout / session termination",
        why=(
            "Logout should actually end the session server-side, not just clear a client cookie. A token that "
            "keeps working after logout is worth documenting."
        ),
        review_checks=(
            "Is the session/token rejected server-side immediately after logout?",
            "Does logout invalidate just this session, or all of them (and is that the intended behavior)?",
            "Is a refresh token also revoked, or can it mint a new access token post-logout?",
        ),
        keywords=("logout", "log-out", "log_out", "signout", "sign-out", "sign_out", "revoke"),
    ),
    StageSpec(
        key="session_issuance",
        title="Session / token issuance",
        why=(
            "This is where a proven identity becomes a bearer credential. Review token contents, lifetime, "
            "refresh handling, and how the token is delivered and stored."
        ),
        review_checks=(
            "What does the issued token contain (JWT claims: user id, role, expiry, audience)?",
            "Is the access token short-lived, and is refresh-token rotation enforced?",
            "Is the token returned in the body, a Set-Cookie (HttpOnly/Secure/SameSite), or both?",
            "Does the OAuth flow validate redirect_uri strictly and use PKCE / state?",
        ),
        keywords=(
            "oauth", "/token", "token/", "auth/token", "access-token", "access_token",
            "refresh-token", "refresh_token", "/jwt", "grant", "/authorize", "openid",
        ),
    ),
    StageSpec(
        key="login",
        title="Login",
        why=(
            "The primary credential check. Look at rate limiting / lockout, whether failures distinguish "
            "'unknown user' from 'wrong password', and any alternate login paths."
        ),
        review_checks=(
            "Is there rate limiting and/or account lockout on failed attempts?",
            "Do responses (body or timing) reveal whether the username exists?",
            "Are there alternate login endpoints (mobile, legacy, SSO callback) with weaker checks?",
            "On success, is a fresh session id issued (no fixation of a pre-login value)?",
        ),
        keywords=(
            "login", "log-in", "log_in", "signin", "sign-in", "sign_in",
            "authenticate", "authentication", "/session", "sessions", "/auth/",
        ),
    ),
    StageSpec(
        key="account_management",
        title="Account management",
        why=(
            "Post-login self-service - profile, email, linked identities. Email change in particular is a "
            "account-takeover-adjacent action and should be treated like a credential change."
        ),
        review_checks=(
            "Does changing the account email require re-authentication and verification of the new address?",
            "Can profile/account endpoints be pointed at another user's id?",
            "Is there a self-service account-deletion or data-export path, and is it authorization-checked?",
            "Can linked social / SSO identities be attached without confirming ownership?",
        ),
        keywords=(
            "/account", "/profile", "/settings", "/me", "/users/", "/user/",
            "change-email", "change_email", "update-email", "email/change",
        ),
    ),
)

# The order Section 18 lists the flow in, for display.
FLOW_ORDER = (
    "registration",
    "email_verification",
    "login",
    "mfa",
    "session_issuance",
    "account_management",
    "password_change",
    "password_reset",
    "logout",
)

STAGE_BY_KEY = {spec.key: spec for spec in STAGES}


def assign_stage(method: str, path: str) -> str | None:
    """Return the stage key an observed request belongs to, or None."""
    lowered = path.lower()
    verb = (method or "GET").upper()

    # A DELETE against a session/token resource is a logout regardless of wording.
    if verb == "DELETE" and any(token in lowered for token in ("session", "token", "/auth")):
        return "logout"

    for spec in STAGES:
        if any(keyword in lowered for keyword in spec.keywords):
            return spec.key
    return None
