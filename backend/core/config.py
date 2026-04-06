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
    OLLAMA_CYBERSEC_MODEL: str = "foundation-sec:8b"

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
