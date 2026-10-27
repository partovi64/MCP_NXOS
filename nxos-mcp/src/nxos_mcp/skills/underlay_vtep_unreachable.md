# Skill: underlay_vtep_unreachable

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## Purpose
Restore understanding of why a VTEP loopback is unreachable across the underlay (OSPF/IS-IS/eBGP).

## When to use
- `show nve peers` Down
- Overlay fails but tenant VRF looks locally fine
- Suspected MTU / ECMP / BFD issue

## Inputs
- `device`, `peer_ip` (remote VTEP loopback), underlay IGP type

## Ordered steps
1. `show_nve_interface(device)` — local VTEP IP / source loopback.
2. `show_ip_route_underlay(device, prefix=peer_ip/32)` — route exists, ECMP next-hops.
3. `check_vtep_reachability(device, peer_ip, do_traceroute=true)` — bounded underlay ping/trace.
4. Underlay protocol:
   - OSPF: `show_ospf_neighbors`
   - IS-IS: `show_isis_adjacency`
   - eBGP: `show_bgp_ipv4_summary`
5. `show_bfd_neighbors(device)` if BFD enabled.
6. `show_mtu_check(device)` — look for underlay MTU < 9216.
7. `show_interface_counters_errors` on underlay links with errors.

## Decision tree
- No /32 route → IGP/BGP advertisement of loopback.
- Route yes, ping fail → ACL, RPF, or dataplane.
- Ping small ok, large fail → MTU / jumbo missing.
- Neighbors flap → BFD / physical / ECMP asymmetry.

## Common root causes
- Loopback not in IGP
- Underlay MTU not jumbo end-to-end
- ECMP member blackhole
- Spine filter on VTEP prefixes

## What NOT to do
- Do not change MTU, IGP, or BFD via this server.
- Keep probes inside allowed_prefixes and rate limits.

## Output template
- Findings / Evidence / Probable cause / Suggested manual fix for operator
