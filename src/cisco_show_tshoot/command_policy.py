import re
from .errors import PolicyError

ALLOWED_PATTERNS = [
    re.compile(r"show version"),
    re.compile(r"show clock"),
    re.compile(r"show ip interface brief"),
    re.compile(r"show interfaces"),
    re.compile(r"show interfaces [A-Za-z0-9/.:_-]+"),
    re.compile(r"show interfaces counters errors"),
    re.compile(r"show ip route"),
    re.compile(r"show ip route [0-9.]+"),
    re.compile(r"show ip ospf neighbor"),
    re.compile(r"show ip bgp summary"),
    re.compile(r"show vlan brief"),
    re.compile(r"show interfaces trunk"),
    re.compile(r"show spanning-tree"),
    re.compile(r"show spanning-tree vlan [0-9]{1,4}"),
    re.compile(r"show logging"),
]


def validate_command(command: str) -> str:
    if not isinstance(command, str):
        raise PolicyError("Command must be a string.")
    command = command.strip()
    if not command or len(command) > 256:
        raise PolicyError("Command is empty or too long.")
    if any(ord(c) < 32 or ord(c) == 127 for c in command):
        raise PolicyError("Control characters are denied.")
    if any(token in command for token in (";", "|", "`", "$", "\\n", "\\r")):
        raise PolicyError("Command chaining and filters are denied.")
    if not any(p.fullmatch(command) for p in ALLOWED_PATTERNS):
        raise PolicyError(f"Command is not allowlisted: {command!r}")
    return command
