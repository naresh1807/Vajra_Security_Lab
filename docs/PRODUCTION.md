# Production deployment

The production Compose stack provides PostgreSQL, Redis/RQ, the API, a recon worker, persistent evidence storage, and a static frontend/reverse proxy. It intentionally binds the web service to `127.0.0.1:8080`; put a TLS-terminating proxy in front of it.

## First deployment

1. Copy `.env.production.example` to `.env` and replace all sample secrets and origins.
2. Temporarily set `VAJRA_ALLOW_REGISTRATION: "true"` for the API and worker in `docker-compose.production.yml`.
3. Run `docker compose -f docker-compose.production.yml up -d --build`.
4. Register the first intended account, then immediately restore `VAJRA_ALLOW_REGISTRATION: "false"` and recreate the API and worker.
5. Configure HTTPS, host firewall rules, encrypted backups for the database/uploads, and log collection in the hosting environment.

The application upgrades the database to the latest reviewed Alembic revision when the API starts. Back up PostgreSQL and the evidence volume before every application upgrade. The Fernet key is separate from both volumes; losing it makes encrypted transactions and controlled identities unrecoverable.

## Required operational checks

- `GET /api/health` must report the RQ queue as available.
- At least one worker must remain connected to the configured Redis queue.
- Test database and evidence-volume restoration regularly.
- Rotate session access by revoking active sessions after suspected compromise.
- Review transaction retention and evidence exports against program rules.

