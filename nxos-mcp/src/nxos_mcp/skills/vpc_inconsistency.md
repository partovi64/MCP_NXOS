# Skill: vpc_inconsistency

Never propose or execute config changes through this server. Provide recommended changes as text for the operator.

## Purpose
Diagnose vPC type-1/type-2 inconsistency, peer-link/keepalive issues, and dual-homed VTEP anomalies.

## When to use
- vPC member suspended / consistency failed
- Dual-homed host sees asymmetric MAC or ARP
- Peer-link or keepalive Down

## Inputs
- Primary and secondary vPC peers (`device` pair)

## Ordered steps
1. `show_vpc(device)` on both peers — role, peer-link, keepalive, vPC peer status.
2. `show_vpc_consistency(device)` — type-1 global parameters.
3. `show_port_channel_summary(device)` — peer-link and dual-attach Po members.
4. `show_interface_status` / `show_interface_counters_errors` on peer-link members.
5. For VXLAN leaves: `show_nve_interface` — anycast VTEP / VIP consistency across pair.
6. `show_mac_address_table` for affected VLAN on both peers.

## Decision tree
- Keepalive Down + peer-link Up → mgmt/keepalive path.
- Peer-link Down → L2/port-channel underlay between peers.
- Type-1 fail → config mismatch (VLAN, STP mode, etc.) — report for human fix.
- Type-2 fail → often operational; still document mismatched params.

## Common root causes
- MTU / speed mismatch on peer-link
- VLAN allowed list mismatch on peer-link
- Anycast gateway / VTEP IP mismatch across vPC pair
- Orphan ports

## What NOT to do
- Never `vpc` config changes, `reload`, or `clear` counters via this server.

## Output template
- Findings / Evidence / Probable cause / Suggested manual fix for operator
