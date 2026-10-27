# Skill: vrf_reachability

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## Purpose
Trace per-VRF reachability hop-by-hop: ARP → local route → BGP VRF → EVPN type-5 → remote L3VNI → ping.

## When to use
- Host A in VRF cannot reach Host B / gateway / remote subnet
- Asymmetric tenant connectivity

## Inputs
- `device` (local leaf), optional remote leaf, `vrf`, `target` IP, optional `source`

## Ordered steps
1. `list_vrfs(device)` / `show_vrf_detail(device, vrf)` — VRF exists, RD/L3VNI.
2. `show_ip_arp_vrf(device, vrf, ip?)` — local ARP for destination or gateway.
   - Good: complete entry; Bad: incomplete → L2 / SVI / host issue.
3. `show_ip_route_vrf(device, vrf, prefix?)` — longest-match route and next-hop.
4. If BGP learned: `show_bgp_vrf(device, vrf, afi, prefix?)` and `show_bgp_vrf_summary`.
5. Overlay: `show_bgp_evpn_route(device, route_type="5", ...)` and remote `show_nve_vni` for L3VNI.
6. `ping_vrf(device, vrf, target)` then `traceroute_vrf` if ping fails.
7. Repeat key steps on remote leaf via `compare_vrf_across_devices` / targeted tools.

## Decision tree
- No ARP → local L2 / access / anycast GW.
- ARP yes, no route → RIB / VRF leaking / BGP.
- Route via VTEP but ping fail → underlay MTU or remote L3VNI (`underlay_vtep_unreachable`).
- Remote has no type-5 → `evpn_route_missing`.

## Common root causes
- Wrong VRF on SVI / host
- Missing redistribute / aggregate for type-5
- Firewall / ACL on border (report only)
- Anycast gateway MAC issues (`mac_ip_mobility_dup`)

## What NOT to do
- Do not change VRF context config or ACLs through this server.
- Keep ping count ≤ 5 and destinations inside allowed_prefixes.

## Output template
- Findings / Evidence / Probable cause / Suggested manual fix for operator
