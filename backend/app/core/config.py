"""
Configuration from environment variables.
PostgreSQL by default; SQLite if SQLITE=1 or DATABASE_URL starts with sqlite.
"""
import os
from functools import lru_cache
from pathlib import Path


def _default_database_url() -> str:
    if os.getenv("SQLITE"):
        return "sqlite:///./scheduler.db"
    return os.getenv(
        "DATABASE_URL",
        "postgresql://scheduler:scheduler@localhost:5432/scheduler",
    )


_DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings:
    def __init__(self):
        self.database_url = _default_database_url()
        self.storage_root = Path(os.getenv("STORAGE_ROOT", "./data")).resolve()
        self.jwt_secret = os.getenv("JWT_SECRET", _DEFAULT_JWT_SECRET)
        self.jwt_algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        # When False, only existing users can log in; new users must be created by an admin/seed.
        self.allow_public_registration = os.getenv("ALLOW_PUBLIC_REGISTRATION", "true").lower() in ("1", "true", "yes")
        # Comma-separated list of allowed emails. If non-empty, only these can register or be created by admin.
        _whitelist = os.getenv("USER_WHITELIST", "").strip()
        self._user_whitelist = frozenset(e.strip().lower() for e in _whitelist.split(",") if e.strip())

    @property
    def user_whitelist(self) -> frozenset[str]:
        """Set of allowed email addresses (lowercase). Empty = no whitelist (any email allowed)."""
        return self._user_whitelist

    @property
    def is_jwt_secret_unsafe(self) -> bool:
        """True if using the default JWT secret (dangerous in production)."""
        return self.jwt_secret == _DEFAULT_JWT_SECRET


@lru_cache()
def get_settings() -> Settings:
    return Settings()
