# Roadmap — what's left

The 12-phase MVP (`PRODUCT_SPEC.md` §48) is complete and runnable. The
backend suite passes (`.\.venv\Scripts\python.exe -m pytest -q`) and the
frontend typechecks and builds. Everything below is the gap between the
shipped MVP and the full 50-section product vision, plus the work needed
to host Vajra for anyone other than a local single user.

Items are grouped by kind, not strictly ordered. A suggested sequence is
at the bottom.

## A. Product-vision features (partial or not built)

### A1. Hunt Mode is cosmetic — §3, §4, §42
`HuntMode` (`guided` / `standard` / `advanced`) is stored on the project
(`backend/app/projects/models.py`) and rendered as a badge, but nothing
consumes it. To close this:
- Gate the "Why this matters / what to check / false positives / evidence"
  panels and mini-lessons on `guided` mode; collapse them in `standard`;
  hide them in `advanced`.
- Reduce Copilot Next-Best-Action verbosity by mode.
- Add the "beginner → professional transition" (§42): surface tool
  commands, let the user drive the recon pipeline, fewer confirmations.

### A2. Parameter Intelligence — §21, Phase 3
Parameters are captured per endpoint (`surface/models.py`
`query_parameters` / `parameter_details`) but never aggregated. Build a
project-scoped parameter inventory: name, observed endpoint count,
inferred classification (numeric object id, UUID, token, free text),
and suggested review areas. No new outbound traffic — this is a
computed view over existing `DiscoveredEndpoint` rows.

### A3. Personal Learning Analytics + Skill Map — §39, §40, §43
Not started. Derive competencies (Recon, HTTP, API, Access Control,
Auth, Reporting) from counts already in the DB (transactions analyzed,
investigations by category, reports generated) and render skill bars on
the dashboard. Read-only aggregation, same pattern as `history/`.

### A4. Authentication Flow Analyzer — §18
Today: a per-transaction "Authentication Behavior" analyzer check.
Missing: the mapped flow (registration → verification → login → session
creation → password change → password reset → logout) with each stage
flagged for manual review. Could be a guided checklist seeded from
discovered endpoints rather than an automated crawler.

### A5. Access Control Workbench — §17
Covered indirectly by Vajra Diff + Access-Control Scenarios. A dedicated
workbench would let the hunter pick Session A, Session B, an endpoint,
and an object identifier, then walk horizontal / vertical / role
boundary tests with teaching at each step.

### A6. Four-panel workstation UI — §45
Current UI is page-per-module with a Copilot side panel. The spec
describes a single workstation view: assets/endpoints left, HTTP/analysis
center, Copilot right, evidence/notes/history bottom. Large front-end
change; do it only if the page-based flow proves limiting.

### A7. Progressive tool disclosure — §41
`tools/adapter.py` records the displayed command and tool version.
Surface it in the UI: "Show underlying tool → show command → explain
command" on each recon step.

### A8. Recon URL + parameter discovery — §7, Phase 3
Only optional Katana GET-endpoint crawling exists. A general (still
ScopeGuard-gated, still bounded) URL crawler and parameter-discovery
stage would fill out the recon pipeline.

### A9. Screenshot annotate + capture — §32
Captions only. No drawing/markup, no headless capture (no browser in the
stack), and "compare" is side-by-side, not a pixel diff.

### A10. Configuration Analyzer / full TLS Analyzer — §22
Deliberately omitted: a standalone Configuration Analyzer would duplicate
Information Exposure, and the TLS check is scheme-level only (httpx
already verifies certificates). Listed here only for spec traceability —
revisit only if cipher/protocol inspection becomes a requirement.

## B. Security & auth hardening

- Password reset, email verification, MFA, SSO/OIDC, organization roles
  (`README.md` "Authentication is implemented, but enterprise identity is
  not").
- Cryptographic signing of evidence bundles. The offline verifier checks
  internal consistency against the bundle's own `SHA256SUMS`; it is not
  attribution. Someone who replaces the whole ZIP can recompute both.
- Per-lab container isolation for Practice labs. They run in-process
  today; the spec wants Docker-isolated labs.

## C. Production operations

- **The repo is not under version control.** `git init`, first commit,
  confirm `.gitignore` covers `backend/.vajra-data.key`, `backend/vajra.db`,
  `.env`, `frontend/node_modules`, `backend/.venv`.
- Deploy `docker-compose.production.yml`: PostgreSQL, Redis/RQ, API,
  worker, TLS-terminating reverse proxy, host firewall, encrypted backups
  for the database and evidence volume, log collection. See
  `docs/PRODUCTION.md`.
- Real values in `.env` (copied from `.env.production.example`), the
  `VAJRA_ALLOW_REGISTRATION` first-account bootstrap, then lock it back
  to `false`.
- Operational checks from `docs/PRODUCTION.md`: `/api/health` reports the
  queue available, at least one worker connected, restore drills.

## D. Known code issues to resolve

- `backend/app/core/config.py` sets `gemini_model = "gemini-3.7-flash"`.
  Verify this against a real Gemini model id before relying on the
  Gemini-backed Copilot path; the Anthropic provider is the tested one.
- `.env.production.example` contained a **real** `GEMINI_API_KEY`
  (confirmed by the owner). It has been replaced with a placeholder and
  `.gitignore` now excludes every real `.env`. **The exposed key must be
  revoked/rotated in Google AI Studio** — it cannot be un-leaked. Real
  secrets live only in an untracked `.env`, never in an `*.example`.

## Suggested sequence

1. `git init` + first commit (nothing is tracked right now).
2. A1 Hunt Mode — the plumbing exists; it's the spec's central UX promise.
3. A2 Parameter Intelligence — high hunting value, computed over existing data.
4. A4 + A5 — remaining core analysis depth.
5. A3 Learning Analytics — the "Learn" pillar of the tagline.
6. Section C — production deployment when ready to host.
