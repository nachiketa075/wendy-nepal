from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = ""

    session_cookie_name: str = "wendy_session"
    session_ttl_hours: int = 12
    # Defaults to True in production; set explicitly to override.
    cookie_secure: bool | None = None

    # Only enable when the API sits behind a reverse proxy you control that
    # sets X-Forwarded-For. Otherwise clients could spoof their address.
    trust_proxy_headers: bool = False

    business_timezone: str = "Asia/Kathmandu"

    # Address of the public site, used to build password-reset and staff setup links.
    public_site_url: str = "http://localhost:5173"
    password_reset_ttl_minutes: int = 30
    employee_setup_ttl_hours: int = 72

    # How password-reset emails leave the system:
    #   disabled - nothing is sent; the site says reset by email is unavailable
    #   smtp     - real delivery through the SMTP_* settings below
    #   dev_file - development only: writes each email to DEV_MAILBOX_DIR, sends nothing
    #   memory   - automated tests only
    email_delivery: Literal["disabled", "smtp", "dev_file", "memory"] = "disabled"
    dev_mailbox_dir: str = "dev-mailbox"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment == "production":
            if not self.cors_origin_list:
                raise ValueError("CORS_ORIGINS must list the site origin(s) in production")
            if any(o == "*" or not o.startswith("https://") for o in self.cors_origin_list):
                raise ValueError("CORS_ORIGINS must be explicit https:// origins in production")
            if self.cookie_secure is False:
                raise ValueError("COOKIE_SECURE cannot be disabled in production")
            if self.email_delivery in ("dev_file", "memory"):
                raise ValueError("EMAIL_DELIVERY=dev_file/memory is for development and tests only")
            if not self.public_site_url.startswith("https://"):
                raise ValueError("PUBLIC_SITE_URL must be the https:// address of the site in production")
        if self.email_delivery == "memory" and self.environment != "test":
            raise ValueError("EMAIL_DELIVERY=memory is for automated tests only")
        if self.email_delivery == "smtp" and not (self.smtp_host and self.smtp_from):
            raise ValueError("EMAIL_DELIVERY=smtp needs SMTP_HOST and SMTP_FROM")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment == "production"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
