"""vPC, STP, MAC, port-channel, interface tools."""

from __future__ import annotations

from typing import Any

from nxos_mcp.guardrails.validator import ArgSchemas
from nxos_mcp.parsers.common import page, rows
from nxos_mcp.runtime import Runtime, error_result

HINTS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def register_vpc_l2_tools(mcp: Any, rt: Runtime) -> None:
    @mcp.tool(
        name="show_vpc",
        description="Show vPC status (peer-link, keepalive, role). Use for dual-homed leaf issues.",
        annotations={"title": "Show vPC", **HINTS},
    )
    async def show_vpc(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(dev, "show vpc", tool="show_vpc", include_raw=include_raw)
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_vpc_consistency",
        description=(
            "Show vPC consistency parameters (type-1/type-2). "
            "Use when vPC is up but forwarding is asymmetric."
        ),
        annotations={"title": "Show vPC Consistency", **HINTS},
    )
    async def show_vpc_consistency(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            # VERIFY: 'show vpc consistency-parameters global' vs per-interface
            result = await rt.execute(
                dev,
                "show vpc consistency-parameters global",
                tool="show_vpc_consistency",
                include_raw=include_raw,
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_port_channel_summary",
        description="Show port-channel summary. Use for peer-link / dual-attach member issues.",
        annotations={"title": "Show Port-Channel Summary", **HINTS},
    )
    async def show_port_channel_summary(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show port-channel summary",
                tool="show_port_channel_summary",
                include_raw=include_raw,
            )
            return {
                "summary": {"rows": len(rows(result.data))},
                "data": rows(result.data),
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_spanning_tree_vlan",
        description="Show STP for a VLAN. Use when L2 loops or blocked ports affect a segment.",
        annotations={"title": "Show Spanning Tree VLAN", **HINTS},
    )
    async def show_spanning_tree_vlan(
        device: str, vlan: int, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            cmd = f"show spanning-tree vlan {ArgSchemas.vlan(vlan)}"
            result = await rt.execute(
                dev, cmd, tool="show_spanning_tree_vlan", include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_mac_address_table",
        description=(
            "Show MAC address table filtered by VLAN/MAC/interface. Use for L2 location of a host."
        ),
        annotations={"title": "Show MAC Address Table", **HINTS},
    )
    async def show_mac_address_table(
        device: str,
        vlan: int | None = None,
        mac: str | None = None,
        interface: str | None = None,
        offset: int = 0,
        limit: int = 50,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            if mac:
                cmd = f"show mac address-table address {ArgSchemas.mac(mac)}"
            elif vlan is not None:
                cmd = f"show mac address-table vlan {ArgSchemas.vlan(vlan)}"
            elif interface:
                cmd = f"show mac address-table interface {ArgSchemas.iface(interface)}"
            else:
                cmd = "show mac address-table"
            result = await rt.execute(
                dev, cmd, tool="show_mac_address_table", include_raw=include_raw
            )
            all_rows = rows(result.data)
            sliced, meta = page(all_rows, offset=offset, limit=limit)
            return {
                "summary": meta,
                "data": sliced,
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated or meta["has_more"],
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_interface_status",
        description="Show interface status table. Use for quick link-up / VLAN / duplex survey.",
        annotations={"title": "Show Interface Status", **HINTS},
    )
    async def show_interface_status(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show interface status", tool="show_interface_status", include_raw=include_raw
            )
            return {
                "summary": {"rows": len(rows(result.data))},
                "data": rows(result.data),
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_interface_counters_errors",
        description=(
            "Show interface error counters. Use for CRC/input errors correlating with loss."
        ),
        annotations={"title": "Show Interface Counters Errors", **HINTS},
    )
    async def show_interface_counters_errors(
        device: str, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show interface counters errors",
                tool="show_interface_counters_errors",
                include_raw=include_raw,
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)
