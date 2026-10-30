"""Device health / logging tools."""

from __future__ import annotations

from typing import Any

from nxos_mcp.nxapi.errors import GuardrailViolation
from nxos_mcp.runtime import Runtime, error_result

HINTS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def register_health_tools(mcp: Any, rt: Runtime) -> None:
    @mcp.tool(
        name="show_system_resources",
        description="Show CPU/memory resources. Use when control-plane stress may explain flaps.",
        annotations={"title": "Show System Resources", **HINTS},
    )
    async def show_system_resources(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show system resources",
                tool="show_system_resources",
                include_raw=include_raw,
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_logging_recent",
        description=(
            "Show recent syslog lines (last_n<=200, optional include filter). "
            "Use for event correlation."
        ),
        annotations={"title": "Show Logging Recent", **HINTS},
    )
    async def show_logging_recent(
        device: str,
        last_n: int = 50,
        filter: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            lim = rt.policy.limits.log_last_n_max
            if last_n < 1 or last_n > lim:
                raise GuardrailViolation(f"last_n must be 1..{lim}")
            dev = rt.get_device(device)
            cmd = f"show logging last {last_n}"
            if filter:
                # Pipe include with charset validation via validator
                # Escape by restricting charset in require()
                cmd = f"show logging last {last_n} | include {filter}"
            result = await rt.execute(dev, cmd, tool="show_logging_recent", include_raw=include_raw)
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_module",
        description="Show module status. Use for hardware / linecard faults.",
        annotations={"title": "Show Module", **HINTS},
    )
    async def show_module(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show module", tool="show_module", include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_environment",
        description="Show environment (power/fan/temp). Use for hardware environmental alarms.",
        annotations={"title": "Show Environment", **HINTS},
    )
    async def show_environment(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show environment", tool="show_environment", include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)
