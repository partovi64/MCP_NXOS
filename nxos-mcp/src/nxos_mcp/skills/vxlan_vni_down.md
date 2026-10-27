# Skill: vxlan_vni_down

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## Purpose
Diagnose why an NVE VNI is Down or not forwarding in a VXLAN BGP-EVPN fabric.

## When to use
- `show nve vni` shows Down / AdminDown
- Hosts in a VLAN/VNI cannot flood or learn MACs across VTEPs
- New VNI recently provisioned

## Inputs
- `device` (leaf preferred)
- optional `vni`, peer VTEP IP, site

## Ordered steps
1. `get_device_info(device)` — confirm `nv overlay` / `nve` features.
   - Good: features enabled; Bad: feature missing → stop, report to operator.
2. `show_nve_interface(device)` — source-interface / encapsulation.
   - Good: nve1 up, loopback bound; Bad: interface down or no source.
3. `show_nve_vni(device, vni?)` — VNI state and type (L2/L3).
   - Good: Up; Bad: Down → continue.
4. `show_vni_mapping(device)` — VLAN↔VNI and VRF↔L3VNI.
   - Good: expected mapping present; Bad: missing/mismatched mapping.
5. `show_nve_peers(device)` — peer Up.
   - Good: peer Up; Bad: peer Down → switch to `underlay_vtep_unreachable`.
6. Flooding path: `run_show_command` with `show nve vni <vni> detail` (validated) for IR vs mcast group.
   - Good: ingress-replication peers or mcast group present; Bad: empty flood list.
7. Optional: `show_bgp_evpn_route(device, route_type="3", vni=...)` for IMET/type-3.

## Decision tree
- VNI Down + mapping missing → provisioning gap (operator config).
- VNI Down + peers Down → underlay/VTEP.
- VNI Up + no flood list → BUM replication design issue.
- L3VNI Down → check VRF / BGP EVPN (`evpn_route_missing`).

## Common root causes
- Missing VLAN–VNI mapping or SVI/anycast GW
- NVE source loopback not advertised in underlay
- Ingress-replication peers not learned (BGP EVPN)
- Multicast underlay BUM broken (if used)

## What NOT to do
- Do not `clear`, `reload`, or change `nve` / `evpn` config via this server.
- Do not run `show tech-support`.

## Output template
- Findings:
- Evidence (device, command, key fields):
- Probable cause:
- Suggested manual fix (for human operator):
