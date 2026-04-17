"""
Application configuration loaded from environment / .env file.

Uses pydantic-settings for type-validated settings with .env file support.
"""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    All values can be overridden via environment variables or a .env file
    in the project root.  Field names are case-insensitive at load time.

    OLLAMA_HOST is normalised so a bare IP/hostname coming from the shell
    (e.g. OLLAMA_HOST=0.0.0.0 set by ``ollama serve``) does not silently
    override the correct .env URL.  The validator adds the http:// scheme
    and default port 11434 when they are absent.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Storage
    DATA_DIR: str = "data"

    # Ollama
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3:14b"
    OLLAMA_EMBED_MODEL: str = "mxbai-embed-large"
    # Cybersecurity-specialised model (ADR-020) — used for investigation/triage prompts
    # Falls back to OLLAMA_MODEL if foundation-sec:8b is not pulled
    OLLAMA_CYBERSEC_MODEL: str = "foundation-sec:8b"

    # Model digest pinning (E6-03) — prevents silent model substitution attacks.
    # Set the expected sha256 digest prefix (first 12+ chars) of the configured model.
    # Get the current digest:
    #   curl http://localhost:11434/api/show -d '{"name":"qwen3:14b"}' | python -m json.tool
    # OLLAMA_MODEL_DIGEST=sha256:abc123...  # First 12 chars of digest
    # OLLAMA_EMBEDDING_DIGEST=sha256:...    # Digest for embedding model
    # OLLAMA_ENFORCE_DIGEST=False           # Set True in production to hard-fail on mismatch
    OLLAMA_MODEL_DIGEST: str = ""          # Expected sha256 digest prefix for OLLAMA_MODEL
    OLLAMA_EMBEDDING_DIGEST: str = ""      # Expected sha256 digest prefix for OLLAMA_EMBED_MODEL
    OLLAMA_ENFORCE_DIGEST: bool = False    # If True, raise RuntimeError on digest mismatch

    # Logging
    LOG_LEVEL: str = "INFO"

    # osquery live telemetry collector
    OSQUERY_ENABLED: bool = False  # Default OFF — set True in .env when osquery is installed
    OSQUERY_LOG_PATH: str = r"C:\Program Files\osquery\log\osqueryd.results.log"
    OSQUERY_POLL_INTERVAL: int = 5  # seconds between log checks

    # Firewall telemetry collector (IPFire syslog + Suricata EVE JSON)
    FIREWALL_ENABLED: bool = False          # Default OFF — set True in .env when IPFire is connected
    FIREWALL_SYSLOG_PATH: str = "/var/log/remote/ipfire/messages"
    FIREWALL_EVE_PATH: str = "/var/log/remote/ipfire/suricata/eve.json"
    FIREWALL_SYSLOG_HOST: str = "0.0.0.0"  # Reserved for future UDP listener
    FIREWALL_SYSLOG_PORT: int = 514         # Reserved for future UDP listener
    FIREWALL_HEARTBEAT_THRESHOLD_SECONDS: int = 120   # connected → degraded threshold
    FIREWALL_OFFLINE_THRESHOLD_SECONDS: int = 300     # degraded → offline threshold
    FIREWALL_POLL_INTERVAL: int = 5                   # seconds between file checks
    FIREWALL_CONSECUTIVE_FAILURE_LIMIT: int = 5       # failures before alert

    # Malcolm NSM OpenSearch collector (Phase 27)
    MALCOLM_ENABLED: bool = False  # Default OFF — set True in .env when Malcolm is on LAN
    MALCOLM_OPENSEARCH_URL: str = "https://192.168.1.22:9200"
    MALCOLM_OPENSEARCH_USER: str = "malcolm_internal"
    MALCOLM_OPENSEARCH_PASS: str = ""  # Set MALCOLM_OPENSEARCH_PASS in .env — never hardcode
    MALCOLM_OPENSEARCH_VERIFY_SSL: bool = False  # Intentional — Malcolm uses self-signed TLS
    MALCOLM_POLL_INTERVAL: int = 30  # seconds between OpenSearch polls

    # Windows Event Log live collection (Sysmon + Security + PowerShell + WMI)
    WINEVENT_ENABLED: bool = True   # ON by default — works on any Windows host
    WINEVENT_POLL_INTERVAL: int = 30  # seconds between Get-WinEvent polls

    # IPFire enforcement (SSH-based iptables block actions)
    # Set IPFIRE_ENABLED=true once SSH key is provisioned on IPFire
    IPFIRE_ENABLED: bool = False   # OFF until SSH key configured
    IPFIRE_HOST: str = "192.168.1.1"
    IPFIRE_SSH_PORT: int = 22
    IPFIRE_SSH_USER: str = "root"
    IPFIRE_SSH_KEY: str = ""  # e.g. C:/Users/Admin/.ssh/id_ed25519_ipfire

    # Phase 40 — Enforcement Policy Gate (response control)
    # Conservative defaults per NIST SP 800-61r2 §3.1 and CISA SOAR guidance.
    # Learning mode ON by default for first 30 days — observe without executing.
    # Transition plan:
    #   Days  1–30: ENFORCEMENT_LEARNING_MODE=true  (observe only)
    #   Days 31–60: ENFORCEMENT_LEARNING_MODE=false, ENFORCEMENT_REQUIRE_APPROVAL=true (human-in-loop)
    #   Day  60+:   Selective automation after documented signal validation
    ENFORCEMENT_LEARNING_MODE: bool = True       # NIST 800-61r2 §3.1 baseline period
    ENFORCEMENT_MIN_CONFIDENCE: float = 0.85     # 85% — conservative per CISA SOAR guidance
    ENFORCEMENT_RATE_LIMIT: int = 3              # conservative cap during baseline period
    ENFORCEMENT_RATE_WINDOW_SEC: int = 3600      # rolling window = 1 hour
    ENFORCEMENT_SAFELIST_CIDRS: str = ""         # comma-sep CIDRs; blank = use RFC-1918 defaults
    ENFORCEMENT_REQUIRE_APPROVAL: bool = True    # always require human confirm

    # Ubuntu normalization pipeline (Phase 31)
    # Set UBUNTU_NORMALIZER_URL=http://192.168.1.22:8080 in .env to enable.
    # Empty string = Ubuntu poll disabled (default for systems without Ubuntu N150).
    UBUNTU_NORMALIZER_URL: str = ""          # e.g. "http://192.168.1.22:8080"
    UBUNTU_NORMALIZER_POLL_INTERVAL: int = 60  # seconds between Ubuntu polls

    # Phase 32 — OSINT API keys (all optional — graceful skip if unset)
    ABUSEIPDB_API_KEY: str = ""
    VT_API_KEY: str = ""          # VirusTotal
    SHODAN_API_KEY: str = ""
    GEOIP_DB_PATH: str = "data/GeoLite2-City.mmdb"

    # Map — home LAN node pin (optional override for IP geolocation inaccuracy)
    # Set these in .env to fix the LAN node to your exact location.
    # Leave unset to auto-detect via external IP geolocation (accurate to ISP hub level).
    HOME_LAT: float | None = None   # e.g. HOME_LAT=47.6062
    HOME_LON: float | None = None   # e.g. HOME_LON=-122.3321

    # Network device monitoring — TCP reachability checks shown in dashboard sidebar
    # Each value is "host:port". Empty string = disabled (dot hidden).
    MONITOR_ROUTER_HOST: str = ""       # e.g. "192.168.0.1:80"
    MONITOR_FIREWALL_HOST: str = ""     # e.g. "192.168.1.1:444"
    MONITOR_GMKTEC_HOST: str = ""       # e.g. "192.168.1.22:9200"

    # ChromaDB — remote HTTP client (preferred) vs local PersistentClient (fallback)
    # Set CHROMA_URL to point at a remote Chroma server (e.g. http://192.168.1.22:8200).
    # Leave empty to use local PersistentClient at DATA_DIR/chroma.
    CHROMA_URL: str = ""          # e.g. "http://192.168.1.22:8200"
    CHROMA_TOKEN: str = ""        # Bearer token for remote Chroma (X-Chroma-Token header)

    # Phase 42: Streaming behavioral profiles
    ANOMALY_THRESHOLD: float = 0.7     # Score above this triggers synthetic detection
    ANOMALY_MODEL_DIR: str = "data/anomaly_models"  # Per-entity model storage
    ANOMALY_DEDUP_WINDOW_MINUTES: int = 60  # Suppress duplicate anomaly detections within window

    # Phase 43: Correlation engine (port scan, brute force, beaconing)
    CORRELATION_LOOKBACK_HOURS: int = 2          # Window of events to analyze
    CORRELATION_DEDUP_WINDOW_MINUTES: int = 60   # Suppress repeat correlation alerts

    # Authentication — default is non-empty so auth is ON by default.
    # Set AUTH_TOKEN= in .env to override. An empty string is treated as
    # misconfiguration and will cause ALL requests to be rejected.
    # The value "dev-only-bypass" is the explicit local dev bypass — all other
    # tokens shorter than 32 characters are rejected at startup.
    AUTH_TOKEN: str = "changeme"

    # Legacy admin path TOTP secret — empty string disables the legacy path entirely.
    # Set LEGACY_TOTP_SECRET=<base32-secret> in .env to enable the legacy admin path
    # with TOTP MFA. Leave empty (default) to disable the legacy path completely.
    LEGACY_TOTP_SECRET: str = ""

    # Phase 51: SpiderFoot OSINT investigation platform
    SPIDERFOOT_BASE_URL: str = "http://localhost:5001"

    # Phase 50: MISP Threat Intelligence
    MISP_ENABLED: bool = False            # OFF until MISP is deployed on GMKtec
    MISP_URL: str = "http://192.168.1.22:8080"
    MISP_KEY: str = ""                    # 40-char hex API key from MISP web UI
    MISP_SSL_VERIFY: bool = False         # False for LAN self-signed cert
    MISP_SYNC_INTERVAL_SEC: int = 21600   # 6-hour sync cycle
    MISP_SYNC_LAST_HOURS: int = 24        # Pull attrs updated in last N hours

    # Phase 52: TheHive Case Management
    THEHIVE_URL: str = "http://192.168.1.22:9000"
    THEHIVE_API_KEY: str = ""                 # Set in .env when TheHive deployed
    THEHIVE_ENABLED: bool = False             # Set True when TheHive running on GMKtec
    THEHIVE_SUPPRESS_RULES: list[str] = []   # Rule IDs that skip auto-case creation

    # Phase 54: Reranker microservice (bge-reranker-v2-m3)
    RERANKER_URL: str = ""          # e.g. "http://127.0.0.1:8100" — empty disables reranking
    RERANKER_TOP_K: int = 5         # number of passages to return after reranking
    RERANKER_ENABLED: bool = False  # set True once reranker service is confirmed running

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    @model_validator(mode="after")
    def reject_default_auth_token(self) -> "Settings":
        """Reject startup if AUTH_TOKEN is the default 'changeme' or is weak.

        Raises ValueError so pydantic wraps it in ValidationError at Settings()
        construction time — never at request time.

        The value 'dev-only-bypass' is explicitly allowed for local development
        without a .env file. All other values shorter than 32 characters are rejected.
        """
        token = self.AUTH_TOKEN
        _ALLOWED_WEAK = {"dev-only-bypass"}
        if token == "changeme":
            raise ValueError(
                "AUTH_TOKEN is set to the default 'changeme'. "
                "Generate a strong token: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set AUTH_TOKEN=<token> in your .env file."
            )
        if token not in _ALLOWED_WEAK and len(token) < 32:
            raise ValueError(
                f"AUTH_TOKEN is too short ({len(token)} chars). "
                "Minimum 32 characters required. "
                "Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

    @field_validator("OLLAMA_HOST", mode="before")
    @classmethod
    def normalize_ollama_host(cls, v: object) -> str:
        """
        Ensure OLLAMA_HOST is a full HTTP URL.

        Handles the common case where the shell environment has
        ``OLLAMA_HOST=0.0.0.0`` (set by ``ollama serve``) which is a
        server-side bind address, not a valid client URL.

        Rules:
        - Value already starts with http:// or https:// → pass through
        - Bare "0.0.0.0" (any-interface bind address) → use loopback
        - Any other bare host/IP → add http:// scheme and :11434 port
        """
        raw = str(v).strip()
        if raw.startswith(("http://", "https://")):
            return raw
        # Strip any trailing slash that might appear
        host = raw.rstrip("/")
        # 0.0.0.0 is a server bind address meaning "all interfaces".
        # For a client URL this is meaningless — translate to loopback.
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        # Add port if not already present
        if ":" not in host:
            host = f"{host}:11434"
        return f"http://{host}"


# Module-level singleton so importers can do: from backend.core.config import settings
settings = Settings()
