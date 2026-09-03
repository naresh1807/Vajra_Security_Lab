# Production deployment

The production Compose stack provides PostgreSQL, Redis/RQ, the API, a recon worker, persistent evidence storage, and a static frontend/reverse proxy. It intentionally binds the web service to `127.0.0.1:8080`; put a TLS-terminating proxy in front of it.

## First deployment

1. Copy `.env.production.example` to `.env` (beside `docker-compose.production.yml`) and replace every sample secret and origin. Generate `VAJRA_DATA_ENCRYPTION_KEY` with the command in that file. Keep this `.env` out of version control (it is gitignored) and out of the image (`.dockerignore` excludes it).
2. Register the first account with registration temporarily open:
   `VAJRA_ALLOW_REGISTRATION=true docker compose -f docker-compose.production.yml up -d --build`
3. Create the intended account, then recreate the API and worker with registration closed (the default):
   `docker compose -f docker-compose.production.yml up -d --force-recreate --no-deps api worker`
4. Configure HTTPS termination in front of `127.0.0.1:8080`, host firewall rules, encrypted backups for the `vajra-db` and `vajra-uploads` volumes, and log collection.

The API runs `alembic upgrade head` on startup; the worker waits for the API to be healthy so migrations run exactly once. Back up PostgreSQL and the evidence volume before every application upgrade. The Fernet key lives in `.env`, not in a volume - losing it makes encrypted transactions and controlled identities unrecoverable.

## Required operational checks

- `GET /api/health` must report `"status": "ok"`. The body breaks down:
  - `queue.available` — the RQ/Redis queue is reachable.
  - `database.reachable` and `database.migrations == "up_to_date"` — PostgreSQL is up and at the latest schema.
  - `encryption.ready` — the data-encryption key loaded (`source` is `env` in production).
- At least one worker must remain connected to the configured Redis queue.
- Test database and evidence-volume restoration regularly.
- Rotate session access by revoking active sessions after suspected compromise.
- Review transaction retention and evidence exports against program rules.

## Local Postgres/RQ smoke test

The bundled `backend/.venv` targets SQLite. To exercise the production
database path locally, ensure `psycopg[binary]` is installed
(`backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`)
and point `VAJRA_DATABASE_URL` at a Postgres instance.

