"""
Central application settings.

All configuration is loaded from environment variables (see .env.example).
Nothing in the codebase should read os.environ directly outside this file —
import `settings` instead so config stays in one auditable place.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Jarvis"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "insecure-dev-key-change-me"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Auth ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./data/jarvis.db"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- AI Providers ---
    DEFAULT_AI_PROVIDER: Literal["anthropic", "openai", "gemini"] = "anthropic"

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-5"

    OPENAI_API_KEY: str | None = None
    OPENAI_DEFAULT_MODEL: str = "gpt-4.1"
    #: Image model for the Logo Studio's generation seam. Only used when an
    #: OpenAI key is configured; otherwise the workspace records the concept
    #: spec instead of fabricating an image.
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"

    GEMINI_API_KEY: str | None = None
    GEMINI_DEFAULT_MODEL: str = "gemini-2.5-pro"

    # --- Web search (Deep Research) ---
    #: Which search provider to use. "" disables live search (Deep Research
    #: falls back to honest model-knowledge mode); "tavily" for live results;
    #: "mock" for deterministic offline dev/testing of the pipeline.
    SEARCH_PROVIDER: str = ""
    TAVILY_API_KEY: str | None = None
    #: Results requested per query, and how long identical queries are cached.
    SEARCH_MAX_RESULTS: int = 5
    SEARCH_CACHE_TTL_SECONDS: int = 900

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    LOG_FILE: str = "./data/logs/jarvis.log"

    # --- Security ---
    # Fernet key (32 url-safe base64-encoded bytes) used to encrypt OAuth
    # refresh/access tokens at rest in IntegrationCredential — see
    # app.core.crypto. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Falls back to a fixed dev-only key so local setup doesn't break, but
    # `ENVIRONMENT=production` requires a real one (see crypto.py).
    CREDENTIAL_ENCRYPTION_KEY: str | None = None

    # Base URL of the frontend SPA, used only to build the redirect target
    # after an OAuth callback finishes (e.g. back to /integrations) — never
    # used for anything security-sensitive.
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # --- Integrations ---
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    # Legacy: the one full callback URL used back when Gmail was the only
    # Google-backed capability. No longer read directly by the OAuth flow
    # (see GOOGLE_OAUTH_REDIRECT_BASE_URL) — kept only so an existing .env
    # doesn't error on an unknown-but-harmless extra key.
    GOOGLE_REDIRECT_URI: str | None = None
    # Base URL every Google-backed capability's callback is built from:
    # f"{GOOGLE_OAUTH_REDIRECT_BASE_URL}/{capability_name}/callback". Each
    # capability gets its own distinct, exact-match callback URL (Gmail ->
    # .../integrations/email/callback, Calendar ->
    # .../integrations/google_calendar/callback, etc.) so a state token can
    # only ever be redeemed against the exact capability it was issued for
    # — see api/v1/endpoints/integrations.py. Every one of these URLs must
    # be added as its own "Authorized redirect URI" on the same Google
    # Cloud OAuth client (Google validates exact match; adding a new
    # Google-backed capability later means adding one more URI there, no
    # new OAuth client needed).
    GOOGLE_OAUTH_REDIRECT_BASE_URL: str | None = None

    QUICKBOOKS_CLIENT_ID: str | None = None
    QUICKBOOKS_CLIENT_SECRET: str | None = None
    QUICKBOOKS_ENVIRONMENT: str = "sandbox"

    AMAZON_SP_API_CLIENT_ID: str | None = None
    AMAZON_SP_API_CLIENT_SECRET: str | None = None
    AMAZON_SP_API_REFRESH_TOKEN: str | None = None

    SHOPIFY_SHOP_URL: str | None = None
    SHOPIFY_ACCESS_TOKEN: str | None = None

    # --- Shopify (read-only, Phase 1) ---
    # Read-only Admin API access to the ONE store this build reads from
    # (Primal Penni). Two supported auth methods, in priority order:
    #
    #   1. Client credentials grant (CURRENT — Dev Dashboard apps). New custom
    #      apps created in Shopify's Dev Dashboard no longer expose a static
    #      `shpat_` token; instead you get a Client ID + Client Secret and
    #      exchange them for a 24h access token at
    #      POST https://{shop}/admin/oauth/access_token
    #      (grant_type=client_credentials). Only works for an app your own org
    #      built, installed on a store you own — exactly this case.
    #      Set SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET.
    #
    #   2. Legacy static token (older admin-created "Develop apps"). If you
    #      still have a `shpat_...`, set SHOPIFY_ADMIN_API_TOKEN and it's used
    #      as-is (takes priority; no token exchange).
    #
    # All of these live in .env ONLY — never in the DB, frontend, logs, or git.
    # SHOPIFY_WORKSPACE_ID binds the store to exactly one Jarvis company so
    # Shopify data can never leak into another workspace. With neither auth
    # method configured, the integration reports "not configured" and serves
    # nothing.
    SHOPIFY_STORE_DOMAIN: str | None = None  # e.g. primal-penni.myshopify.com
    SHOPIFY_CLIENT_ID: str | None = None  # Dev Dashboard > Settings > Client ID
    SHOPIFY_CLIENT_SECRET: str | None = None  # Dev Dashboard > Settings > Secret
    SHOPIFY_ADMIN_API_TOKEN: str | None = None  # legacy shpat_... (optional fallback)
    SHOPIFY_API_VERSION: str = "2025-01"
    SHOPIFY_WORKSPACE_ID: str | None = None  # Primal Penni's company UUID

    # Market data for the Investment Dashboard's watchlist/news — free-tier
    # key from https://finnhub.io. Leave blank to keep the dashboard in its
    # honest "not configured" empty state instead of showing sample prices.
    FINNHUB_API_KEY: str | None = None

    TWITTER_API_KEY: str | None = None
    TWITTER_API_SECRET: str | None = None
    INSTAGRAM_ACCESS_TOKEN: str | None = None
    LINKEDIN_ACCESS_TOKEN: str | None = None
    FACEBOOK_ACCESS_TOKEN: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings are cached so the .env file is only parsed once per process."""
    return Settings()


settings = get_settings()
