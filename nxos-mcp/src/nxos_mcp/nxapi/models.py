"""Pydantic models for NX-API requests/responses and tool envelopes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class InsApiRequest(BaseModel):
    version: str = "1.0"
    type: Literal["cli_show"] = "cli_show"
    chunk: str = "0"
    sid: str = "1"
    input: str
    output_format: Literal["json", "text"] = "json"

    def payload(self) -> dict[str, Any]:
        return {"ins_api": self.model_dump()}


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["cli"] = "cli"
    params: dict[str, Any]
    id: int = 1

    @classmethod
    def show(cls, command: str, *, version: int = 1, req_id: int = 1) -> JsonRpcRequest:
        return cls(params={"cmd": command, "version": version}, id=req_id)


class ToolMeta(BaseModel):
    device: str | None = None
    command_executed: str | None = None
    vrf: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    truncated: bool = False
    dry_run: bool = False


class ToolResult(BaseModel):
    summary: dict[str, Any] | list[Any] | str | None = None
    data: Any = None
    raw: Any = None
    warnings: list[str] = Field(default_factory=list)
    truncated: bool = False
    meta: ToolMeta = Field(default_factory=ToolMeta)

    def model_post_init(self, __context: Any) -> None:
        if self.warnings and not self.meta.warnings:
            self.meta.warnings = list(self.warnings)
        self.meta.truncated = self.meta.truncated or self.truncated


def normalize_table_rows(payload: Any, row_key_hint: str | None = None) -> list[dict[str, Any]]:
    """Normalize NX-OS TABLE_/ROW_ nesting and dict-vs-list quirks."""
    if payload is None:
        return []
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                out.append(item)
            else:
                out.append({"value": item})
        return out
    if not isinstance(payload, dict):
        return [{"value": payload}]

    # Direct ROW_ key
    for key, value in payload.items():
        if key.startswith("ROW_") or (row_key_hint and key == row_key_hint):
            if isinstance(value, list):
                return [v for v in value if isinstance(v, dict)]
            if isinstance(value, dict):
                return [value]
        if key.startswith("TABLE_"):
            return normalize_table_rows(value, row_key_hint=row_key_hint)

    # Nested body / TABLE_*
    for nested_key in ("body", "result", "ins_api"):
        if nested_key in payload:
            nested = normalize_table_rows(payload[nested_key], row_key_hint=row_key_hint)
            if nested:
                return nested
    return [payload] if payload else []
