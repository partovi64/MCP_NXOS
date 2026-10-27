"""Generic inventory and show-command tools."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from pydantic import BaseModel, Field

from nxos_mcp.guardrails.validator import ArgSchemas
from nxos_mcp.nxapi.errors import GuardrailViolation
from nxos_mcp.parsers.common import rows
from nxos_mcp.runtime import Runtime, error_result


class ListDevicesArgs(BaseModel):
    role: str | None = None
    site: str | None = None


class DeviceArg(BaseModel):
    device: str


class RunShowArgs(BaseModel):
    device: str
    command: str = Field(..., min_length=1, max_length=512)
    output_format: Literal["json", "text"] = "json"
    include_raw: bool = False


class RunShowMultiArgs(BaseModel):
    devices: list[str] = Field(..., min_length=1)
    command: str = Field(..., min_length=1, max_length=512)
    include_raw: bool = False


def register_generic_tools(mcp: Any, rt: Runtime) -> None:
    @mcp.tool(
        name="list_devices",
        description=(
            "List inventoried NX-OS devices. Use first to discover names, roles "
            "(spine/leaf/border), and sites before other tools."
        ),
        annotations={
            "title": "List Devices",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_devices(role: str | None = None, site: str | None = None) -> dict[str, Any]:
        devices = rt.inventory.list(role=role, site=site)
        return {
            "summary": {"count": len(devices)},
            "data": [
                {
                    "name": d.name,
                    "host": d.host,
                    "role": d.role,
                    "site": d.site,
                    "platform": d.platform,
                    "tags": d.tags,
                }
                for d in devices
            ],
            "warnings": [],
            "truncated": False,
        }

    @mcp.tool(
        name="get_device_info",
        description=(
            "Collect version, uptime/hostname, and feature flags (nv overlay, bgp, vpc, nxapi). "
            "Use at the start of troubleshooting to confirm platform/release."
        ),
        annotations={
            "title": "Get Device Info",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_device_info(device: str) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            rt.assert_tool_allowed(dev, "get_device_info")
            ver = await rt.execute(dev, "show version", tool="get_device_info")
            # VERIFY: feature list command varies slightly by release
            feat = await rt.execute(dev, "show feature | include nxapi|nve|bgp|vpc|nv", tool="get_device_info")
            summary = {
                "version_keys": ver.summary,
                "features_snippet": feat.summary,
            }
            return {
                "summary": summary,
                "data": {"version": ver.data, "features": feat.data},
                "raw": None,
                "warnings": ver.warnings + feat.warnings,
                "truncated": ver.truncated or feat.truncated,
                "meta": ver.meta.model_dump(),
            }
        except Exception as exc:  # noqa: BLE001
            return error_result(exc, device=device)

    @mcp.tool(
        name="run_show_command",
        description=(
            "Run a single validated show/ping/traceroute command on one device. "
            "Prefer specialized tools when available; use this for ad-hoc read-only queries."
        ),
        annotations={
            "title": "Run Show Command",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def run_show_command(
        device: str,
        command: str,
        output_format: Literal["json", "text"] = "json",
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            args = RunShowArgs(
                device=device, command=command, output_format=output_format, include_raw=include_raw
            )
            dev = rt.get_device(args.device)
            rt.assert_tool_allowed(dev, "run_show_command")
            result = await rt.execute(
                dev,
                args.command,
                tool="run_show_command",
                include_raw=args.include_raw,
                output_format=args.output_format,
            )
            return result.model_dump()
        except Exception as exc:  # noqa: BLE001
            return error_result(exc, device=device)

    @mcp.tool(
        name="run_show_multi",
        description=(
            "Fan-out one validated show command to multiple devices (bounded). "
            "Use for fabric-wide consistency checks."
        ),
        annotations={
            "title": "Run Show Multi",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def run_show_multi(
        devices: list[str],
        command: str,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            args = RunShowMultiArgs(devices=devices, command=command, include_raw=include_raw)
            max_n = rt.policy.limits.max_fanout_devices
            if len(args.devices) > max_n:
                raise GuardrailViolation(
                    f"fan-out limited to {max_n} devices",
                    hint="Split the device list or raise max_fanout_devices",
                )
            # Validate once
            rt.validator.require(args.command)

            async def one(name: str) -> dict[str, Any]:
                try:
                    dev = rt.get_device(name)
                    rt.assert_tool_allowed(dev, "run_show_multi")
                    res = await rt.execute(
                        dev,
                        args.command,
                        tool="run_show_multi",
                        include_raw=args.include_raw,
                    )
                    return {"device": name, "ok": True, "result": res.model_dump()}
                except Exception as exc:  # noqa: BLE001
                    return {"device": name, "ok": False, "error": error_result(exc, device=name)}

            results = await asyncio.gather(*[one(n) for n in args.devices])
            ok = sum(1 for r in results if r.get("ok"))
            return {
                "summary": {"devices": len(results), "ok": ok, "failed": len(results) - ok},
                "data": results,
                "warnings": [],
                "truncated": False,
            }
        except Exception as exc:  # noqa: BLE001
            return error_result(exc)
