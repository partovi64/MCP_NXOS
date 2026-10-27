"""Command validator — allow/block matrix including injection attempts."""

from __future__ import annotations

import pytest

from nxos_mcp.guardrails.validator import ArgSchemas, CommandValidator, PingArgs
from nxos_mcp.nxapi.errors import GuardrailViolation

ALLOWED = [
    "show version",
    "show version | json",
    "show ip route",
    "show ip route vrf TENANT_A",
    "show ip arp vrf TENANT_A",
    "show nve peers",
    "show nve vni",
    "show nve vni 10001",
    "show nve interface",
    "show bgp l2vpn evpn summary",
    "show bgp l2vpn evpn",
    "show l2route evpn mac all",
    "show l2route evpn mac-ip all",
    "show vrf",
    "show vrf TENANT_A detail",
    "show vpc",
    "show vpc consistency-parameters global",
    "show port-channel summary",
    "show spanning-tree vlan 100",
    "show mac address-table",
    "show mac address-table vlan 100",
    "show interface status",
    "show interface counters errors",
    "show system resources",
    "show logging last 50",
    "show logging last 50 | include BGP",
    "show module",
    "show environment",
    "show feature",
    "show feature | include nxapi",
    "show ip ospf neighbors",
    "show isis adjacency",
    "show bgp ipv4 unicast summary",
    "show bfd neighbors",
    "show vxlan",
    "show interface brief",
    "ping 10.0.0.1 vrf default count 2 timeout 2 packet-size 100",
    "traceroute 10.1.1.1 vrf TENANT_A",
    "show version | include NXOS",
    "show version | exclude Copyright",
    "show ip route | count",
    "show logging last 20 | last 5",
    "show running-config interface",  # blocked separately if starts with show running-config
]

# show running-config is blocked by policy — remove from allowed if present
ALLOWED = [c for c in ALLOWED if not c.startswith("show running-config")]

BLOCKED = [
    "configure terminal",
    "conf t",
    "show version; conf t",
    "show version && reload",
    "show version || reload",
    "show run | redirect bootflash:x",
    "show version > bootflash:x",
    "show version | tee",
    "show version | email",
    "reload",
    "copy running-config startup-config",
    "write memory",
    "delete bootflash:x",
    "erase startup-config",
    "format bootflash:",
    "install all",
    "boot nxos",
    "clear ip arp vrf all",
    "debug bgp all",
    "terminal length 0",
    "run bash",
    "guestshell",
    "python",
    "tclsh",
    "username admin password x",
    "shutdown",
    "no feature nxapi",
    "feature nxapi",
    "checkpoint file x",
    "rollback running-config",
    "event manager applet x",
    "scheduler job name x",
    "ssh 10.0.0.1",
    "telnet 10.0.0.1",
    "tftp",
    "ftp",
    "scp",
    "sftp",
    "crypto key generate",
    "show tech-support",
    "show running-config",
    "show running-config aaa",
    "bash",
    "show version\nconf t",
    "show version`id`",
    "show version $(id)",
    "  ",
    "",
    "ping 8.8.8.8 vrf default count 2 timeout 2 packet-size 100",  # outside prefixes via build_ping
    "show version | redirect flash:x",
    "show version | include $(whoami)",
    "show version;show ip route",
    "clear counters",
    "\u200bshow version",  # zero-width then show — after strip Cf may become show version (allowed)
]


@pytest.mark.parametrize("command", ALLOWED)
def test_allowed_commands(validator: CommandValidator, command: str) -> None:
    result = validator.validate(command)
    assert result.allowed, f"expected allow for {command!r}: {result.reason}"


@pytest.mark.parametrize(
    "command",
    [
        c
        for c in BLOCKED
        if c
        not in {
            "",  # handled
            "\u200bshow version",  # may normalize to allowed
            "ping 8.8.8.8 vrf default count 2 timeout 2 packet-size 100",  # allowlist ok; dest check separate
        }
    ],
)
def test_blocked_commands(validator: CommandValidator, command: str) -> None:
    if not command.strip():
        result = validator.validate(command)
        assert not result.allowed
        return
    result = validator.validate(command)
    assert not result.allowed, f"expected block for {command!r}"


def test_empty_and_whitespace(validator: CommandValidator) -> None:
    assert not validator.validate("").allowed
    assert not validator.validate("   ").allowed


def test_zero_width_normalized_to_show(validator: CommandValidator) -> None:
    # Zero-width chars stripped; should become valid show
    result = validator.validate("\u200bshow version")
    assert result.allowed


def test_trailing_spaces_ok(validator: CommandValidator) -> None:
    assert validator.validate("show version   ").allowed


def test_unicode_homoglyph_semicolon(validator: CommandValidator) -> None:
    # Fullwidth semicolon should be caught via NFKC → ';'
    result = validator.validate("show version\uff1bconf t")
    assert not result.allowed


def test_pipe_arg_too_long(validator: CommandValidator) -> None:
    long_arg = "A" * 100
    assert not validator.validate(f"show version | include {long_arg}").allowed


def test_pipe_not_allowed(validator: CommandValidator) -> None:
    assert not validator.validate("show version | xml").allowed


def test_ping_destination_outside_prefix(validator: CommandValidator) -> None:
    with pytest.raises(GuardrailViolation):
        validator.build_ping(
            PingArgs(target="8.8.8.8", vrf="default", count=2, timeout=2)
        )


def test_ping_multicast_blocked(validator: CommandValidator) -> None:
    with pytest.raises(GuardrailViolation):
        validator.build_ping(
            PingArgs(target="224.0.0.5", vrf="default", count=1, timeout=1)
        )


def test_ping_allowed_rfc1918(validator: CommandValidator) -> None:
    cmd = validator.build_ping(
        PingArgs(target="10.1.2.3", vrf="default", count=2, timeout=2)
    )
    assert cmd.startswith("ping 10.1.2.3")


def test_arg_schemas() -> None:
    assert ArgSchemas.vni(10001) == "10001"
    with pytest.raises(GuardrailViolation):
        ArgSchemas.vni(0)
    with pytest.raises(GuardrailViolation):
        ArgSchemas.vni(16_777_216)
    assert ArgSchemas.vlan(100) == "100"
    with pytest.raises(GuardrailViolation):
        ArgSchemas.vlan(4095)
    assert ArgSchemas.vrf("TENANT_A") == "TENANT_A"
    with pytest.raises(GuardrailViolation):
        ArgSchemas.vrf("bad vrf")
    assert ArgSchemas.mac("aabb.ccdd.eeff") == "aabb.ccdd.eeff"
    with pytest.raises(GuardrailViolation):
        ArgSchemas.mac("zz")


def test_require_raises(validator: CommandValidator) -> None:
    with pytest.raises(GuardrailViolation):
        validator.require("reload")


def test_injection_nested_pipes(validator: CommandValidator) -> None:
    assert not validator.validate("show version | include x | redirect y").allowed


def test_count_cases_cover_sixty_plus() -> None:
    # Meta-test: ensure matrix size meets requirement
    assert len(ALLOWED) + len(BLOCKED) >= 60
