from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VERSIONWEAVER_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./versionweaver.sqlite3"
    api_token: str = "development-token"
    runner_api_token: str | None = None
    admin_api_token: str | None = None
    public_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    cors_allowed_origins: str = ""
    web_dist_dir: Path = Path("./web/dist")

    artifact_backend: Literal["local", "s3"] = "local"
    artifact_dir: Path = Path("./artifacts")
    s3_endpoint_url: str | None = None
    s3_bucket: str = "versionweaver-evidence"
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    runner_id: str = "local-runner"
    server_url: str = "http://localhost:8000"
    runner_poll_seconds: float = Field(default=5.0, ge=0.5, le=300)
    runner_lease_seconds: int = Field(default=120, ge=30, le=3600)
    sandbox_engine: Literal["docker", "podman", "local"] = "docker"
    sandbox_image: str = "python:3.12-slim"
    allow_unsafe_local_execution: bool = False
    model_base_url: str = "http://localhost:11434/v1"
    model_api_key: str | None = None

    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @field_validator("api_token")
    @classmethod
    def validate_production_token(cls, value: str, info: object) -> str:
        # Environment-aware enforcement also runs in validate_for_startup because field order is
        # not a stable place to read another value in a pydantic validator.
        return value

    def validate_for_startup(self) -> None:
        if self.environment == "production" and self.api_token in {
            "",
            "development-token",
            "change-me-before-hosting",
        }:
            raise ValueError("VERSIONWEAVER_API_TOKEN must be replaced in production")
        if self.environment == "production":
            if not self.runner_api_token or not self.admin_api_token:
                raise ValueError(
                    "VERSIONWEAVER_RUNNER_API_TOKEN and VERSIONWEAVER_ADMIN_API_TOKEN "
                    "are required in production"
                )
            if len({self.api_token, self.runner_api_token, self.admin_api_token}) != 3:
                raise ValueError("production API tokens must be distinct for each role")
        if self.sandbox_engine == "local" and not self.allow_unsafe_local_execution:
            raise ValueError(
                "local sandbox engine requires VERSIONWEAVER_ALLOW_UNSAFE_LOCAL_EXECUTION=true"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
