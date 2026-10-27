# NX-OS VXLAN BGP-EVPN Troubleshooting Skills

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## When to use which skill

| Symptom | Skill | First tools |
|---------|-------|-------------|
| VNI / NVE down, no overlay BUM | `vxlan_vni_down` | `show_nve_vni`, `show_nve_peers`, `show_vni_mapping` |
| Missing EVPN type-2/type-5 | `evpn_route_missing` | `show_bgp_evpn_summary`, `show_bgp_evpn_route`, `show_vrf_rt_import_export` |
| Host unreachable in a VRF | `vrf_reachability` | `show_ip_arp_vrf`, `show_ip_route_vrf`, `ping_vrf` |
| vPC peer inconsistency / dual-home oddness | `vpc_inconsistency` | `show_vpc`, `show_vpc_consistency`, `show_port_channel_summary` |
| Duplicate MAC/IP, flapping host | `mac_ip_mobility_dup` | `show_l2route_evpn_mac`, `show_l2route_evpn_mac_ip`, `show_logging_recent` |
| VTEP peer unreachable / NVE peers down | `underlay_vtep_unreachable` | `check_vtep_reachability`, `show_ip_route_underlay`, `show_mtu_check` |

## Triggering guidance for LLMs

1. Call `list_devices` / `get_device_info` once to anchor platform and release.
2. Pick **one** skill that matches the primary symptom; do not run all skills.
3. Follow the skill's ordered steps; stop when evidence identifies a probable cause.
4. Prefer specialized tools over `run_show_command`.
5. Output: findings, evidence (device + command), probable cause, **suggested manual fix for a human** (never applied by this server).
