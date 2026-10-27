from dataclasses import dataclass
from .errors import PolicyError


@dataclass(frozen=True)
class Device:
    alias: str
    host: str
    device_type: str = "cisco_ios"
    location: str = "lab"


# Add explicitly approved lab devices. Do not put credentials here.
DEVICES: dict[str, Device] = {
    # "lab-r1": Device(alias="lab-r1", host="192.0.2.10"),
}


def get_device(alias: str) -> Device:
    if alias not in DEVICES:
        raise PolicyError(f"Unknown or unauthorized device alias: {alias!r}")
    return DEVICES[alias]


def list_devices() -> list[dict[str, str]]:
    return [{"alias": d.alias, "host": d.host, "device_type": d.device_type,
             "location": d.location} for d in DEVICES.values()]
