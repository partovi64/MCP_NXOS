"""Shared runtime: inventory, client, guardrails, command execution helper."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from nxos_mcp.guardrails.audit import AuditEvent, AuditLogger, utc_now_iso
from nxos_mcp.guardrails.policy import GuardrailPolicy, load_policy
from nxos_mcp.guardrails.ratelimit import DeviceGate, RateLimiter
from nxos_mcp.guardrails.redaction import Redactor, load_redactor
from nxos_mcp.guardrails.validator import CommandValidator
from nxos_mcp.inventory import Device, Inventory, load_inventory
from nxos_mcp.nxapi.client import NxapiClient
from nxos_mcp.nxapi.errors import GuardrailViolation, NxosMcpError
from nxos_mcp.nxapi.models import ToolMeta, ToolResult
from nxos_mcp.settings import Settings, load_settings

log = structlog.get_logger(__name__)


@dataclass
class Runtime:
    settings: Settings
    inventory: Inventory
    policy: GuardrailPolicy
    validator: CommandValidator
    redactor: Redactor
    audit: AuditLogger
    limiter: RateLimiter
    client: NxapiClient
    vrf_cache: dict[str, tuple[float, set[str]]] = field(default_factory=dict)
    mcp_client: str | None = None

    @classmethod
    def create(cls, settings: Settings | None = None) -> Runtime:
        settings = settings or load_settings()
        inventory = load_inventory(settings.inventory)
        policy = load_policy(settings.guardrails)
        # Allow settings override for output/fanout
        policy.limits.max_output_bytes = min(
            policy.limits.max_output_bytes, settings.max_output_bytes
        )
        policy.limits.max_fanout_devices = min(
            policy.limits.max_fanout_devices, settings.max_fanout
        )
        username = settings.username
        password = settings.password
        # Client uses settings credentials; per-device may re-auth via inventory
        client = NxapiClient(settings, username=username or "unused", password=password or "unused")
        return cls(
            settings=settings,
            inventory=inventory,
            policy=policy,
            validator=CommandValidator(policy),
            redactor=load_redactor(settings.redaction),
            audit=AuditLogger(settings.audit_log_path),
            limiter=RateLimiter(policy.limits),
            client=client,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    def get_device(self, name: str) -> Device:
        return self.inventory.get(name)

    def assert_tool_allowed(self, device: Device, tool: str) -> None:
        if device.allowed_tools and tool not in device.allowed_tools:
            raise GuardrailViolation(
                f"tool '{tool}' not permitted on {device.name}",
                hint="Check inventory allowed_tools",
            )

    def assert_vrf_allowed(self, device: Device, vrf: str) -> None:
        from nxos_mcp.guardrails.validator import ArgSchemas

        ArgSchemas.vrf(vrf)
        if device.allowed_vrfs and vrf not in device.allowed_vrfs:
            raise GuardrailViolation(
                f"VRF '{vrf}' not permitted on {device.name}",
                hint="Check inventory allowed_vrfs",
            )

    async def ensure_vrf_exists(self, device: Device, vrf: str) -> None:
        self.assert_vrf_allowed(device, vrf)
        now = time.monotonic()
        cached = self.vrf_cache.get(device.name)
        ttl = self.policy.cache_vrf_list_ttl_s
        if cached and now - cached[0] < ttl:
            known = cached[1]
        else:
            result = await self.execute(device, "show vrf", tool="list_vrfs_cache")
            known = _extract_vrf_names(result.data)
            self.vrf_cache[device.name] = (now, known)
        if vrf not in known and vrf not in {"default", "management"}:
            raise GuardrailViolation(
                f"VRF '{vrf}' not found on {device.name}",
                hint=f"Known VRFs (cached): {', '.join(sorted(known)) or '(none)'}",
            )

    async def execute(
        self,
        device: Device,
        command: str,
        *,
        tool: str,
        vrf: str | None = None,
        include_raw: bool = False,
        output_format: str = "json",
        request_id: str | None = None,
    ) -> ToolResult:
        rid = request_id or str(uuid.uuid4())
        started = time.perf_counter()
        warnings: list[str] = []
        try:
            validated = self.validator.require(command)
        except GuardrailViolation as exc:
            self.audit.write(
                AuditEvent(
                    timestamp=utc_now_iso(),
                    request_id=rid,
                    mcp_client=self.mcp_client,
                    device=device.name,
                    command=command,
                    decision="blocked",
                    reason=str(exc),
                    tool=tool,
                )
            )
            raise

        if self.settings.dry_run:
            meta = ToolMeta(
                device=device.name,
                command_executed=validated,
                vrf=vrf,
                duration_ms=0,
                warnings=["dry-run: command not executed"],
                dry_run=True,
            )
            self.audit.write(
                AuditEvent(
                    timestamp=utc_now_iso(),
                    request_id=rid,
                    mcp_client=self.mcp_client,
                    device=device.name,
                    command=validated,
                    decision="allowed",
                    reason="dry_run",
                    tool=tool,
                    duration_ms=0,
                    output_size=0,
                )
            )
            return ToolResult(
                summary={"dry_run": True, "command": validated},
                data={"command": validated},
                warnings=meta.warnings,
                meta=meta,
            )

        auth = self.inventory.credentials_for(device)

        async with DeviceGate(self.limiter, device.name):
            try:
                raw = await self.client.show(
                    device,
                    validated,
                    output_format=output_format,  # type: ignore[arg-type]
                    auth=auth,
                )
            except NxosMcpError as exc:
                duration = int((time.perf_counter() - started) * 1000)
                self.audit.write(
                    AuditEvent(
                        timestamp=utc_now_iso(),
                        request_id=rid,
                        mcp_client=self.mcp_client,
                        device=device.name,
                        command=validated,
                        decision="error",
                        reason=str(exc),
                        tool=tool,
                        duration_ms=duration,
                    )
                )
                raise

        duration = int((time.perf_counter() - started) * 1000)
        redacted = self.redactor.redact(raw)
        truncated = False
        encoded = json.dumps(redacted, default=str)
        max_bytes = self.policy.limits.max_output_bytes
        if len(encoded.encode("utf-8")) > max_bytes:
            truncated = True
            warnings.append(
                f"output truncated to {max_bytes} bytes; narrow the query or use pagination"
            )
            # Keep body summary only
            redacted = _truncate_payload(redacted, max_bytes)

        self.audit.write(
            AuditEvent(
                timestamp=utc_now_iso(),
                request_id=rid,
                mcp_client=self.mcp_client,
                device=device.name,
                command=validated,
                decision="allowed",
                tool=tool,
                duration_ms=duration,
                output_size=len(encoded.encode("utf-8")),
            )
        )

        body = redacted.get("body", redacted) if isinstance(redacted, dict) else redacted
        meta = ToolMeta(
            device=device.name,
            command_executed=validated,
            vrf=vrf,
            timestamp=datetime.now(UTC),
            duration_ms=duration,
            warnings=warnings,
            truncated=truncated,
        )
        return ToolResult(
            summary=_compact_summary(body),
            data=body,
            raw=redacted if include_raw else None,
            warnings=warnings,
            truncated=truncated,
            meta=meta,
        )


def _extract_vrf_names(data: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(data, dict):
        rows = data.get("TABLE_vrf", data)
        if isinstance(rows, dict):
            row = rows.get("ROW_vrf", rows.get("ROW_vrfs"))
            if isinstance(row, dict):
                row = [row]
            if isinstance(row, list):
                for item in row:
                    if isinstance(item, dict):
                        for key in ("vrf_name", "vrf-name", "name"):
                            if key in item:
                                names.add(str(item[key]))
        for key, value in data.items():
            if key in {"vrf_name", "vrf-name", "name"} and isinstance(value, str):
                names.add(value)
            elif isinstance(value, (dict, list)):
                names |= _extract_vrf_names(value)
    elif isinstance(data, list):
        for item in data:
            names |= _extract_vrf_names(item)
    return names


def _truncate_payload(payload: Any, max_bytes: int) -> Any:
    text = json.dumps(payload, default=str)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return payload
    cut = encoded[: max_bytes - 32].decode("utf-8", errors="ignore")
    return {"truncated": True, "preview": cut}


def _compact_summary(body: Any) -> dict[str, Any]:
    if body is None or body == {} or (isinstance(body, dict) and body.get("empty")):
        return {"empty": True}
    if isinstance(body, dict):
        keys = list(body.keys())[:12]
        return {"keys": keys, "key_count": len(body)}
    if isinstance(body, list):
        return {"row_count": len(body)}
    return {"type": type(body).__name__}


def error_result(exc: Exception, *, device: str | None = None) -> dict[str, Any]:
    if isinstance(exc, NxosMcpError):
        out = exc.to_dict()
    else:
        out = {
            "error": "InternalError",
            "message": "unexpected failure",
            "hint": "Check server logs; details omitted for safety",
        }
        log.exception("unhandled_error", error=str(exc))
    if device:
        out["device"] = device
    return out
