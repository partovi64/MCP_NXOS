"""Command validation pipeline — fail closed."""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from nxos_mcp.guardrails.policy import GuardrailPolicy
from nxos_mcp.nxapi.errors import GuardrailViolation

# Strict argument patterns for templated commands
RE_VRF = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
RE_IPV4 = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$")
RE_IPV6 = re.compile(r"^[0-9A-Fa-f:]+$")
RE_MAC = re.compile(
    r"^(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}$"
    r"|^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
)
RE_IFACE = re.compile(
    r"^(?:Ethernet|Eth|port-channel|Po|Vlan|Lo|loopback|mgmt|nve)"
    r"[0-9]+(?:/[0-9]+)*(?:\.[0-9]+)?$",
    re.IGNORECASE,
)
RE_ASN = re.compile(r"^\d{1,10}(?:\.\d{1,10})?$")
RE_VLAN = re.compile(r"^(?:[1-9]\d{0,2}|[1-3]\d{3}|40[0-8]\d|409[0-4])$")
RE_PREFIX = re.compile(
    r"^(?:(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)"
    r"/(?:[0-9]|[12]\d|3[0-2]))$"
    r"|^(?:[0-9A-Fa-f:]+/(?:[0-9]|[1-9]\d|1[01]\d|12[0-8]))$"
)

PIPE_SPLIT = re.compile(r"\s*\|\s*")


class CommandValidation(BaseModel):
    command: str
    allowed: bool = True
    reason: str | None = None
    pipes: list[str] = Field(default_factory=list)


class ArgSchemas:
    """Builders that only accept validated args — never raw concat of user text."""

    @staticmethod
    def vrf(value: str) -> str:
        if not RE_VRF.match(value) or value.startswith("-"):
            raise GuardrailViolation(f"invalid VRF name: {value!r}")
        return value

    @staticmethod
    def vni(value: int | str) -> str:
        try:
            n = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise GuardrailViolation(f"invalid VNI: {value!r} (1-16777215)") from exc
        if not 1 <= n <= 16_777_215:
            raise GuardrailViolation(f"invalid VNI: {value!r} (1-16777215)")
        return str(n)

    @staticmethod
    def ipv4(value: str) -> str:
        if not RE_IPV4.match(value):
            raise GuardrailViolation(f"invalid IPv4: {value!r}")
        return value

    @staticmethod
    def ip(value: str) -> str:
        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise GuardrailViolation(f"invalid IP: {value!r}") from exc
        return value

    @staticmethod
    def mac(value: str) -> str:
        if not RE_MAC.match(value):
            raise GuardrailViolation(f"invalid MAC: {value!r}")
        return value

    @staticmethod
    def iface(value: str) -> str:
        if not RE_IFACE.match(value):
            raise GuardrailViolation(f"invalid interface: {value!r}")
        return value

    @staticmethod
    def asn(value: str | int) -> str:
        s = str(value)
        if not RE_ASN.match(s):
            raise GuardrailViolation(f"invalid ASN: {value!r}")
        return s

    @staticmethod
    def vlan(value: int | str) -> str:
        s = str(value)
        if not RE_VLAN.match(s):
            raise GuardrailViolation(f"invalid VLAN: {value!r}")
        return s

    @staticmethod
    def prefix(value: str) -> str:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise GuardrailViolation(f"invalid prefix: {value!r}") from exc
        return value


class PingArgs(BaseModel):
    target: str
    vrf: str
    count: int = Field(default=2, ge=1, le=5)
    timeout: int = Field(default=2, ge=1, le=2)
    size: int = Field(default=100, ge=36, le=1500)
    source: str | None = None

    @field_validator("target")
    @classmethod
    def _target(cls, v: str) -> str:
        return ArgSchemas.ip(v)

    @field_validator("vrf")
    @classmethod
    def _vrf(cls, v: str) -> str:
        return ArgSchemas.vrf(v)

    @field_validator("source")
    @classmethod
    def _source(cls, v: str | None) -> str | None:
        if v is None:
            return None
        # interface or IP
        try:
            return ArgSchemas.iface(v)
        except GuardrailViolation:
            return ArgSchemas.ip(v)


class TracerouteArgs(BaseModel):
    target: str
    vrf: str
    source: str | None = None

    @field_validator("target")
    @classmethod
    def _target(cls, v: str) -> str:
        return ArgSchemas.ip(v)

    @field_validator("vrf")
    @classmethod
    def _vrf(cls, v: str) -> str:
        return ArgSchemas.vrf(v)


def _normalize_unicode(command: str) -> str:
    # NFKC collapses homoglyphs; strip zero-width
    normalized = unicodedata.normalize("NFKC", command)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")


class CommandValidator:
    def __init__(self, policy: GuardrailPolicy) -> None:
        self.policy = policy

    def validate(self, command: str) -> CommandValidation:
        try:
            cleaned = self._validate(command)
            return CommandValidation(command=cleaned, allowed=True)
        except GuardrailViolation as exc:
            return CommandValidation(command=command, allowed=False, reason=str(exc))

    def require(self, command: str) -> str:
        result = self.validate(command)
        if not result.allowed:
            raise GuardrailViolation(
                result.reason or "command blocked",
                hint="Only show/ping/traceroute with allowlisted forms are permitted",
            )
        return result.command

    def _validate(self, command: str) -> str:
        if command is None:
            raise GuardrailViolation("empty command")
        raw = _normalize_unicode(command).strip()
        if not raw:
            raise GuardrailViolation("empty command")
        if len(raw) > 512:
            raise GuardrailViolation("command too long (max 512 chars)")

        for token in self.policy.forbidden_chars:
            if token in raw:
                raise GuardrailViolation(f"forbidden sequence: {token!r}")

        # No shell metacharacters / redirection outside pipe policy
        if ">" in raw or "<" in raw:
            raise GuardrailViolation("redirection characters are not allowed")

        lower = raw.lower()
        if self.policy.block_show_running_config and lower.startswith("show running-config"):
            raise GuardrailViolation("show running-config is blocked by policy")
        if not self.policy.allow_show_tech_support and "show tech-support" in lower:
            raise GuardrailViolation("show tech-support is blocked by policy")

        # Pipe policy
        parts = PIPE_SPLIT.split(raw)
        base = parts[0].strip()
        first = base.split(None, 1)[0].lower() if base else ""
        is_readonly_verb = first in {"show", "ping", "traceroute"}

        # Config-verb tokens that may appear harmlessly inside show output filters
        skip_if_readonly = {
            "feature",
            "boot",
            "event",
            "python",
            "install",
            "scheduler",
            "crypto",
            "username",
        }

        for pattern in self.policy.denylist_re:
            if is_readonly_verb:
                pat_l = pattern.pattern.lower()
                if any(tok in pat_l for tok in skip_if_readonly):
                    continue
            if pattern.search(raw):
                raise GuardrailViolation(f"denylist match: {pattern.pattern}")

        pipes: list[str] = []
        for part in parts[1:]:
            part = part.strip()
            if not part:
                raise GuardrailViolation("empty pipe segment")
            tokens = part.split(None, 1)
            pipe_name = tokens[0].lower()
            if pipe_name not in self.policy.allowed_pipes:
                raise GuardrailViolation(f"pipe not allowed: {pipe_name}")
            if len(tokens) > 1:
                arg = tokens[1]
                if len(arg) > self.policy.pipe_arg_max_length:
                    raise GuardrailViolation("pipe argument too long")
                if self.policy.pipe_arg_re and not self.policy.pipe_arg_re.match(arg):
                    raise GuardrailViolation("pipe argument has illegal characters")
            pipes.append(pipe_name)

        matched = any(p.match(base) for p in self.policy.allowlist_re)
        if not matched:
            raise GuardrailViolation("command does not match allowlist")

        # Must start with show / ping / traceroute after allowlist
        if not is_readonly_verb:
            raise GuardrailViolation("only show, ping, and traceroute are permitted")

        if not pipes:
            return base
        pipe_segments = ["| " + " ".join(part.split()) for part in parts[1:]]
        return base + " " + " ".join(pipe_segments)

    def assert_destination_allowed(self, target: str) -> None:
        try:
            addr = ipaddress.ip_address(target)
        except ValueError as exc:
            raise GuardrailViolation(f"invalid destination IP: {target!r}") from exc
        if self.policy.deny_broadcast_multicast:
            if addr.is_multicast or addr.is_unspecified or getattr(addr, "is_reserved", False):
                raise GuardrailViolation(f"destination not allowed: {target}")
            if isinstance(addr, ipaddress.IPv4Address) and str(addr).endswith(".255"):
                # coarse broadcast heuristic for common /24 labs
                raise GuardrailViolation(f"broadcast-like destination blocked: {target}")
        if not any(addr in net for net in self.policy.networks):
            raise GuardrailViolation(
                f"destination {target} outside allowed_prefixes",
                hint="Update guardrails.yaml allowed_prefixes for your underlay/overlay ranges",
            )

    def build_ping(self, args: PingArgs) -> str:
        self.assert_destination_allowed(args.target)
        cmd = (
            f"ping {args.target} vrf {args.vrf} count {args.count} "
            f"timeout {args.timeout} packet-size {args.size}"
        )
        if args.source:
            cmd += f" source {args.source}"
        return self.require(cmd)

    def build_traceroute(self, args: TracerouteArgs) -> str:
        self.assert_destination_allowed(args.target)
        cmd = f"traceroute {args.target} vrf {args.vrf}"
        if args.source:
            try:
                src = ArgSchemas.iface(args.source)
            except GuardrailViolation:
                src = ArgSchemas.ip(args.source)
            cmd += f" source {src}"
        return self.require(cmd)


OutputFormatName = Literal["json", "text"]
