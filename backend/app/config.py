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

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment == "production":
            if not self.cors_origin_list:
                raise ValueError("CORS_ORIGINS must list the site origin(s) in production")
            if any(o == "*" or not o.startswith("https://") for o in self.cors_origin_list):
                raise ValueError("CORS_ORIGINS must be explicit https:// origins in production")
            if self.cookie_secure is False:
                raise ValueError("COOKIE_SECURE cannot be disabled in production")
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
