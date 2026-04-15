"""Application settings and environment parsing."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_database_url() -> str:
    db_path = Path(__file__).resolve().parents[1] / "chatkit.db"
    return f"sqlite:///{db_path}"


class Settings(BaseSettings):
    database_url: str = Field(default_factory=_default_database_url, alias="DATABASE_URL")
    cors_allowed_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )

    vite_chatkit_api_url: str = Field(default="/chatkit", alias="VITE_CHATKIT_API_URL")
    vite_chatkit_api_domain_key: str = Field(
        default="",
        alias="VITE_CHATKIT_API_DOMAIN_KEY",
    )
    vite_auth0_domain: str = Field(default="", alias="VITE_AUTH0_DOMAIN")
    vite_auth0_client_id: str = Field(default="", alias="VITE_AUTH0_CLIENT_ID")
    vite_auth0_audience: str = Field(default="", alias="VITE_AUTH0_AUDIENCE")

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins_raw.split(",")
            if origin.strip()
        ]

    @property
    def auth0_issuer(self) -> str:
        return f"https://{self.vite_auth0_domain.strip('/')}/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
