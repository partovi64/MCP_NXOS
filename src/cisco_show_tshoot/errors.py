class PolicyError(ValueError):
    """Request violates command or access policy."""


class DeviceError(RuntimeError):
    """Device access or command execution failed."""
