"""MCP resources and prompts (skills)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from nxos_mcp.runtime import Runtime

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

SKILL_NAMES = [
    "vxlan_vni_down",
    "evpn_route_missing",
    "vrf_reachability",
    "vpc_inconsistency",
    "mac_ip_mobility_dup",
    "underlay_vtep_unreachable",
]

COMMAND_CATALOG = [
    {"tool": "list_devices", "category": "generic"},
    {"tool": "get_device_info", "category": "generic"},
    {"tool": "run_show_command", "category": "generic"},
    {"tool": "run_show_multi", "category": "generic"},
    {"tool": "show_nve_peers", "category": "vxlan"},
    {"tool": "show_nve_vni", "category": "vxlan"},
    {"tool": "show_nve_interface", "category": "vxlan"},
    {"tool": "show_nve_multisite", "category": "vxlan"},
    {"tool": "show_vni_mapping", "category": "vxlan"},
    {"tool": "show_bgp_evpn_summary", "category": "vxlan"},
    {"tool": "show_bgp_evpn_route", "category": "vxlan"},
    {"tool": "show_l2route_evpn_mac", "category": "vxlan"},
    {"tool": "show_l2route_evpn_mac_ip", "category": "vxlan"},
    {"tool": "show_l2route_topology", "category": "vxlan"},
    {"tool": "show_evpn_esi", "category": "vxlan"},
    {"tool": "check_vtep_reachability", "category": "vxlan"},
    {"tool": "list_vrfs", "category": "vrf"},
    {"tool": "show_vrf_detail", "category": "vrf"},
    {"tool": "show_ip_route_vrf", "category": "vrf"},
    {"tool": "show_ip_arp_vrf", "category": "vrf"},
    {"tool": "show_ipv6_neighbor_vrf", "category": "vrf"},
    {"tool": "show_bgp_vrf", "category": "vrf"},
    {"tool": "show_bgp_vrf_summary", "category": "vrf"},
    {"tool": "ping_vrf", "category": "vrf"},
    {"tool": "traceroute_vrf", "category": "vrf"},
    {"tool": "compare_vrf_across_devices", "category": "vrf"},
    {"tool": "show_vrf_rt_import_export", "category": "vrf"},
    {"tool": "show_ospf_neighbors", "category": "underlay"},
    {"tool": "show_isis_adjacency", "category": "underlay"},
    {"tool": "show_bgp_ipv4_summary", "category": "underlay"},
    {"tool": "show_bfd_neighbors", "category": "underlay"},
    {"tool": "show_ip_route_underlay", "category": "underlay"},
    {"tool": "show_mtu_check", "category": "underlay"},
    {"tool": "show_vpc", "category": "vpc_l2"},
    {"tool": "show_vpc_consistency", "category": "vpc_l2"},
    {"tool": "show_port_channel_summary", "category": "vpc_l2"},
    {"tool": "show_spanning_tree_vlan", "category": "vpc_l2"},
    {"tool": "show_mac_address_table", "category": "vpc_l2"},
    {"tool": "show_interface_status", "category": "vpc_l2"},
    {"tool": "show_interface_counters_errors", "category": "vpc_l2"},
    {"tool": "show_system_resources", "category": "health"},
    {"tool": "show_logging_recent", "category": "health"},
    {"tool": "show_module", "category": "health"},
    {"tool": "show_environment", "category": "health"},
]


def read_skill(name: str) -> str:
    path = SKILLS_DIR / f"{name}.md"
    if name == "index":
        path = SKILLS_DIR / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"skill not found: {name}")
    return path.read_text(encoding="utf-8")


def register_resources_and_prompts(mcp: Any, rt: Runtime) -> None:
    @mcp.resource("nxos://inventory")
    def inventory_resource() -> str:
        devices = [
            {
                "name": d.name,
                "host": d.host,
                "role": d.role,
                "site": d.site,
                "platform": d.platform,
                "tags": d.tags,
                "vrfs": d.vrfs,
            }
            for d in rt.inventory.devices
        ]
        return yaml.safe_dump({"devices": devices}, sort_keys=False)

    @mcp.resource("nxos://guardrails/policy")
    def guardrails_resource() -> str:
        return yaml.safe_dump(rt.policy.model_dump(), sort_keys=False)

    @mcp.resource("nxos://commands/catalog")
    def catalog_resource() -> str:
        return yaml.safe_dump({"tools": COMMAND_CATALOG}, sort_keys=False)

    @mcp.resource("nxos://skills/index")
    def skills_index() -> str:
        return read_skill("index")

    for skill in SKILL_NAMES:
        _attach_skill(mcp, skill)


def _attach_skill(mcp: Any, skill: str) -> None:
    def make_reader(name: str) -> Callable[[], str]:
        def _reader() -> str:
            return read_skill(name)

        _reader.__name__ = f"skill_resource_{name}"
        return _reader

    mcp.resource(f"nxos://skills/{skill}")(make_reader(skill))

    def make_prompt(name: str) -> Callable[[], str]:
        def _prompt() -> str:
            return read_skill(name)

        _prompt.__name__ = f"skill_prompt_{name}"
        return _prompt

    mcp.prompt(name=skill)(make_prompt(skill))
