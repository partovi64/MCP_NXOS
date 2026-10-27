"""Load guardrails.yaml into typed policy."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class Limits(BaseModel):
    max_output_bytes: int = 65536
    max_fanout_devices: int = 10
    max_concurrent_per_device: int = 3
    global_concurrency: int = 20
    rate_limit_per_device: float = 5.0
    rate_limit_burst: int = 10
    ping_count_max: int = 5
    ping_timeout_max_s: int = 2
    ping_size_max: int = 1500
    traceroute_probe_max: int = 5
    log_last_n_max: int = 200
    table_page_default: int = 50
    table_page_max: int = 200


class GuardrailPolicy(BaseModel):
    allowlist: list[str] = Field(default_factory=lambda: [r"^show\s+.+$"])
    denylist: list[str] = Field(default_factory=list)
    block_show_running_config: bool = True
    allow_show_tech_support: bool = False
    allowed_pipes: list[str] = Field(
        default_factory=lambda: [
            "json",
            "include",
            "exclude",
            "grep",
            "count",
            "last",
            "begin",
            "section",
            "wc",
        ]
    )
    pipe_arg_max_length: int = 64
    pipe_arg_charset: str = r"^[A-Za-z0-9_.:\-/\s\^\$\[\]\(\)\|\?\*\\+\\]+$"
    forbidden_chars: list[str] = Field(
        default_factory=lambda: [";", "&&", "||", "`", "$(", "\n", "\r"]
    )
    limits: Limits = Field(default_factory=Limits)
    allowed_prefixes: list[str] = Field(
        default_factory=lambda: [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "fc00::/7",
            "fe80::/10",
        ]
    )
    deny_broadcast_multicast: bool = True
    require_vrf_for_ping_traceroute: bool = True
    cache_vrf_list_ttl_s: int = 300

    # Compiled at load time
    allowlist_re: list[re.Pattern[str]] = Field(default_factory=list, exclude=True)
    denylist_re: list[re.Pattern[str]] = Field(default_factory=list, exclude=True)
    pipe_arg_re: re.Pattern[str] | None = Field(default=None, exclude=True)
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = Field(
        default_factory=list, exclude=True
    )

    @field_validator("allowed_pipes")
    @classmethod
    def _pipes_lower(cls, value: list[str]) -> list[str]:
        return [p.lower() for p in value]

    def model_post_init(self, __context: Any) -> None:
        self.allowlist_re = [re.compile(p, re.IGNORECASE) for p in self.allowlist]
        self.denylist_re = [re.compile(p) for p in self.denylist]
        self.pipe_arg_re = re.compile(self.pipe_arg_charset)
        nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for prefix in self.allowed_prefixes:
            nets.append(ipaddress.ip_network(prefix, strict=False))
        self.networks = nets


def load_policy(path: Path) -> GuardrailPolicy:
    if not path.exists():
        raise FileNotFoundError(f"guardrails not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("guardrails root must be a mapping")
    return GuardrailPolicy.model_validate(raw)
