"""
Central configuration for Vajra Security Lab backend.

Development defaults to SQLite so the platform runs with zero external
services. Point DATABASE_URL at PostgreSQL for production, per the spec's
tech stack (Section 46).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VAJRA_", env_file=".env", extra="ignore")

    app_name: str = "Vajra Security Lab"
    database_url: str = "sqlite:///./vajra.db"

    # When set to a built frontend directory, the API also serves the SPA at
    # `/` (used by the desktop app so the UI and API are same-origin).
    static_dir: str = ""

    # CORS - the Vite dev server default origin.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ScopeGuard defaults. A project can override its own rate limit.
    default_rate_limit_rps: float = 1.0

    # Outbound HTTP behaviour used by the recon engine's live-host probing.
    http_timeout_seconds: float = 8.0
    http_user_agent: str = "VajraSecurityLab-Recon/0.1 (+authorized-recon)"
    max_outbound_redirects: int = 5
    allow_private_network_targets: bool = False

    # Sensitive HTTP transaction payloads are encrypted before persistence.
    # Production should inject the key through VAJRA_DATA_ENCRYPTION_KEY.
    # Local development gets a gitignored key file generated on first write.
    data_encryption_key: str = ""
    data_encryption_key_file: str = ".vajra-data.key"
    # Opt-in to avoid surprising deletion during an upgrade. Hosted
    # deployments should set an explicit policy such as 90 days.
    transaction_retention_days: int = 0
    session_cookie_name: str = "vajra_session"
    csrf_cookie_name: str = "vajra_csrf"
    session_lifetime_hours: int = 12
    secure_cookies: bool = False
    allow_registration: bool = True
    login_attempt_limit: int = 5
    login_attempt_window_minutes: int = 15
    job_queue_backend: str = "inline"  # inline | rq
    redis_url: str = "redis://127.0.0.1:6379/0"
    recon_queue_name: str = "vajra-recon"
    recon_job_timeout_seconds: int = 1800
    subfinder_enabled: bool = True
    subfinder_executable: str = "subfinder"
    dnsx_enabled: bool = True
    dnsx_executable: str = "dnsx"
    projectdiscovery_httpx_enabled: bool = True
    projectdiscovery_httpx_executable: str = "httpx"
    katana_enabled: bool = False
    katana_executable: str = "katana"
    katana_depth: int = 2
    katana_max_response_size: int = 2 * 1024 * 1024
    public_metadata_enabled: bool = True
    public_metadata_max_response_bytes: int = 2 * 1024 * 1024
    public_metadata_max_documents_per_host: int = 10
    public_metadata_max_entries_per_document: int = 2000
    api_spec_discovery_enabled: bool = True
    external_tool_timeout_seconds: int = 120
    external_tool_max_output_bytes: int = 10 * 1024 * 1024
    ai_provider: str = "auto"  # auto | gemini | anthropic
    # A current, generally-available Gemini model. Override with
    # VAJRA_GEMINI_MODEL if your account has access to a newer one.
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 30.0

    # Passive OSINT sources. crt.sh is a public certificate-transparency
    # search engine - querying it never touches the target's infrastructure.
    # It's a free community service that is frequently slow or briefly
    # overloaded (502/503), so it gets a longer timeout and a couple of
    # retries rather than the tight timeout used for live-host probing.
    crtsh_url: str = "https://crt.sh/"
    crtsh_timeout_seconds: float = 20.0
    crtsh_retries: int = 2

    # Passive URL discovery from the Internet Archive Wayback Machine CDX
    # index. Queries an archive of already-crawled pages - never contacts
    # the target. Every URL still passes ScopeGuard before storage.
    wayback_enabled: bool = True
    wayback_cdx_url: str = "http://web.archive.org/cdx/search/cdx"
    wayback_timeout_seconds: float = 25.0
    wayback_max_urls: int = 1000
    wayback_max_response_bytes: int = 8 * 1024 * 1024

    # DNS-based fallback subdomain check. Passive-adjacent: only resolves
    # candidate hostnames via public DNS, never sends the target an HTTP
    # request. Runs alongside crt.sh so recon isn't a single point of
    # failure on one third-party service.
    common_subdomain_wordlist: list[str] = [
        "www", "api", "app", "admin", "portal", "account", "accounts", "auth", "login", "sso",
        "dev", "staging", "stage", "test", "uat", "qa", "beta", "demo", "sandbox", "preprod",
        "secure", "vpn", "mail", "webmail", "cdn", "static", "assets", "img", "media", "files",
        "upload", "docs", "help", "support", "status", "blog", "shop", "store", "m", "mobile",
        "internal", "intranet", "git", "gitlab", "jenkins", "ci", "grafana", "kibana", "monitor",
        "metrics", "graphql", "ws", "payments", "billing", "dashboard", "console", "backend",
        "service", "services", "gateway", "rest",
    ]
    dns_bruteforce_concurrency: int = 15

    # Evidence Vault (Section 31-32). Local disk is fine for a single-user
    # dev deployment; a hosted deployment should point this at object
    # storage instead.
    upload_dir: str = "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_evidence_export_bytes: int = 100 * 1024 * 1024  # uncompressed source bytes
    max_evidence_export_attachments: int = 100
    max_evidence_verify_upload_bytes: int = 110 * 1024 * 1024
    max_evidence_verify_uncompressed_bytes: int = 125 * 1024 * 1024
    max_evidence_verify_entries: int = 300
    max_evidence_verify_file_bytes: int = 25 * 1024 * 1024
    max_evidence_verify_compression_ratio: float = 250.0
    allowed_upload_content_types: list[str] = ["image/png", "image/jpeg", "image/gif", "image/webp"]


settings = Settings()
