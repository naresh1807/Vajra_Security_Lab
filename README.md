# Vajra Security Lab

**AI-Assisted Professional Bug Bounty Hunting Workstation**

Find · Understand · Validate · Report · Learn

Vajra is a bug bounty hunting workstation, not a course site. Every screen
is built around a real authorized-hunting workflow (scope → recon → attack
surface → HTTP analysis → investigation → evidence → report), and learning
happens contextually alongside that workflow rather than in a separate LMS.

This repo implements **Phases 1–12** from the product spec
(`docs/PRODUCT_SPEC.md`): project creation, ScopeGuard, the recon engine,
attack-surface asset prioritization, the HTTP Inspector, the JS Inspector,
the API Mapper, the Analyzer, Vajra Diff, the Investigations → Findings
pipeline, the Evidence Vault, the Report Generator, and the Hunt Copilot
(rule-based explanations plus a real, optional LLM for free-form
questions), and the Practice Bridge. Everything below is real and runnable,
not a mock.

## What's implemented

| Module | Status | Notes |
|---|---|---|
| **Vajra ScopeGuard** | ✅ | Normalizes any target, checks it against a project's allowed domains/subdomains/exclusions, returns ALLOWED / BLOCKED / MANUAL_REVIEW + reason. Every recon and HTTP Inspector request routes through it and logs to an audit trail - nothing is ever sent to a target it doesn't cover. |
| **Project creation & dashboard** | ✅ | Program name, target, allowed domains/subdomains, excluded assets, program rules, testing restrictions, rate limit, hunt mode. |
| **Authentication & ownership** | ✅ | Scrypt-hashed passwords, opaque database-backed sessions in HttpOnly SameSite cookies, double-submit CSRF protection, persistent database-backed login throttling, authentication audit events, active-session review/revocation, project ownership enforcement across every nested project API, and ownership checks for global asset/evidence lookups. The first account safely claims legacy unowned projects. Set `VAJRA_ALLOW_REGISTRATION=false` after provisioning accounts on a hosted deployment. |
| **Vajra Recon Engine** | ✅ | Subdomain discovery via crt.sh certificate transparency plus a DNS common-name fallback, passive URL discovery from the Wayback Machine CDX index (bounded, ScopeGuard-filtered, never fetched), ScopeGuard-gated and rate-limited live-host probing, and technology detection. Jobs use zero-dependency inline execution for development or durable Redis/RQ queues with independent workers for production. Queue identifiers are persisted and queued jobs can be cancelled before execution. A per-project "Recon Toolchain" view (Section 41) shows, for every pipeline stage, the underlying tool, the exact command with the real target and rate limit substituted in, and a flag-by-flag explanation. Experienced hunters can toggle which optional sources (subfinder, Wayback, public metadata, Katana) run per project (Section 42); a project can only disable a source, never force on one the deployment has turned off. |
| **Asset Priority Engine** | ✅ | Transparent keyword/heuristic scoring (API, auth, admin, payment, GraphQL, upload, WebSocket, dev/staging indicators) — every point comes with a stated reason, never a black-box score. |
| **Vajra HTTP Inspector** | ✅ | Send a request (method/URL/headers/body) to any in-scope target and inspect the full response - status, headers, cookies, body (JSON pretty-printed), size, timing, and detected technologies. Project-scoped controlled identities store authentication headers encrypted at rest, return only header names through profile APIs, and are applied only after explicit selection. Full request history retains masked profile attribution for repeatable access-control tests. |
| **Vajra JS Inspector** | ✅ | Fetches a JS file (ScopeGuard-gated) and regex-extracts API routes, GraphQL/WebSocket URLs, config references, source-map URLs, and potential secrets (AWS keys, JWTs, generic API-key assignments, private-key blocks) - every secret is masked (first/last 4 chars only) *before* it's ever returned or stored, never as an afterthought. |
| **Endpoint Inventory & Vajra API Mapper** | ✅ | A method-aware inventory of ScopeGuard-approved operations found in bounded `robots.txt`, sitemap, OpenAPI 3.x, and Swagger 2.0 documents, plus GET endpoints from optional constrained Katana crawling. Specification operations are never executed. Operation ID, summary, tags, deprecation, parameter locations, request media types, and security requirements are retained. Inert request templates are generated from schemas without copying examples/defaults/secrets and can be loaded into HTTP Inspector for explicit review and submission. |
| **Visual Attack Surface Map** | ✅ | An interactive, dependency-free graph connects the project to its busiest hosts and their discovered routes. Parameterized, authenticated, and deprecated operations are visually distinguished; host nodes filter the inventory and route nodes open inert HTTP Inspector templates. Large inventories are deliberately bounded to the ten busiest hosts while the complete table remains available. |
| **Vajra Parameter Intelligence** | ✅ | A computed, project-scoped inventory of every parameter seen across HTTP Inspector history, discovered endpoints (declared name/location/type/required plus `{name}` path placeholders), and JS Inspector routes. Each parameter carries a transparent shape classification (numeric/UUID/opaque identifier, credential, pagination, sort-filter, redirect, file, boolean, free-form) and the review areas that shape tends to touch (Section 21) - never a vulnerability claim about the parameter itself. Raw observed values never leave the backend; only their shape (`numeric`/`uuid`/`boolean-like`/`free text`), and nothing at all for credential-shaped names. |
| **Vajra Authentication Flow Analyzer** | ✅ | Maps the canonical auth flow - registration, email verification, login, MFA, session/token issuance, account management, password change, password reset, logout - from paths Vajra has already seen (HTTP history, discovered endpoints, JS routes, public metadata). Each stage carries why it matters and concrete manual-review checks (Section 18); a dynamic "where to focus" list is derived from what was observed. It never sends a request - "Do not automatically attack accounts" is enforced by design. |
| **Vajra Analyzer** | ✅ | Security Header, Cookie, CORS, Transport Security, Information Exposure, API Response, Authentication Behavior, and Public Metadata analyzers classify collected evidence as INFORMATIONAL / INTERESTING / NEEDS_REVIEW / POTENTIAL_FINDING (Section 22), never "confirmed vulnerability." Public Metadata analysis treats advertised paths only as manual-review signals. Run per-transaction or use the project summary across HTTP and metadata evidence. |
| **Vajra Access Control Workbench** | ✅ | A computed planning layer over Vajra Diff (Section 17). Teaches the four comparisons - horizontal, vertical, object ownership, role boundary - with setup steps, finding signals, and evidence needed for each. Groups the project's captured requests by endpoint shape and, per shape, reports whether a comparison is ready to run or exactly what to capture next, with diff-ready pairs (captures differing only by identity) linked straight into Diff. Never sends a request. |
| **Vajra Diff & Access-Control Scenarios** | ✅ | Compares two HTTP Inspector transactions for access-control testing (Sections 16-17). Normalizes both URLs to a path pattern, uses stable controlled-profile attribution when available, diffs response headers and JSON body structure, and produces a confidence score (0-100) - explicitly **never** "Confirmed IDOR." Reusable scenarios group 2–8 captured requests into a bounded pairwise matrix, warn about mixed endpoints, same-identity setups, manual attribution, failed/stale evidence, and open any matrix cell in the full Diff view. Scenarios are read-only over existing evidence and never replay traffic. |
| **Vajra Investigations → Findings** | ✅ | The full SIGNAL → CANDIDATE → INVESTIGATION → EVIDENCE → VALIDATION → FINDING pipeline (Section 23) as one table. Start one from an Analyzer finding, Diff pair, high-priority asset, or selected Access-Control Scenario matrix cells. Matrix investigations store a canonical, versioned, non-secret snapshot of identities, URLs, statuses, confidence signals, categories, and setup warnings. The snapshot remains after its editable scenario is changed or deleted. Includes the six-question False Positive Engine, Impact Assistant, and live report-readiness guidance. |
| **Vajra Evidence Vault** | ✅ | Upload screenshots with captions, annotate them (highlight / redact / label as a non-destructive overlay, or "Flatten & replace" to bake the markup into the image file), and compare two images side by side. Every masking pass runs through one shared function used everywhere evidence is packaged. Scenario investigations include their preserved comparison snapshot alongside project-validated, masked HTTP transactions. A portable ZIP export contains canonical report Markdown, one JSON file per masked transaction, the scenario snapshot, safely named original screenshots, a disclosure-aware manifest, and `SHA256SUMS` integrity checks. Temporary exports are deleted after delivery. |
| **Offline Evidence Bundle Verifier** | ✅ | Accepts a Vajra ZIP without persisting or extracting it, then validates bounded compressed/uncompressed sizes, entry count, per-file size, compression ratios, traversal/absolute paths, Windows path separators, symlinks, encryption, unsupported compression, duplicate/case-colliding names, manifest schema and records, and every SHA-256 checksum. It displays escaped metadata and filenames only—never imported HTML, images, report content, or transaction bodies. |
| **Vajra Report Generator** | ✅ | Auto-drafts editable report fields from an investigation's recorded evidence and notes. Steps use controlled identity names instead of credential values, scenario identities seed the prerequisites, and Markdown export includes the preserved selected comparison cells and setup warnings. The readiness score still requires human validation and never treats a matrix score as confirmed impact. |
| **Vajra Hunt Copilot** | ✅ | Structured explanations remain deterministic and rule-based. Hunt Mode drives how much the Copilot volunteers: `guided` shows the full explanation, a recommended-next-step banner on the project page, and every explanatory blurb; `standard` condenses; `advanced` strips guidance back to a professional analyst view. The Next-Best-Action engine is stage-aware - it reads the project's real state and recommends one concrete move with a one-click shortcut. Free-form chat supports Gemini through `GEMINI_API_KEY` and Claude through `ANTHROPIC_API_KEY`, with `VAJRA_AI_PROVIDER=auto|gemini|anthropic`. Gemini is preferred in auto mode when configured. Both providers receive only grounded project context, with transaction secrets masked before the call, and every answer visibly identifies its provider. English and Telugu questions are supported. |
| **Hunt History** | ✅ | A project-scoped chronological timeline aggregates ScopeGuard decisions, recon jobs, discovered assets, HTTP captures, JavaScript analysis, investigations, and report edits from their authoritative records. Events can be filtered by category and link back to the relevant workspace without duplicating or rewriting audit evidence. |
| **Personal Bug Bounty Skill Map** | ✅ | A per-user view (spanning every project you own) that scores six skills - Recon, HTTP, API Analysis, Access Control, Authentication, Reporting (Section 40) - from capped, transparent signals traced to real activity (recon jobs completed, distinct endpoint shapes exercised, requests sent as a controlled identity, scenarios built, findings validated...). Practice labs feed the skill they teach. Every score opens to show the exact signal breakdown that produced it - no quizzes, no course to complete (Section 39). Full page plus a compact "Your Skills" block on the dashboard (Section 43). |
| **Practice Bridge** | ✅ | Five deliberately vulnerable local labs cover BOLA/IDOR, credentialed CORS origin reflection, insecure cookies, missing security headers, and verbose error exposure. The learning catalog, lessons, and guided steps are available in English and Telugu through a persistent language selector. Investigations recommend relevant labs, carry a safe return link into the exercise, and persist started/completed learning progress. Practice traffic remains separate from target evidence and cannot create a ScopeGuard or localhost/SSRF bypass. Per-lab container isolation remains an optional hardening enhancement. |

## Honest design notes / known limitations

- **Outbound requests are redirect- and SSRF-guarded.** HTTP Inspector,
  JS Inspector, and recon live-host probes validate the initial URL and
  every redirect against project scope. Only HTTP(S) is accepted, embedded
  URL credentials are rejected, cross-origin redirects lose Authorization,
  Cookie, and every custom credential header supplied by a controlled identity;
  DNS answers pointing to non-public address space
  are blocked by default. A deliberately internal authorized lab can opt in
  with `VAJRA_ALLOW_PRIVATE_NETWORK_TARGETS=true`; do not enable that for a
  hosted or untrusted deployment.
- **Recon is passive-first.** Subdomain discovery combines crt.sh, an
  optional local `subfinder` executable, and a DNS common-name fallback.
  URL discovery adds the Internet Archive's Wayback CDX index - a lookup
  against pages already crawled by the Archive, never a request to the
  target - bounded by a URL cap, timeout, and response-size limit.
  Every normalized result passes through ScopeGuard before storage or live
  probing; historical URLs are indexed as inventory, never fetched. The tool adapter never invokes a shell, enforces time and output
  limits, records the displayed command/version, and treats missing tools as
  an explicitly noted degraded source rather than a failed recon run.
- **Go-tool integration is deliberately constrained.** `subfinder`, `dnsx`,
  ProjectDiscovery `httpx`, and Katana are supported
  when present on PATH (or configured through their `VAJRA_*_EXECUTABLE`
  settings). dnsx receives only hosts that already passed ScopeGuard and
  records A, AAAA, and CNAME evidence; the built-in resolver remains the
  fallback. ProjectDiscovery httpx receives only hosts that pass an additional
  public-address preflight, follows no redirects, and inherits the project's
  request rate; Vajra's internal safe client probes any missed hosts. Katana is
  opt-in (`VAJRA_KATANA_ENABLED=true`) and receives only live, already-approved
  URLs. It uses same-host scope, shallow depth, single-request concurrency,
  project rate limits, no form filling or headless browser, and retains only
  parsed GET endpoints that independently pass ScopeGuard. Destructive/session-
  changing path patterns are excluded and rejected discoveries are recorded for
  review. Set `VAJRA_KATANA_EXECUTABLE` when it is not on PATH; use the
  corresponding `VAJRA_*_ENABLED=false` setting to disable any adapter.
- **Hunt Copilot is rule-based, not a live model call**, so every
  explanation is deterministic and auditable. `backend/app/copilot/knowledge.py`
  defines an `AIProvider` protocol as the seam for wiring in a real model later.
- **Authentication is implemented, but enterprise identity is not.** Vajra
  provides local accounts, scrypt password hashing, expiring server-side
  sessions, CSRF protection, and strict project ownership. It does not yet
  provide password reset/email verification, MFA, SSO/OIDC, or organization
  roles. Hosted deployments should set
  `VAJRA_SECURE_COOKIES=true`, serve only through HTTPS, and set
  `VAJRA_ALLOW_REGISTRATION=false` after provisioning intended accounts.
- **HTTP Inspector stores full request/response data** (headers,
  cookies, bodies) because later analysis and evidence generation need the
  original transaction. Those sensitive fields are encrypted at rest with
  authenticated Fernet encryption. Local development generates a gitignored
  `backend/.vajra-data.key` on first write; back it up securely because losing
  it makes encrypted rows unrecoverable. Production should inject
  `VAJRA_DATA_ENCRYPTION_KEY` from a secrets manager instead of using a file.
  Existing plaintext SQLite rows are encrypted during the first startup after
  this upgrade. Optional startup retention is controlled by
  `VAJRA_TRANSACTION_RETENTION_DAYS` (disabled at `0`; set an explicit value
  for hosted deployments), and SQLite secure-delete is enabled. Masking
  (`backend/app/evidence/masking.py`) still applies the moment a
  transaction is packaged as evidence - the Evidence Vault, and the Report
  Generator's auto-drafted steps to reproduce. Headers applied from controlled
  identity profiles are additionally masked in every HTTP transaction API
  response and are never copied back into the Inspector editor. Manually entered
  headers remain visible in the raw Inspector view. Masking of JSON body fields (`password`/`token`/`secret`/
  etc.) is regex-based, not a full JSON-schema-aware pass, so a report's
  "Sensitive information masked" check flags when a body isn't valid JSON
  and the match can't be verified as complete. (Multiple `Set-Cookie`
  headers on one response are captured properly via `response_cookies` —
  the plain `response_headers` dict still collapses duplicates for any
  *other* multi-valued header, which is rare enough in practice not to
  warrant its own field yet.)
- **Evidence Vault has no automated screenshot capture** - this stack has
  no headless browser to drive, so "Capture" (Section 32) means uploading
  your own screenshot, not Vajra taking one. "Compare" is a side-by-side
  view, not a pixel-level diff. "Annotate" (Section 32) is implemented:
  highlight boxes, redaction boxes, and text labels are drawn over the
  image as a non-destructive overlay (image-relative coordinates, edited
  and re-saved freely). Redaction boxes are opaque in the app but only
  become part of the image file - and therefore part of a shared bundle -
  when you use "Flatten & replace", which composites the markup into a new
  PNG client-side. The evidence bundle manifest explicitly flags any
  screenshot whose redactions are not baked in.
- **Evidence bundle screenshots and user-authored report text are not
  automatically redacted.** The ZIP manifest labels that boundary explicitly;
  only HTTP transaction fields pass through Vajra's masking engine. Review the
  report and every screenshot before sharing a bundle. Export construction is
  capped by `VAJRA_MAX_EVIDENCE_EXPORT_BYTES` (100 MiB uncompressed by default)
  and `VAJRA_MAX_EVIDENCE_EXPORT_ATTACHMENTS` (100 by default), rejects files
  outside the investigation's storage directory, sanitizes archive paths, and
  writes SHA-256 checksums for every payload file and the manifest.
- **A valid bundle is internally consistent, not cryptographically attributed.**
  The offline verifier detects corruption or alteration relative to the ZIP's
  own manifest and `SHA256SUMS`, but Vajra does not yet digitally sign exports.
  Someone capable of replacing the whole bundle can recompute both. Treat the
  result as an integrity/structure check, not proof of who created the archive.
  Verification never extracts, executes, imports, or renders bundle contents.
- **The Analyzer covers 8 of the spec's 9 named sub-analyzers with real,
  distinct logic** (Security Headers, Cookies, CORS, Transport Security,
  Information Exposure, API Response, Authentication Behavior, and Public
  Metadata). A standalone Configuration Analyzer is deliberately not
  implemented because its signals would duplicate Information Exposure at
  the scope of a single HTTP transaction. The TLS Analyzer is scheme-level only
  (flags plain HTTP; doesn't independently inspect cipher suite/protocol
  version, since httpx already handles certificate verification).
- **JS Inspector is regex-based, not a JS parser.** It won't catch routes
  built dynamically at runtime (e.g. string-concatenated from variables)
  or hidden inside a minified bundle's string table without a literal
  path-like substring. Good enough to be genuinely useful, not exhaustive.
- **Endpoint discovery is intentionally bounded, not exhaustive.** API Mapper
  combines your HTTP Inspector history, JS Inspector findings, bounded public
  metadata/API specifications, and the optional constrained Katana inventory.
  Discovery fetches only `robots.txt`, capped sitemap documents, and a small set
  of conventional OpenAPI/Swagger document locations. URLs and operations
  listed inside them are indexed after ScopeGuard approval but are not
  automatically requested. YAML aliases are rejected, external `$ref` values
  are not followed, and only local parameter references are resolved. Vajra
  generates bounded placeholder request bodies from local schemas but ignores
  documented examples and defaults. Loading one only fills the Inspector form;
  nothing is sent until the hunter reviews required placeholders and explicitly
  clicks Send. Vajra does not fill remote forms, execute authenticated browser
  flows, submit documented operations automatically, or crawl outside approved
  scope, so state-dependent routes still require manual exploration.
- **Controlled identities are intentionally simple credential profiles.** They
  encrypt one or more authentication headers, support explicit enable/disable
  and selection, and give Diff a stable non-secret identity key even when a
  token rotates. They do not perform login flows, OAuth refresh, browser cookie
  synchronization, or validate that two profiles really belong to different
  people. For legacy/manual requests, Diff still falls back to a literal
  Authorization/Cookie comparison and is not JWT-aware.
- **Access-control scenarios compare captured evidence; they are not an active
  authorization scanner.** Saving or opening a scenario never sends requests.
  The hunter explicitly captures each request first, and Vajra recomputes at
  most 28 pairwise comparisons from up to 8 selected transactions. A high
  matrix score is a triage signal that still requires manual validation,
  ownership confirmation, program-policy review, and reproducibility evidence.
  Starting an investigation copies only selected matrix cells into a versioned,
  non-secret snapshot. Later scenario edits do not silently rewrite an
  investigation's historical basis, and deleting the scenario nulls the live
  link without removing the snapshot or linked HTTP evidence.
- **Investigations and Findings are one table, not two.** "Findings" is
  a filtered view (`status=validated`) over Investigations, deliberately -
  Section 23's pipeline stages are states of one record, not separate
  entities that could drift out of sync. The False Positive Engine's six
  questions are prompts only; Vajra surfaces a hint when an answer is
  logically in tension with the investigation staying open (e.g. "program
  excludes this issue" = true), but never auto-sets status - that
  decision stays with the hunter, per Section 34.
- **Hunt Copilot's live chat sends whatever context it's given to
  Anthropic's API** when a key is configured - investigation notes, an
  asset's hostname/priority signals, or a transaction's (masked) headers
  and body. That's an external network call to a third party, unlike
  every other feature in this app, which only ever talks to the target
  or to fully local/passive sources (crt.sh included). Masking of
  transaction data is regex/key-based (the same engine the Evidence
  Vault uses, not a separate implementation), so the same caveat applies:
  verified to catch `password`/`token`/`secret`-style JSON keys and
  Authorization/Cookie headers, not a guarantee against every possible
  way a secret could appear in a body. Structured explanations
  (Explain buttons, Next-Best-Action) never call out to any API - only
  free-form chat does.
- **Rate limiting follows the queue deployment mode.** Inline development
  uses one in-process token bucket per project. RQ deployments use an atomic
  Redis-backed project bucket shared by API and worker processes; if Redis is
  unavailable, outbound work stops visibly instead of bypassing the limit.
- **SQLite for dev**, per the spec's own recommendation — point
  `VAJRA_DATABASE_URL` at Postgres for anything beyond local use. Schema
  evolution is managed through reviewed Alembic migrations rather than
  relying on `create_all()` to modify existing tables.

## Running it

### Backend (FastAPI + SQLite)

A `.venv` with all dependencies already installed is included at
`backend/.venv`. From `backend/`, in **PowerShell**:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In **bash/git-bash**:

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

(First time / on another machine: `python -m venv .venv` then
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.)

Note: PowerShell doesn't support `&&` for chaining commands the way
bash does — run each line separately, or join with `;`. Also `python`
launches Windows' Python-not-found stub on this machine; the venv's own
`python.exe` (as above) is what actually works.

Health check: `GET http://127.0.0.1:8000/api/health`
Interactive API docs: `http://127.0.0.1:8000/docs`

Database schema changes are managed by Alembic. Normal application startup
runs `alembic upgrade head` automatically. Databases created by older Vajra
builds are safely brought to the baseline and stamped without recreating
tables or deleting rows. For explicit control from `backend/`:

```powershell
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head
```

After changing SQLAlchemy models, generate and review a new revision:

```powershell
.\.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
```

Run tests: `.\.venv\Scripts\python.exe -m pytest -q` (the suite covers
ScopeGuard, the priority engine, the recon service's crt.sh-retry/DNS-fallback
behavior, the HTTP Inspector's scope enforcement, the JS Inspector's
extraction/masking, public-metadata/OpenAPI parsing and response bounds, the API Mapper's path normalization and scoring, every
Analyzer check, Vajra Diff's identity/pattern/confidence logic, the
Investigations false-positive-hint/missing-evidence computations, the
Evidence Vault's masking functions, the Report Generator's
steps-to-reproduce generation and readiness scoring, and the Hunt
Copilot's provider fallback logic - including a real discovered edge
case: the Anthropic SDK raises a plain `TypeError` (not
`AuthenticationError`) when no credentials are configured at all).

Want the free-form Hunt Copilot chat to use a real model? Set
`ANTHROPIC_API_KEY` (or run `ant auth login`) before starting the
backend - no other configuration needed. Without it, chat answers with a
plain message explaining that, and everything else in the app is
unaffected.

### Durable recon workers (Redis + RQ)

Development defaults to `VAJRA_JOB_QUEUE_BACKEND=inline`, so the existing
single-process command still works without Redis. For durable production-like
jobs, start Redis from the repository root:

```powershell
docker compose -f docker-compose.redis.yml up -d
```

Set these variables for both the API and worker processes:

```powershell
$env:VAJRA_JOB_QUEUE_BACKEND = "rq"
$env:VAJRA_REDIS_URL = "redis://127.0.0.1:6379/0"
```

Then run the API normally and start an independent worker from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.worker
```

`GET /api/health` reports the selected queue backend and degrades visibly
when Redis is configured but unavailable. Vajra does not silently fall back
to inline execution in that situation, because doing so would hide a broken
production worker configuration.

### Frontend (React + TypeScript + Vite + Tailwind)

From `frontend/`:

```powershell
npm install
npm run dev
```

Opens on `http://localhost:5173` (or the next free port) and proxies
`/api/*` to the backend on `:8000` — see `vite.config.ts`.

### Try the full loop

1. Open the frontend → **New Project** → fill in a target you're
   authorized to test (e.g. your own domain, or a program's root domain
   with its allowed subdomains/exclusions).
2. On the project page, use **Vajra ScopeGuard** to test a few targets
   and see ALLOWED/BLOCKED/MANUAL_REVIEW decisions live.
3. Click **Start Recon** — watch the job move through
   subdomain discovery → DNS resolution → live-host probing → prioritization.
4. Click any discovered asset in the **Attack Surface** table — the
   **Hunt Copilot** panel on the right explains what it is, why it may
   matter, what to check, what would make it a false positive, and what
   evidence you'd need.
5. Click **Inspect →** on any asset (or **HTTP Inspector** in the
   header) to send it a real request and see the full response - status,
   headers, cookies, body, timing, detected tech, and a quick-glance
   "interesting indicators" summary. Click any response header to get a
   Hunt Copilot explanation of it.
6. Click **Run Vajra Analyzer →** under a response to get the full
   categorized breakdown (Security Headers / Cookies / CORS / Transport
   Security / Information Exposure / API Response / Auth Behavior), or
   click **Analyzer** in the project header for a project-wide summary of
   every Needs-Review/Potential-Finding result across your request history.
7. Click **JS Inspector** to fetch and analyze an in-scope JS file for
   routes, GraphQL/WebSocket URLs, and masked potential secrets.
8. Open **Endpoints** to review robots/sitemap evidence and crawler inventory,
   then click **API Mapper** to see every endpoint collected from HTTP history,
   JS, metadata, or crawling grouped by resource, with an interesting
   score and a suggested first investigation for each.
9. In **HTTP Inspector → Manage controlled identities**, save the complete
   authentication header set for each authorized test account. Select the
   intended identity explicitly and send two requests against the same
   endpoint shape with a different object ID. Then open **Diff** and compare
   them - it names both controlled identities, tells you whether the comparison
   actually tests access control, and gives a confidence score if it does.
   Save 2–8 related captures as an **Access-Control Scenario** to retain the
   setup, review every pair in a matrix, select the cells that matter, and start
   an Investigation with that exact comparison context preserved.
10. Click **Start Investigation →** on any Analyzer finding, Diff result,
    or asset (from the Hunt Copilot panel) to open it in the Investigation
    Workspace - work through the false-positive checklist, attach evidence,
    fill in Observed/Potential impact, and mark it **Validated** once
    you're confident. It'll then show up under **Findings**.
11. Upload a screenshot under **Screenshot Evidence** on the investigation
    page (captioned, never disconnected from the investigation), then click
    **Generate Report →** - it auto-drafts the report from your actual
    recorded evidence and notes, shows a live Readiness Score out of 100
    with exactly what's missing, and lets you **Copy as Markdown** or
    **Export Evidence Bundle (.zip)**. Review user-authored text and
    screenshots before sharing the bundle, then verify it with `SHA256SUMS`.
12. Open **Verify Evidence Bundle** from the sidebar and upload a ZIP to
    validate its structure, safety limits, manifest, and checksums without
    extracting or importing its contents.
13. Type a question into **Ask Vajra Hunt Copilot** at the bottom of the
    side panel, on any page. With `ANTHROPIC_API_KEY` set, it answers
    with a real model grounded in whatever's on screen (an investigation,
    a selected asset, or the current HTTP transaction); without it, it
    tells you plainly how to enable that instead of guessing.

## Repository layout

```
backend/app/
  core/         config, SQLAlchemy session/engine
  projects/     Project model, CRUD, dashboard stats
  scopeguard/   normalize_target, check_scope, rate limiter, audit log
  recon/        crt.sh + DNS-fallback + Wayback URL discovery, live-host probing, priority engine
  http/         Vajra HTTP Inspector - scope/rate-limited request sending, response capture
  identities/   Encrypted, project-scoped controlled credential profiles
  js_inspector/ Vajra JS Inspector - regex extraction of routes/URLs/secrets from fetched JS
  api_mapper/   Vajra API Mapper - computed endpoint grouping/scoring across collected sources
  parameters/   Vajra Parameter Intelligence - computed parameter inventory + shape classification
  authflow/     Vajra Auth Flow Analyzer - maps observed paths onto the canonical auth flow
  surface/      Endpoint inventory, bounded public metadata, and rejection audit
  analyzer/     Pure classification checks over HTTP transactions and metadata evidence
  diff/         Vajra Diff plus saved, bounded access-control comparison scenarios
  workbench/    Vajra Access Control Workbench - computed comparison planner + test-type teaching
  investigations/ Investigation Workspace - false-positive checklist, impact assistant, missing-evidence
  evidence/     Evidence Vault - screenshot upload/storage, request/response masking
  reports/      Report Generator - auto-drafted report fields, readiness scoring
  intelligence/ shared technology-fingerprinting heuristics (used by recon + http)
  copilot/      rule-based Hunt Copilot knowledge base + the AIProvider seam
  skills/       Personal Skill Map - per-user competency scoring from real activity
  history/      read-only project activity aggregation for Hunt History
  recon/tool_reference.py   "Show Underlying Tool" (Section 41) - per-stage command breakdown
  copilot/anthropic_provider.py   real Claude-backed provider for free-form chat
  main.py       FastAPI app wiring

frontend/src/
  modules/dashboard/   hunting dashboard
  modules/projects/    create project, project list, project detail (scope/recon/assets)
  modules/http/        HTTP Inspector - request builder, response viewer, history
  modules/js/          JS Inspector - analyze a JS file, browse findings
  modules/api/         API Mapper - grouped/scored endpoint view
  modules/parameters/  Parameter Intelligence - parameter inventory grouped by shape
  modules/authflow/    Auth Flow Analyzer - the 9-stage flow map with per-stage review checks
  modules/analyzer/    Analyzer - project-wide classified findings summary
  modules/diff/        Vajra Diff - pick two requests, compare, confidence score
  modules/workbench/   Access Control Workbench - test-type teaching + per-endpoint comparison planner
  modules/investigations/ Investigations list, Findings (filtered view), detail/edit workspace (evidence lives here too)
  modules/reports/     Report Generator page - editable fields, readiness score, copy-as-markdown
  modules/skills/      Personal Skill Map page + the shared SkillBar (also on the dashboard)
  modules/copilot/     Hunt Copilot side panel, including the free-form chat box
  components/          Layout, Sidebar, Badge, Card
  api/client.ts        typed fetch client
  types.ts             shared types mirroring backend schemas

docs/PRODUCT_SPEC.md   the full 50-section product vision this build is working toward
```

## Roadmap

The original 12-phase MVP plan (`docs/PRODUCT_SPEC.md`, Section 48) is complete. Remaining work is tracked as post-MVP enhancement and production operations rather than being presented as missing core functionality. **`docs/ROADMAP.md` enumerates the concrete pending items** (vision features, hardening, production ops, known code issues). See `docs/PRODUCTION.md` for the hardened PostgreSQL/Redis/RQ deployment path. The larger 50-section product vision still includes optional expansions such as browser-driven discovery, richer visual mapping, and personal learning analytics.
