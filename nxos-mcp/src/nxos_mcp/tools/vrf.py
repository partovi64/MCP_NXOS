"""Per-VRF L3 troubleshooting tools."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from nxos_mcp.guardrails.validator import ArgSchemas, PingArgs, TracerouteArgs
from nxos_mcp.nxapi.errors import GuardrailViolation
from nxos_mcp.parsers.common import page, rows
from nxos_mcp.runtime import Runtime, error_result

HINTS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def register_vrf_tools(mcp: Any, rt: Runtime) -> None:
    @mcp.tool(
        name="list_vrfs",
        description=(
            "List VRFs with state. Use to discover tenant VRFs and L3 context before per-VRF tools."
        ),
        annotations={"title": "List VRFs", **HINTS},
    )
    async def list_vrfs(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(dev, "show vrf", tool="list_vrfs", include_raw=include_raw)
            vrf_rows = rows(result.data, "TABLE_vrf", "ROW_vrf")
            if not vrf_rows:
                vrf_rows = rows(result.data)
            return {
                "summary": {"count": len(vrf_rows)},
                "data": vrf_rows,
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_vrf_detail",
        description="Show VRF detail (RD, interfaces). Use when validating a single tenant VRF.",
        annotations={"title": "Show VRF Detail", **HINTS},
    )
    async def show_vrf_detail(device: str, vrf: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            result = await rt.execute(
                dev,
                f"show vrf {vrf_s} detail",
                tool="show_vrf_detail",
                vrf=vrf_s,
                include_raw=include_raw,
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_ip_route_vrf",
        description=(
            "Show IPv4 routes in a VRF (optional prefix). Use for blackhole / missing route checks."
        ),
        annotations={"title": "Show IP Route VRF", **HINTS},
    )
    async def show_ip_route_vrf(
        device: str,
        vrf: str,
        prefix: str | None = None,
        offset: int = 0,
        limit: int = 50,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            if prefix:
                cmd = f"show ip route {ArgSchemas.prefix(prefix)} vrf {vrf_s}"
            else:
                cmd = f"show ip route vrf {vrf_s}"
            result = await rt.execute(
                dev, cmd, tool="show_ip_route_vrf", vrf=vrf_s, include_raw=include_raw
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
        name="show_ip_arp_vrf",
        description="Show ARP in a VRF (optional IP). Use early in host reachability workflows.",
        annotations={"title": "Show IP ARP VRF", **HINTS},
    )
    async def show_ip_arp_vrf(
        device: str, vrf: str, ip: str | None = None, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            if ip:
                cmd = f"show ip arp {ArgSchemas.ip(ip)} vrf {vrf_s}"
            else:
                cmd = f"show ip arp vrf {vrf_s}"
            result = await rt.execute(
                dev, cmd, tool="show_ip_arp_vrf", vrf=vrf_s, include_raw=include_raw
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
        name="show_ipv6_neighbor_vrf",
        description="Show IPv6 neighbors in a VRF. Use for IPv6 overlay host issues.",
        annotations={"title": "Show IPv6 Neighbor VRF", **HINTS},
    )
    async def show_ipv6_neighbor_vrf(
        device: str, vrf: str, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            result = await rt.execute(
                dev,
                f"show ipv6 neighbor vrf {vrf_s}",
                tool="show_ipv6_neighbor_vrf",
                vrf=vrf_s,
                include_raw=include_raw,
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_bgp_vrf_summary",
        description=(
            "Show BGP summary for a VRF address-family. Use to check PE-CE / overlay BGP sessions."
        ),
        annotations={"title": "Show BGP VRF Summary", **HINTS},
    )
    async def show_bgp_vrf_summary(
        device: str,
        vrf: str,
        afi: Literal["ipv4", "ipv6"] = "ipv4",
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            cmd = f"show bgp {afi} unicast summary vrf {vrf_s}"
            result = await rt.execute(
                dev, cmd, tool="show_bgp_vrf_summary", vrf=vrf_s, include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_bgp_vrf",
        description=(
            "Show BGP routes in a VRF AF (optional prefix). Use after local RIB checks fail."
        ),
        annotations={"title": "Show BGP VRF", **HINTS},
    )
    async def show_bgp_vrf(
        device: str,
        vrf: str,
        afi: Literal["ipv4", "ipv6"] = "ipv4",
        prefix: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            if prefix:
                cmd = f"show bgp {afi} unicast {ArgSchemas.prefix(prefix)} vrf {vrf_s}"
            else:
                cmd = f"show bgp {afi} unicast vrf {vrf_s}"
            result = await rt.execute(
                dev, cmd, tool="show_bgp_vrf", vrf=vrf_s, include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="ping_vrf",
        description=(
            "Bounded ping inside a VRF (count≤5, timeout≤2s). VRF required. "
            "Use to verify host/gateway reachability after ARP/route checks."
        ),
        annotations={"title": "Ping VRF", **HINTS},
    )
    async def ping_vrf(
        device: str,
        vrf: str,
        target: str,
        count: int = 2,
        timeout: int = 2,
        size: int = 100,
        source: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            lim = rt.policy.limits
            if (
                count > lim.ping_count_max
                or timeout > lim.ping_timeout_max_s
                or size > lim.ping_size_max
            ):
                raise GuardrailViolation("ping parameters exceed policy limits")
            dev = rt.get_device(device)
            await rt.ensure_vrf_exists(dev, ArgSchemas.vrf(vrf))
            cmd = rt.validator.build_ping(
                PingArgs(
                    target=target, vrf=vrf, count=count, timeout=timeout, size=size, source=source
                )
            )
            result = await rt.execute(dev, cmd, tool="ping_vrf", vrf=vrf, include_raw=include_raw)
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="traceroute_vrf",
        description="Traceroute inside a VRF. Use after ping fails to locate the path break.",
        annotations={"title": "Traceroute VRF", **HINTS},
    )
    async def traceroute_vrf(
        device: str,
        vrf: str,
        target: str,
        source: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            await rt.ensure_vrf_exists(dev, ArgSchemas.vrf(vrf))
            cmd = rt.validator.build_traceroute(
                TracerouteArgs(target=target, vrf=vrf, source=source)
            )
            result = await rt.execute(
                dev, cmd, tool="traceroute_vrf", vrf=vrf, include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_vrf_rt_import_export",
        description=(
            "Show VRF route-target import/export. Use for EVPN type-5 / inter-VRF RT mismatch."
        ),
        annotations={"title": "Show VRF RT Import/Export", **HINTS},
    )
    async def show_vrf_rt_import_export(
        device: str, vrf: str, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            vrf_s = ArgSchemas.vrf(vrf)
            await rt.ensure_vrf_exists(dev, vrf_s)
            # VERIFY: 'show vrf context' / detail carries RTs on many releases
            result = await rt.execute(
                dev,
                f"show vrf {vrf_s} detail",
                tool="show_vrf_rt_import_export",
                vrf=vrf_s,
                include_raw=include_raw,
            )
            return {
                **result.model_dump(),
                "warnings": [
                    *result.warnings,
                    "# VERIFY: parse RT fields from detail JSON for your NX-OS release",
                ],
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="compare_vrf_across_devices",
        description=(
            "Compare VRF presence / detail across devices (bounded fan-out). "
            "Use for RT/L3VNI consistency across leaves."
        ),
        annotations={"title": "Compare VRF Across Devices", **HINTS},
    )
    async def compare_vrf_across_devices(
        devices: list[str], vrf: str, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            vrf_s = ArgSchemas.vrf(vrf)
            max_n = rt.policy.limits.max_fanout_devices
            if len(devices) > max_n:
                raise GuardrailViolation(f"fan-out limited to {max_n} devices")

            async def one(name: str) -> dict[str, Any]:
                try:
                    dev = rt.get_device(name)
                    await rt.ensure_vrf_exists(dev, vrf_s)
                    res = await rt.execute(
                        dev,
                        f"show vrf {vrf_s} detail",
                        tool="compare_vrf_across_devices",
                        vrf=vrf_s,
                        include_raw=include_raw,
                    )
                    return {"device": name, "ok": True, "data": res.data, "summary": res.summary}
                except Exception as exc:
                    return {"device": name, "ok": False, "error": error_result(exc, device=name)}

            results = await asyncio.gather(*[one(n) for n in devices])
            ok = [r for r in results if r.get("ok")]
            return {
                "summary": {
                    "vrf": vrf_s,
                    "devices": len(results),
                    "ok": len(ok),
                    "failed": len(results) - len(ok),
                    "note": (
                        "Compare RD/RT/L3VNI fields manually from data; schema varies by release"
                    ),
                },
                "data": results,
                "warnings": [],
                "truncated": False,
            }
        except Exception as exc:
            return error_result(exc)
