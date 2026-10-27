import pytest
from cisco_show_tshoot.command_policy import validate_command
from cisco_show_tshoot.errors import PolicyError


@pytest.mark.parametrize("command", [
    "show version; reload", "show version | include uptime",
    "configure terminal", "write memory", "reload", "clear counters",
    "debug ip packet", "show version\\nreload",
])
def test_unsafe_commands_are_rejected(command):
    with pytest.raises(PolicyError):
        validate_command(command)


@pytest.mark.parametrize("command", [
    "show version", "show clock", "show ip interface brief",
    "show interfaces GigabitEthernet1/0/1", "show ip route 192.0.2.1",
])
def test_approved_commands_are_accepted(command):
    assert validate_command(command) == command
