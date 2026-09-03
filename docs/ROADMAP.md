# Roadmap — what's left

The 12-phase MVP (`PRODUCT_SPEC.md` §48) is complete and runnable. The
backend suite passes (`.\.venv\Scripts\python.exe -m pytest -q`) and the
frontend typechecks and builds. Everything below is the gap between the
shipped MVP and the full 50-section product vision, plus the work needed
to host Vajra for anyone other than a local single user.

Items are grouped by kind, not strictly ordered. A suggested sequence is
at the bottom.

## A. Product-vision features (partial or not built)

### A1. Hunt Mode drives Copilot verbosity — §3, §4, §42 — DONE (first pass)
`HuntMode` (`guided` / `standard` / `advanced`) now changes what the Hunt
Copilot panel volunteers:
- `guided` — everything inline: what / why / checklist / false-positive
  notes / evidence needed, the 60-second concept card, and Next-Best-Action
  with alternatives (unchanged from before).
- `standard` — what / why / checklist inline; false-positive + evidence
  behind one disclosure; the concept one click away; no NBA alternatives.
- `advanced` — what / why only; all other guidance behind a single
  "Show Copilot guidance" disclosure; no concept card; compact NBA.
The mode is switchable after creation from the project header
(`useProjectMode` + `PATCH /api/projects/{id}`, covered by
`backend/tests/test_projects.py`); a `vajra:project-updated` window event
refreshes the panel live. `CreateProject` shows each mode's blurb.

Still open under this heading: the "beginner → professional transition"
(§42) — surfacing tool commands, letting the user drive the recon
pipeline, fewer confirmations — and mode-awareness in the inline
per-page explanations (currently only the Copilot panel reacts).

### A2. Parameter Intelligence — §21, Phase 3 — DONE
`backend/app/parameters/` is a computed view (no table, no outbound
traffic) that aggregates every parameter seen for a project from three
existing sources: HTTP Inspector history (query names + value *shapes*),
discovered endpoints (`parameter_details`, `query_parameters`, and
`{name}` path placeholders), and JS Inspector API_ROUTE findings. Each
parameter gets a transparent classification (numeric / UUID / opaque
identifier, credential, pagination, sort-filter, redirect, file, boolean,
free-form), its review areas (§21 "potential areas"), locations, sources,
schema types, required flag, and observed-endpoint count. Raw values
never leave the backend - only `numeric` / `uuid` / `boolean-like` /
`free text`, and nothing at all for credential-shaped names.
`GET /api/projects/{id}/parameters`, page at `/projects/:id/parameters`,
covered by `backend/tests/test_parameters.py` (12 tests). Not a
vulnerability claim - "Do not classify the parameter itself as
vulnerable" (§21) is enforced by wording throughout.

### A3. Personal Learning Analytics + Skill Map — §39, §40, §43
Not started. Derive competencies (Recon, HTTP, API, Access Control,
Auth, Reporting) from counts already in the DB (transactions analyzed,
investigations by category, reports generated) and render skill bars on
the dashboard. Read-only aggregation, same pattern as `history/`.

### A4. Authentication Flow Analyzer — §18 — DONE
`backend/app/authflow/` maps the canonical flow (registration → email
verification → login → MFA → session/token issuance → account management
→ password change → password reset → logout) from paths Vajra has
already seen (HTTP history, discovered endpoints, JS routes, public
metadata). `assign_stage` is a pure precedence rule (reset before change
before login; MFA `verify` before email `verify`; `DELETE /session` →
logout). Each stage carries a "why it matters" and 3-5 concrete
manual-review checks (§18's examples: reset-token unpredictability,
session invalidation, MFA-bypass endpoints, email-change re-auth). A
dynamic "where to focus" list is built from what was observed. It never
sends a request - §18's "Do not automatically attack accounts" is
enforced by design. `GET /api/projects/{id}/auth-flow`, page at
`/projects/:id/auth-flow`, `backend/tests/test_authflow.py` (8 tests).
The per-transaction "Authentication Behavior" analyzer check is
unchanged and complementary.

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

1. ~~`git init` + first commit~~ — done.
2. ~~A1 Hunt Mode (Copilot verbosity + switcher)~~ — done, first pass.
3. ~~A2 Parameter Intelligence~~ — done.
4. ~~A4 Authentication Flow Analyzer~~ — done. **A5 Access Control Workbench** next.
5. A3 Learning Analytics — the "Learn" pillar of the tagline.
6. Section C — production deployment when ready to host.
7. A1 remainder — the §42 beginner→professional transition.
