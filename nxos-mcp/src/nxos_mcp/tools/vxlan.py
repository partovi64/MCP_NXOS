"""VXLAN / EVPN read-only tools."""

from __future__ import annotations

from typing import Any, Literal

from nxos_mcp.guardrails.validator import ArgSchemas, PingArgs, TracerouteArgs
from nxos_mcp.parsers.common import page, pick, rows, summarize_peers
from nxos_mcp.runtime import Runtime, error_result

HINTS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def register_vxlan_tools(mcp: Any, rt: Runtime) -> None:
    @mcp.tool(
        name="show_nve_peers",
        description=(
            "Show NVE peer state. Use when VTEP adjacency or VXLAN tunnel status is suspect."
        ),
        annotations={"title": "Show NVE Peers", **HINTS},
    )
    async def show_nve_peers(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            rt.assert_tool_allowed(dev, "show_nve_peers")
            # VERIFY: exact table keys vary by NX-OS release
            result = await rt.execute(
                dev, "show nve peers", tool="show_nve_peers", include_raw=include_raw
            )
            peer_rows = rows(result.data, "TABLE_nve_peers", "ROW_nve_peers")
            if not peer_rows:
                peer_rows = rows(result.data)
            summary = summarize_peers(peer_rows, ("peer-state", "state", "peer_state"))
            return {
                "summary": summary,
                "data": peer_rows,
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_nve_vni",
        description=(
            "Show NVE VNI state (Up/Down, type L2/L3). "
            "Filter by VNI when isolating one segment."
        ),
        annotations={"title": "Show NVE VNI", **HINTS},
    )
    async def show_nve_vni(
        device: str, vni: int | None = None, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            rt.assert_tool_allowed(dev, "show_nve_vni")
            cmd = f"show nve vni {ArgSchemas.vni(vni)}" if vni is not None else "show nve vni"
            result = await rt.execute(dev, cmd, tool="show_nve_vni", include_raw=include_raw)
            vni_rows = rows(result.data)
            down = [
                r
                for r in vni_rows
                if str(pick(r, "vni-state", "state", default="")).lower() not in {"up", ""}
            ]
            return {
                "summary": {"count": len(vni_rows), "not_up": len(down)},
                "data": vni_rows,
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated,
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_nve_interface",
        description=(
            "Show nve1 interface (source-interface, encapsulation). "
            "Use to verify VTEP loopback binding."
        ),
        annotations={"title": "Show NVE Interface", **HINTS},
    )
    async def show_nve_interface(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev, "show nve interface", tool="show_nve_interface", include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_nve_multisite",
        description="Show NVE multisite state. Use only on fabrics with EVPN Multi-Site.",
        annotations={"title": "Show NVE Multisite", **HINTS},
    )
    async def show_nve_multisite(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            # VERIFY: command availability depends on Multi-Site feature
            result = await rt.execute(
                dev, "show nve multisite", tool="show_nve_multisite", include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_vni_mapping",
        description=(
            "Show VLAN<->VNI and VRF<->L3VNI mappings. "
            "Use when a VNI or tenant mapping looks wrong."
        ),
        annotations={"title": "Show VNI Mapping", **HINTS},
    )
    async def show_vni_mapping(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            # VERIFY: 'show vxlan' / 'show vlan id <n>' alternatives per release
            vlan = await rt.execute(
                dev, "show vxlan", tool="show_vni_mapping", include_raw=include_raw
            )
            return {
                "summary": vlan.summary,
                "data": rows(vlan.data),
                "raw": vlan.raw,
                "warnings": [
                    *vlan.warnings,
                    "# VERIFY: show vxlan JSON schema varies; confirm on your NX-OS release",
                ],
                "truncated": vlan.truncated,
                "meta": vlan.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_bgp_evpn_summary",
        description=(
            "Show BGP L2VPN EVPN neighbor summary. "
            "Use when EVPN sessions or prefixes look wrong."
        ),
        annotations={"title": "Show BGP EVPN Summary", **HINTS},
    )
    async def show_bgp_evpn_summary(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show bgp l2vpn evpn summary",
                tool="show_bgp_evpn_summary",
                include_raw=include_raw,
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
        name="show_bgp_evpn_route",
        description=(
            "Show BGP L2VPN EVPN routes filtered by type/VNI/RD/MAC/IP. "
            "Use for missing type-2/type-5 investigations."
        ),
        annotations={"title": "Show BGP EVPN Route", **HINTS},
    )
    async def show_bgp_evpn_route(
        device: str,
        route_type: Literal["2", "3", "4", "5", "all"] = "all",
        vni: int | None = None,
        rd: str | None = None,
        mac: str | None = None,
        ip: str | None = None,
        offset: int = 0,
        limit: int = 50,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            cmd = "show bgp l2vpn evpn"
            if route_type != "all":
                # VERIFY: filter syntax; may need 'show bgp l2vpn evpn' + client-side filter
                cmd = "show bgp l2vpn evpn"
            if rd:
                if not ArgSchemas.prefix.__doc__:
                    pass
                # RD like ASN:nn or IP:nn — keep conservative charset
                if not all(c.isalnum() or c in ".:-" for c in rd):
                    raise ValueError("invalid RD")
                cmd = f"show bgp l2vpn evpn rd {rd}"
            result = await rt.execute(
                dev, cmd, tool="show_bgp_evpn_route", include_raw=include_raw
            )
            all_rows = rows(result.data)
            filtered = all_rows
            if vni is not None:
                vni_s = ArgSchemas.vni(vni)
                filtered = [r for r in filtered if vni_s in str(r)]
            if mac:
                mac_s = ArgSchemas.mac(mac)
                filtered = [r for r in filtered if mac_s.lower() in str(r).lower()]
            if ip:
                ip_s = ArgSchemas.ip(ip)
                filtered = [r for r in filtered if ip_s in str(r)]
            if route_type != "all":
                filtered = [
                r
                for r in filtered
                if f"[{route_type}]" in str(r) or f"type {route_type}" in str(r).lower()
            ]
            sliced, page_meta = page(filtered, offset=offset, limit=limit)
            return {
                "summary": {"matched": len(filtered), **page_meta},
                "data": sliced,
                "raw": result.raw,
                "warnings": [
                    *result.warnings,
                    "Client-side filters applied; prefer RD-scoped command when possible",
                ],
                "truncated": result.truncated or page_meta.get("has_more", False),
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_l2route_evpn_mac",
        description="Show l2route EVPN MAC table. Use for MAC learn/mobility issues on a VNI.",
        annotations={"title": "Show L2Route EVPN MAC", **HINTS},
    )
    async def show_l2route_evpn_mac(
        device: str,
        vni: int | None = None,
        mac: str | None = None,
        offset: int = 0,
        limit: int = 50,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            if vni is not None and mac:
                cmd = (
                    f"show l2route evpn mac evi {ArgSchemas.vni(vni)} detail"
                    f" | include {ArgSchemas.mac(mac)}"
                )
            elif vni is not None:
                cmd = f"show l2route evpn mac evi {ArgSchemas.vni(vni)}"
            else:
                cmd = "show l2route evpn mac all"
            result = await rt.execute(
                dev, cmd, tool="show_l2route_evpn_mac", include_raw=include_raw
            )
            all_rows = rows(result.data)
            sliced, page_meta = page(all_rows, offset=offset, limit=limit)
            return {
                "summary": page_meta,
                "data": sliced,
                "raw": result.raw,
                "warnings": result.warnings,
                "truncated": result.truncated or page_meta["has_more"],
                "meta": result.meta.model_dump(),
            }
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_l2route_evpn_mac_ip",
        description=(
            "Show l2route EVPN MAC-IP bindings. Use for ARP/GARP mobility and duplicate IP."
        ),
        annotations={"title": "Show L2Route EVPN MAC-IP", **HINTS},
    )
    async def show_l2route_evpn_mac_ip(
        device: str, vni: int | None = None, include_raw: bool = False
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            if vni is not None:
                cmd = f"show l2route evpn mac-ip evi {ArgSchemas.vni(vni)}"
            else:
                cmd = "show l2route evpn mac-ip all"
            result = await rt.execute(
                dev, cmd, tool="show_l2route_evpn_mac_ip", include_raw=include_raw
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
        name="show_l2route_topology",
        description="Show l2route topology summary. Use for overlay control-plane health overview.",
        annotations={"title": "Show L2Route Topology", **HINTS},
    )
    async def show_l2route_topology(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            result = await rt.execute(
                dev,
                "show l2route topology detail",
                tool="show_l2route_topology",
                include_raw=include_raw,
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="show_evpn_esi",
        description=(
            "Show EVPN Ethernet Segment (ESI) state. "
            "Use for EVPN multihoming / ESI issues."
        ),
        annotations={"title": "Show EVPN ESI", **HINTS},
    )
    async def show_evpn_esi(device: str, include_raw: bool = False) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            # VERIFY: command name may be 'show bgp l2vpn evpn es' depending on release
            result = await rt.execute(
                dev, "show evpn ethernet-segment", tool="show_evpn_esi", include_raw=include_raw
            )
            return result.model_dump()
        except Exception as exc:
            return error_result(exc, device=device)

    @mcp.tool(
        name="check_vtep_reachability",
        description=(
            "Ping/traceroute a peer VTEP IP in the underlay VRF (bounded). "
            "Use when NVE peers are down or overlay fails but underlay is suspect."
        ),
        annotations={"title": "Check VTEP Reachability", **HINTS},
    )
    async def check_vtep_reachability(
        device: str,
        peer_ip: str,
        do_traceroute: bool = False,
        source: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        try:
            dev = rt.get_device(device)
            underlay = dev.underlay_vrf or "default"
            await rt.ensure_vrf_exists(dev, underlay)
            ping_cmd = rt.validator.build_ping(
                PingArgs(target=peer_ip, vrf=underlay, count=3, timeout=2, source=source)
            )
            ping = await rt.execute(
                dev, ping_cmd, tool="check_vtep_reachability", vrf=underlay, include_raw=include_raw
            )
            out: dict[str, Any] = {
                "summary": {"ping": ping.summary, "underlay_vrf": underlay},
                "data": {"ping": ping.data},
                "warnings": ping.warnings,
                "truncated": ping.truncated,
                "meta": ping.meta.model_dump(),
            }
            if do_traceroute:
                tr_cmd = rt.validator.build_traceroute(
                    TracerouteArgs(target=peer_ip, vrf=underlay, source=source)
                )
                tr = await rt.execute(
                    dev,
                    tr_cmd,
                    tool="check_vtep_reachability",
                    vrf=underlay,
                    include_raw=include_raw,
                )
                out["data"]["traceroute"] = tr.data
                out["warnings"] = out["warnings"] + tr.warnings
            return out
        except Exception as exc:
            return error_result(exc, device=device)
