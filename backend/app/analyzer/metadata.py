"""Pure analysis of already-collected public metadata documents."""
from __future__ import annotations

from urllib.parse import urlsplit

from app.analyzer.checks import AnalyzerFinding, Classification
from app.surface.models import PublicMetadataDocument

_SENSITIVE_PATH_MARKERS = (
    "/admin", "/internal", "/private", "/debug", "/backup", "/backups",
    "/config", "/secret", "/graphql", "/upload", "/.git", "/.env",
)


def analyze_public_metadata(document: PublicMetadataDocument) -> list[AnalyzerFinding]:
    concrete_entries = [
        entry for entry in (document.entries or [])
        if entry.get("type") in {"allow", "disallow", "url"} and entry.get("value")
    ]
    operations = [
        entry["value"] for entry in (document.entries or [])
        if entry.get("type") == "operation" and entry.get("value")
    ]
    sensitive = [
        entry["value"] for entry in concrete_entries
        if any(marker in urlsplit(entry["value"]).path.lower() for marker in _SENSITIVE_PATH_MARKERS)
    ]
    sensitive.extend(
        operation for operation in operations
        if any(marker in operation.lower() for marker in _SENSITIVE_PATH_MARKERS)
    )
    if sensitive:
        return [AnalyzerFinding(
            category="public_metadata",
            classification=Classification.NEEDS_REVIEW,
            title="Sensitive-looking paths are advertised in public metadata",
            description=(
                "Public metadata and API specifications are hints, not access controls. These path names may identify useful "
                "manual review targets, but their presence does not prove that the resources exist or are vulnerable."
            ),
            evidence=sensitive[:10],
        )]

    disallowed = [entry["value"] for entry in concrete_entries if entry.get("type") == "disallow"]
    if disallowed:
        return [AnalyzerFinding(
            category="public_metadata",
            classification=Classification.INTERESTING,
            title="robots.txt advertises disallowed paths",
            description=(
                "Disallow directives guide cooperative crawlers; they do not protect a resource. Review these paths "
                "manually within program policy instead of treating them as findings."
            ),
            evidence=disallowed[:10],
        )]

    if operations:
        return [AnalyzerFinding(
            category="public_metadata",
            classification=Classification.INTERESTING,
            title="Public API specification advertises operations",
            description=(
                "A public OpenAPI/Swagger description improves attack-surface understanding. Exposure is commonly "
                "intentional and is not a vulnerability by itself; validate operations only within program policy."
            ),
            evidence=operations[:10],
        )]

    return [AnalyzerFinding(
        category="public_metadata",
        classification=Classification.INFORMATIONAL,
        title="Public metadata contained no sensitive-looking path signals",
        description=f"Reviewed {len(concrete_entries)} concrete entries from this {document.kind} document.",
    )]
