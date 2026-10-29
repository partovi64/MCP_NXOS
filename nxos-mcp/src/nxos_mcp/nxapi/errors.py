"""Typed exceptions for NX-API and guardrail failures."""

from __future__ import annotations


class NxosMcpError(Exception):
    """Base error; safe message for MCP clients (no secrets/stack)."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        out = {"error": self.__class__.__name__, "message": str(self)}
        if self.hint:
            out["hint"] = self.hint
        return out


class AuthError(NxosMcpError):
    """Authentication / authorization failure against NX-API."""


class DeviceUnreachable(NxosMcpError):
    """Device TCP/TLS/DNS unreachable."""


class CommandRejected(NxosMcpError):
    """Device rejected the show command (syntax/feature/privilege)."""


class Timeout(NxosMcpError):
    """Connect or read timeout."""


class GuardrailViolation(NxosMcpError):
    """Command blocked by local policy before network I/O."""


class RateLimitExceeded(NxosMcpError):
    """Per-device or global rate/concurrency limit hit."""


class OutputTooLarge(NxosMcpError):
    """Response exceeded configured output budget."""


class NxapiNotEnabled(NxosMcpError):
    """feature nxapi appears disabled or endpoint missing."""


class ProtocolError(NxosMcpError):
    """Malformed NX-API response or unsupported mode."""
