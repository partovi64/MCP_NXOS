"""Load and validate device inventory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


Role = Literal["spine", "leaf", "border", "borderleaf", "super-spine", "other"]
ApiStyle = Literal["jsonrpc", "ins_api"]


class CredentialRef(BaseModel):
    username_env: str = "NXOS_USERNAME"
    password_env: str = "NXOS_PASSWORD"


class DeviceDefaults(BaseModel):
    protocol: Literal["https", "http"] = "https"
    port: int = 443
    path: str = "/ins"
    api_style: ApiStyle = "jsonrpc"
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0
    underlay_vrf: str = "default"
    platform_profile: str = "n9k-10.3"


class Device(BaseModel):
    name: str
    host: str
    role: Role = "other"
    site: str = "default"
    platform: str = "unknown"
    protocol: Literal["https", "http"] | None = None
    port: int | None = None
    path: str | None = None
    api_style: ApiStyle | None = None
    credentials_ref: str = "NXOS_DEFAULT"
    vrfs: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_vrfs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    connect_timeout_s: float | None = None
    read_timeout_s: float | None = None
    underlay_vrf: str | None = None
    platform_profile: str | None = None

    @field_validator("name")
    @classmethod
    def _name_ok(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(c in cleaned for c in " \t\n/\\"):
            raise ValueError("device name must be a non-empty token without whitespace or path chars")
        return cleaned

    def resolved(self, defaults: DeviceDefaults) -> Device:
        data = self.model_dump()
        for key in (
            "protocol",
            "port",
            "path",
            "api_style",
            "connect_timeout_s",
            "read_timeout_s",
            "underlay_vrf",
            "platform_profile",
        ):
            if data.get(key) is None:
                data[key] = getattr(defaults, key)
        return Device.model_validate(data)

    @property
    def base_url(self) -> str:
        proto = self.protocol or "https"
        port = self.port or (443 if proto == "https" else 80)
        path = self.path or "/ins"
        return f"{proto}://{self.host}:{port}{path}"


class Inventory(BaseModel):
    defaults: DeviceDefaults = Field(default_factory=DeviceDefaults)
    devices: list[Device]
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._by_name: dict[str, Device] = {}
        for device in self.devices:
            resolved = device.resolved(self.defaults)
            if resolved.name in self._by_name:
                raise ValueError(f"duplicate device name: {resolved.name}")
            self._by_name[resolved.name] = resolved
        self.devices = list(self._by_name.values())

    def get(self, name: str) -> Device:
        try:
            return self._by_name[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._by_name)) or "(none)"
            raise KeyError(f"unknown device '{name}'; known: {known}") from exc

    def list(
        self,
        *,
        role: str | None = None,
        site: str | None = None,
        tag: str | None = None,
    ) -> list[Device]:
        out: list[Device] = []
        for device in self.devices:
            if role and device.role != role:
                continue
            if site and device.site != site:
                continue
            if tag and tag not in device.tags:
                continue
            out.append(device)
        return out

    def credentials_for(self, device: Device) -> tuple[str, str]:
        ref = self.credential_refs.get(device.credentials_ref)
        if ref is None:
            ref = CredentialRef()
        username = os.environ.get(ref.username_env, "")
        password = os.environ.get(ref.password_env, "")
        # Fall back to NXOS_USERNAME / NXOS_PASSWORD
        if not username:
            username = os.environ.get("NXOS_USERNAME", "")
        if not password:
            password = os.environ.get("NXOS_PASSWORD", "")
        if not username or not password:
            raise RuntimeError(
                f"missing credentials for ref '{device.credentials_ref}' "
                f"(set {ref.username_env}/{ref.password_env})"
            )
        return username, password


def load_inventory(path: Path) -> Inventory:
    if not path.exists():
        raise FileNotFoundError(f"inventory not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("inventory root must be a mapping")
    return Inventory.model_validate(raw)
