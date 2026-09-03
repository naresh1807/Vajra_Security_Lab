"""Shared case-insensitive header lookup over a plain dict[str, str].

httpx.Headers is case-insensitive natively, but once a response's headers
are stored as a plain dict (HttpTransaction.response_headers), that
guarantee is gone - every module reading stored headers needs the same
lookup, not a copy of it.
"""
from __future__ import annotations


def get_header_ci(headers: dict[str, str], key: str) -> str | None:
    key = key.lower()
    for k, v in headers.items():
        if k.lower() == key:
            return v
    return None
