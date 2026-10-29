"""Environment-driven settings for the NX-OS MCP server."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Transport(str, Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NXOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    username: str = Field(default="", description="Default NX-API username")
    password: str = Field(default="", description="Default NX-API password")

    inventory: Path = Field(default=Path("config/inventory.yaml"))
    guardrails: Path = Field(default=Path("config/guardrails.yaml"))
    redaction: Path = Field(default=Path("config/redaction.yaml"))

    transport: Transport = Transport.STDIO
    http_host: str = "127.0.0.1"
    http_port: int = 8080
    http_bearer_token: str = ""

    allow_insecure: bool = False
    ca_bundle: str | None = None
    allow_http: bool = False

    dry_run: bool = False
    log_level: str = "INFO"
    audit_log_path: Path = Path("logs/audit.jsonl")
    max_output_bytes: int = 65536
    max_fanout: int = 10

    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0
    retry_max: int = 3
    retry_base_s: float = 0.5

    @field_validator("transport", mode="before")
    @classmethod
    def _normalize_transport(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @property
    def tls_verify(self) -> bool | str:
        if self.allow_insecure:
            return False
        if self.ca_bundle:
            return self.ca_bundle
        return True


def load_settings() -> Settings:
    return Settings()
