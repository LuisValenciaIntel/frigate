from typing import Optional

from pydantic import Field

from .base import FrigateBaseModel

__all__ = ["AuthConfig", "LoginTelegramConfig"]


class LoginTelegramConfig(FrigateBaseModel):
    enabled: bool = Field(
        default=False, title="Send a Telegram message on successful login"
    )
    bot_token: Optional[str] = Field(default=None, title="Telegram bot token")
    chat_id: Optional[str] = Field(default=None, title="Telegram chat ID")
    parse_mode: Optional[str] = Field(
        default="HTML", title="Telegram message parse mode"
    )
    include_location: bool = Field(
        default=True,
        title="Include approximate public IP geolocation in Telegram login alerts",
    )
    location_api_url: str = Field(
        default="https://ipapi.co/{ip}/json/",
        title="IP geolocation API URL. Use {ip} as the IP address placeholder.",
    )
    timeout: int = Field(default=10, title="Telegram request timeout", ge=1)


class AuthConfig(FrigateBaseModel):
    enabled: bool = Field(default=True, title="Enable authentication")
    reset_admin_password: bool = Field(
        default=False, title="Reset the admin password on startup"
    )
    cookie_name: str = Field(
        default="frigate_token", title="Name for jwt token cookie", pattern=r"^[a-z_]+$"
    )
    cookie_secure: bool = Field(default=False, title="Set secure flag on cookie")
    session_length: int = Field(
        default=86400, title="Session length for jwt session tokens", ge=60
    )
    refresh_time: int = Field(
        default=43200,
        title="Refresh the session if it is going to expire in this many seconds",
        ge=30,
    )
    failed_login_rate_limit: Optional[str] = Field(
        default=None,
        title="Rate limits for failed login attempts.",
    )
    trusted_proxies: list[str] = Field(
        default=[],
        title="Trusted proxies for determining IP address to rate limit",
    )
    login_telegram: LoginTelegramConfig = Field(
        default_factory=LoginTelegramConfig,
        title="Telegram notification configuration for successful logins",
    )
    # As of Feb 2023, OWASP recommends 600000 iterations for PBKDF2-SHA256
    hash_iterations: int = Field(default=600000, title="Password hash iterations")
