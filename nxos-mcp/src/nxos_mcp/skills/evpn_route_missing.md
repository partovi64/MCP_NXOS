# Skill: evpn_route_missing

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## Purpose
Find why an EVPN type-2 (MAC/IP) or type-5 (IP prefix) route is missing on a VTEP.

## When to use
- Remote MAC/IP not in `l2route` / BGP EVPN
- Inter-VRF or tenant prefix not learned
- RT mismatch suspected after VRF change

## Inputs
- `device`, optional peer device, `vni` / `vrf`, `mac` / `ip` / `rd`

## Ordered steps
1. `show_bgp_evpn_summary(device)` — sessions Established, prefixes > 0.
2. `show_bgp_evpn_route(device, route_type, vni?, rd?, mac?, ip?)` — route present locally?
3. On ingress VTEP (where host lives): `show_l2route_evpn_mac` / `show_l2route_evpn_mac_ip`.
4. `show_vrf_rt_import_export(device, vrf)` and `compare_vrf_across_devices` for RT/RD consistency.
5. `show_nve_vni(device, vni)` — VNI Up and correct type.
6. `run_show_command` only if needed: `show bgp l2vpn evpn <prefix> detail` (allowlisted show).

## Decision tree
- BGP EVPN neighbors Down → underlay / BGP peering first.
- Route on source VTEP but not remote → RT import/export or RD.
- Type-2 missing + MAC local only → EVPN advertisement / VLAN–VNI.
- Type-5 missing → VRF BGP / redistribute / L3VNI.

## Common root causes
- RT import/export mismatch between VRFs
- Route-map / table-map filtering (report as hypothesis; do not change)
- VNI or VRF not associated to NVE
- Spine not reflecting EVPN (RR) sessions

## What NOT to do
- Never edit route-maps or BGP via this server.
- Do not clear BGP sessions.

## Output template
- Findings / Evidence / Probable cause / Suggested manual fix for operator
