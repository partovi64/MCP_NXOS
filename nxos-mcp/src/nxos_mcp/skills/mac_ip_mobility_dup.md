# Skill: mac_ip_mobility_dup

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## Purpose
Detect duplicate MAC/IP and EVPN mobility sequence problems causing flaps or blackholing.

## When to use
- Host flaps between interfaces/VTEPs
- Duplicate IP alerts / intermittent ARP
- Rapid MAC moves in logs

## Inputs
- `device`(s), `vni` / VLAN, `mac`, `ip`

## Ordered steps
1. `show_mac_address_table(device, vlan?, mac?)` on suspected leaves.
2. `show_l2route_evpn_mac(device, vni?, mac?)` — sequence / next-hop VTEP.
3. `show_l2route_evpn_mac_ip(device, vni?)` — IP↔MAC binding and duplicates.
4. `show_ip_arp_vrf(device, vrf, ip)` — ARP vs MAC-IP consistency.
5. `show_logging_recent(device, last_n=100, filter="MAC")` or `"MOVE"` / `"DUP"` (allowlisted pipe).
6. Compare across both vPC peers if dual-homed (`show_mac_address_table` both).

## Decision tree
- Same MAC on two active VTEPs with rising seq → mobility storm / loop.
- Same IP different MACs → duplicate IP on segment.
- Local MAC only, remote EVPN stale → control-plane lag (`evpn_route_missing`).

## Common root causes
- Bridging loop / mis-cabled dual attach
- VM mobility without proper EVPN mobility handling
- Rogue DHCP / IP conflict
- vPC orphan inconsistency

## What NOT to do
- Do not clear MAC/ARP/BGP via this server.
- Do not shut interfaces through this server.

## Output template
- Findings / Evidence / Probable cause / Suggested manual fix for operator
