"""Shared outbound-request safety controls.

Scope is checked for the initial URL and every redirect. DNS answers are
also inspected so a public-looking hostname cannot silently send Vajra to a
loopback, private, link-local, multicast, reserved, or unspecified address.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import settings
from app.projects.models import Project
from app.scopeguard.engine import check_scope
from app.scopeguard.models import ScopeDecision


class OutboundSafetyError(Exception):
    pass


def _resolve_addresses(host: str) -> set[str]:
    return {item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    default_port = 443 if parts.scheme.lower() == "https" else 80 if parts.scheme.lower() == "http" else None
    return parts.scheme.lower(), (parts.hostname or "").lower(), parts.port or default_port


async def validate_outbound_url(project: Project, url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        raise OutboundSafetyError("Only HTTP and HTTPS URLs are permitted.")
    if not parts.hostname:
        raise OutboundSafetyError("The URL does not contain a valid hostname.")
    if parts.username is not None or parts.password is not None:
        raise OutboundSafetyError("Credentials embedded in URLs are not permitted.")

    scope = check_scope(project, parts.hostname)
    if scope.decision != ScopeDecision.ALLOWED:
        raise OutboundSafetyError(f"ScopeGuard blocked '{url}': {scope.reason}")

    try:
        addresses = await asyncio.to_thread(_resolve_addresses, parts.hostname)
    except socket.gaierror as exc:
        raise OutboundSafetyError(f"Could not resolve '{parts.hostname}'.") from exc

    if not addresses:
        raise OutboundSafetyError(f"'{parts.hostname}' did not resolve to an IP address.")
    if not settings.allow_private_network_targets:
        unsafe = sorted(address for address in addresses if not ipaddress.ip_address(address).is_global)
        if unsafe:
            raise OutboundSafetyError(
                f"'{parts.hostname}' resolves to a non-public address ({', '.join(unsafe)}). "
                "Private, loopback, link-local, reserved, and unspecified targets are disabled by default."
            )
    return scope.normalized_target


async def request_with_safe_redirects(
    client: httpx.AsyncClient,
    project: Project,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: str | None = None,
    max_response_bytes: int | None = None,
    sensitive_header_names: set[str] | None = None,
) -> httpx.Response:
    current_url = url
    current_method = method.upper()
    current_content = content
    request_headers = dict(headers or {})
    credential_header_names = {
        "authorization", "cookie", "proxy-authorization", *(name.lower() for name in (sensitive_header_names or set()))
    }

    async def _buffer_bounded(response: httpx.Response) -> httpx.Response:
        assert max_response_bytes is not None
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > max_response_bytes
            except ValueError:
                too_large = False
            if too_large:
                await response.aclose()
                raise OutboundSafetyError(f"Response exceeded the {max_response_bytes}-byte safety limit.")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_response_bytes:
                await response.aclose()
                raise OutboundSafetyError(f"Response exceeded the {max_response_bytes}-byte safety limit.")
        await response.aclose()
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=bytes(body),
            request=response.request,
            extensions=response.extensions,
        )

    for redirect_count in range(settings.max_outbound_redirects + 1):
        await validate_outbound_url(project, current_url)
        if max_response_bytes is None:
            response = await client.request(
                current_method,
                current_url,
                headers=request_headers or None,
                content=current_content,
                follow_redirects=False,
            )
        else:
            request = client.build_request(
                current_method, current_url, headers=request_headers or None, content=current_content
            )
            response = await client.send(request, follow_redirects=False, stream=True)
        if not response.is_redirect:
            if max_response_bytes is not None:
                return await _buffer_bounded(response)
            return response
        if redirect_count >= settings.max_outbound_redirects:
            if max_response_bytes is not None:
                await response.aclose()
            raise OutboundSafetyError(f"Redirect limit ({settings.max_outbound_redirects}) exceeded.")

        location = response.headers.get("location")
        if not location:
            if max_response_bytes is not None:
                return await _buffer_bounded(response)
            return response
        next_url = urljoin(str(response.url), location)
        if max_response_bytes is not None:
            await response.aclose()

        # Never forward credentials to a different origin. Other caller
        # headers remain intact for same-origin application redirects.
        if _origin(next_url) != _origin(current_url):
            request_headers = {
                key: value for key, value in request_headers.items()
                if key.lower() not in credential_header_names
            }
        if response.status_code == 303 or (response.status_code in {301, 302} and current_method == "POST"):
            current_method, current_content = "GET", None
        current_url = next_url

    raise OutboundSafetyError("Redirect processing failed safely.")
