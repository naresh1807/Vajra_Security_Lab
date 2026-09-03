"""Shared secret-masking used by the JS Inspector (Section 19: "Potential
credentials must be masked") and the Evidence Vault (Section 31: "Mask
cookies, bearer tokens, passwords, sensitive credentials"). One rule for
what "masked" means everywhere in the app.
"""
from __future__ import annotations


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * min(len(value) - 8, 20)}{value[-4:]}"
