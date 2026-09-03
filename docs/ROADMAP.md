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

The "beginner → professional transition" (§42) is now partly here too:
- The Next-Best-Action engine (`backend/app/copilot/next_action.py`) is
  stage-aware - it reads the project's real state (assets, endpoints with
  object ids, mapped auth-flow stages, open/validated investigations,
  reports) and picks the single most useful next move plus a shortcut
  route (`cta_route`) and a §26-style "areas worth your attention" list.
- `guided`/`standard` projects get a prominent recommended-next-step
  banner on the project page with a one-click CTA; `advanced` projects
  don't (they navigate themselves). `guided` also sees the focus-area
  list and the explanatory blurbs; `standard`/`advanced` don't.
- Per-project recon pipeline switches (§42: "User changes recon
  pipeline"): `Project.recon_sources` (JSON, migration `b7f2d1a4c8e3`)
  toggles subfinder / Wayback / public-metadata / Katana per project.
  A project can only *disable* an optional source, never force on one the
  deployment turned off (`recon_source_enabled` in `recon/service.py`
  gates each stage; crt.sh and the DNS fallback always run). Toggles show
  on the project page for `standard`/`advanced` hunters, not `guided`.

- Hunt Playbook (§42: "User creates custom workflows"):
  `Project.playbook` (JSON, migration `c3a9e5f01b46`) is an ordered
  checklist of steps, seeded from a default authorized-bug-bounty
  methodology on project creation and fully editable (add / edit / check
  / remove, debounce-saved via `PATCH /api/projects/{id}`, validated by
  `app/projects/playbook.py`). Shown as a collapsible card on the project
  page with a progress bar. Gates nothing - it just keeps the hunter's
  place across a long engagement.

A1 (§3, §4, §42) is now fully addressed.

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

### A3. Personal Learning Analytics + Skill Map — §39, §40, §43 — DONE
`backend/app/skills/` is a per-user computed view (route `GET /api/skills`,
not project-scoped - §39's "personal learning" spans every project the
user owns). Six skills in §40's order - Recon, HTTP, API Analysis,
Access Control, Authentication, Reporting - each scored 0-100 from
capped, transparent signals traced to real DB activity (recon jobs
completed, distinct endpoint shapes exercised, requests sent as a
controlled identity, scenarios built, findings validated, ...). Practice
labs feed the skill they teach (idor -> Access Control, cookies -> Auth).
Bands: not started / getting started / developing / proficient / strong.
Each skill returns its signal breakdown - no black-box number (§39: "no
separate course completion"). Full page at `/skills` (10-segment bars +
per-skill "what produced this score" + grow-it next step); a compact
"Your Skills" block on the dashboard (§43). `backend/tests/test_skills.py`
(6 tests, incl. per-user scoping). Suite: 211 passing.

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

### A5. Access Control Workbench — §17 — DONE
`backend/app/workbench/` is a computed planning layer over Vajra Diff.
`teaching.py` holds the four test types (horizontal, vertical, object
ownership, role boundary) with how-to-set-up / signals-worth-a-finding /
evidence-needed for each. `service.py` groups the project's captured
requests by endpoint shape and, per shape, reports a readiness state
(`ready` / `needs_second_identity` / `no_usable_captures`), a concrete
next step, and diff-ready `suggested_pairs` (captures that differ only by
identity). `GET /api/projects/{id}/access-control/workbench`, page at
`/projects/:id/access-control` (sidebar + project header). HTTP Inspector
now honors `?identity=<id>` and Diff honors `?a=&b=` so the workbench's
links land ready to act. `backend/tests/test_access_control_workbench.py`
(5 tests). Never sends a request - §17's "controlled accounts and
authorized environments only" is enforced by design.

### A6. Four-panel workstation UI — §45 — DONE
`frontend/src/modules/workstation/Workstation.tsx` at
`/projects/:id/workstation` is the §45 cockpit: attack surface (assets +
endpoints) on the left, the recommended next action and focus detail in
the centre, the Hunt Copilot on the right, and Investigations / History /
Playbook tabs along the bottom. It's a new composition view - the
existing per-module pages stay as the deep-dive workspaces, and every
panel deep-links into them. `Layout` drops the global nav sidebar on this
route so it's a true cockpit. Reached via a prominent "Open Workstation"
button on the project page. Verified end to end with a headless browser
(register → create project → workstation, no console errors).

### A7. Progressive tool disclosure — §41 — DONE
`backend/app/recon/tool_reference.py` is a pure per-project breakdown of
the recon toolchain: for each pipeline stage (subdomain discovery, DNS
resolution, live-host probing, tech detection, metadata discovery,
crawling) it lists the built-in and optional-external tools, each with
its role, an active/passive marker, the exact command with the project's
real target and rate limit substituted in, and a flag-by-flag
explanation. External tools report their real enabled/disabled config.
`GET /api/projects/{id}/recon/tool-reference`, page at
`/projects/:id/recon-tools` ("Show underlying tools →" from the recon
card). `backend/tests/test_recon_tool_reference.py` (5 tests). Recon job
notes still carry what actually ran on a given run; this is the
"learn the tooling" companion.

### A8. Recon URL + parameter discovery — §7, Phase 3 — DONE
`backend/app/recon/wayback.py` adds a passive URL-discovery stage: it
queries the Internet Archive's Wayback CDX index (a public archive of
already-crawled pages - never contacts the target), bounded by a URL
cap, a timeout, and a response-size limit. `store_wayback_discovery`
runs every historical URL through `sanitize_endpoint_url` (ScopeGuard +
destructive-path + sensitive-value redaction) and indexes the survivors
as GET `DiscoveredEndpoint` rows with `source="wayback"` - so they flow
straight into the API Mapper, Parameter Intelligence, Auth Flow
Analyzer, and Access Control Workbench. Nothing is fetched. Wired into
`run_recon` (parallel with subdomain discovery), reported in the job
summary/notes, `VAJRA_WAYBACK_*` settings, `backend/tests/test_wayback.py`
(7 tests). General active crawling beyond opt-in Katana remains out of
scope by design.

### A9. Screenshot annotate — §32 — DONE (markup; capture still N/A)
Screenshots now carry a non-destructive markup overlay: highlight boxes,
opaque redaction boxes, and text labels in image-relative coordinates,
stored on the attachment (`annotations` JSON column, migration
`a1c4e7b902d5`), validated by `app/evidence/annotations.py`, editable and
re-saved freely. `AnnotationEditor` (drag to draw) also offers "Flatten &
replace", which composites the markup into a new PNG client-side and
swaps the stored file via `PUT .../evidence/{id}/image` (clearing the
overlay). The evidence bundle manifest flags any screenshot whose
redactions are not baked in, with a per-file `has_unbaked_annotations`
and a warning. `backend/tests/test_evidence_annotations.py` (5 tests).
Automated capture stays out of scope - no headless browser in the stack.

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

## C. Production operations — deployment artifacts hardened

- ~~Repo under version control~~ — done (`main` branch, `.gitignore` /
  `.gitattributes` cover `.env`, keys, DBs, `node_modules`, `.venv`).
- `docker-compose.production.yml` reviewed: `worker` now waits for the
  API to be healthy so migrations run exactly once; `web` has a
  healthcheck; `VAJRA_ALLOW_REGISTRATION` is env-overridable for the
  first-account bootstrap; the API healthcheck has a `start_period`.
  `.dockerignore` added for both images (the frontend `COPY . .` was
  pulling in `node_modules` and any local `.env`).
- `GET /api/health` now reports database reachability + migration state
  and data-encryption readiness alongside the queue, and `status` is
  `degraded` if any is unhealthy (`backend/tests/test_health.py`).
- FastAPI startup moved from the deprecated `on_event` to a `lifespan`
  handler.
- **Still requires a hosting environment**: provision the host, real
  `.env` secrets, DNS + TLS termination in front of `127.0.0.1:8080`,
  firewall, encrypted volume backups, log collection. `docs/PRODUCTION.md`
  is the checklist. This is the only remaining part of C and it cannot be
  done from a dev machine.

## D. Known code issues — resolved

- ~~`gemini_model = "gemini-3.7-flash"`~~ — corrected to
  `gemini-2.5-flash` (a current GA model) in `config.py`, `.env.example`,
  and `docker-compose.production.yml`. Override with `VAJRA_GEMINI_MODEL`.
- ~~bundled `.venv` missing `psycopg`~~ — installed to match
  `requirements.txt`; `docs/PRODUCTION.md` notes the local Postgres path.
- `.env.production.example` had a **real** `GEMINI_API_KEY` (owner
  confirmed). Replaced with a placeholder twice; `.gitignore` excludes
  every real `.env`. **The exposed key(s) must be revoked in Google AI
  Studio** — that is on the owner, outside this repo.

## Suggested sequence

1. ~~`git init` + first commit~~ — done.
2. ~~A1 Hunt Mode (Copilot verbosity + switcher)~~ — done, first pass.
3. ~~A2 Parameter Intelligence~~ — done.
4. ~~A4 Authentication Flow Analyzer~~ — done.
5. ~~A5 Access Control Workbench~~ — done.
6. ~~A3 Learning Analytics / Skill Map~~ — done.
7. ~~A7 progressive tool disclosure~~ — done.
8. ~~A8 recon URL / parameter discovery~~ — done.
9. ~~A9 screenshot annotate~~ — done.
10. ~~Section C — production artifacts hardened~~ (deployment to a real
    host still needs a host — see C).
11. ~~A1 remainder~~ — done (stage-aware Next-Best-Action, mode-gated
    guidance, per-project recon pipeline switches, Hunt Playbook).
12. ~~A6 four-panel Workstation UI~~ — done.

**Everything in this roadmap is built.** A10 (standalone Configuration
Analyzer / deep TLS inspection) remains deliberately deferred - its
signals would duplicate Information Exposure and httpx already verifies
certificates. The only work left is operational: deploying the hardened
Compose stack to an actual host (section C), which needs infrastructure,
not code.
