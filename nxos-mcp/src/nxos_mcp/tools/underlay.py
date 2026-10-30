"""Underlay routing / BFD / MTU tools."""

from __future__ import annotations

from typing import Any

from nxos_mcp.parsers.common import rows, summarize_peers
from nxos_mcp.runtime import Runtime, error_result

HINTS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def register_underlay_tools(mcp: Any, rt: Runtime) -> None:
    @mcp.tool(
        name="show_ospf_neighbors",
        description=(
            "Show OSPF neighbors. Use when underlay is OSPF and adjacency/VTEP "
            "reachability fails."
        ),
        annotations={"title": "Show OSPF Neighbors", **HINTS},
    )
    async def show_ospf_neighbors(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show ip ospf neighbors", tool="show_ospf_neighbors", include_raw=include_raw
            )
            peer_rows = rows(result.data)
            return {
                "summary": summarize_peers(peer_rows, ("state", "neighborstate")),
                "data": peer_rows,
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_isis_adjacency",
        description="Show IS-IS adjacency. Use when underlay is IS-IS.",
        annotations={"title": "Show IS-IS Adjacency", **HINTS},
    )
    async def show_isis_adjacency(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show isis adjacency", tool="show_isis_adjacency", include_raw=include_raw
            )
            return {
                "summary": summarize_peers(rows(result.data), ("state", "adj_state")),
                "data": rows(result.data),
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_bgp_ipv4_summary",
        description=(
            "Show BGP IPv4 unicast summary (underlay eBGP). "
            "Use for underlay BGP session health."
        ),
        annotations={"title": "Show BGP IPv4 Summary", **HINTS},
    )
    async def show_bgp_ipv4_summary(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show bgp ipv4 unicast summary",
                tool="show_bgp_ipv4_summary",
                include_raw=include_raw,
            )
            return {
                "summary": summarize_peers(rows(result.data), ("state",)),
                "data": rows(result.data),
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_bfd_neighbors",
        description=(
            "Show BFD neighbors. Use when underlay sessions flap or ECMP paths look unstable."
        ),
        annotations={"title": "Show BFD Neighbors", **HINTS},
    )
    async def show_bfd_neighbors(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show bfd neighbors", tool="show_bfd_neighbors", include_raw=include_raw
            )
            return {
                "summary": summarize_peers(rows(result.data), ("state", "session_state")),
                "data": rows(result.data),
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_ip_route_underlay",
        description=(
            "Show default-VRF IPv4 routes (optional prefix). "
            "Use for VTEP loopback reachability in underlay."
        ),
        annotations={"title": "Show IP Route Underlay", **HINTS},
    )
    async def show_ip_route_underlay(
        device: str, prefix: str | None = None, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            from nxos_mcp.guardrails.validator import ArgSchemas

            dev = rt.get_device(device)
            cmd = f"show ip route {ArgSchemas.prefix(prefix)}" if prefix else "show ip route"
            result = await rt.execute(
                dev, cmd, tool="show_ip_route_underlay", vrf="default", include_raw=include_raw
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
        name="show_mtu_check",
        description=(
            "Show interface MTU for underlay links. Use when VXLAN needs jumbo (≥9216) and "
            "fragmentation/blackholing is suspected."
        ),
        annotations={"title": "Show MTU Check", **HINTS},
    )
    async def show_mtu_check(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show interface status",
                tool="show_mtu_check",
                include_raw=include_raw,
            )
            # Also pull brief MTU from running interface view when possible
            mtu = await rt.execute(
                dev, "show interface brief", tool="show_mtu_check", include_raw=include_raw
            )
            return {
                "summary": {
                    "note": "Review MTU ≥ 9216 on underlay interfaces for VXLAN",
                    "status_rows": len(rows(result.data)),
                    "brief_rows": len(rows(mtu.data)),
                },
                "data": {"status": rows(result.data), "brief": rows(mtu.data)},
                "warnings": result.warnings
                + mtu.warnings
                + ["# VERIFY: prefer 'show interface EthernetX/Y' for exact MTU per link"],
                "truncated": result.truncated or mtu.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)
