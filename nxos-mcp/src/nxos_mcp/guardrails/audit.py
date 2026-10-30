"""JSON-lines audit log (no credentials, no full outputs)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog

log = structlog.get_logger(__name__)

Decision = Literal["allowed", "blocked", "error"]


@dataclass
class AuditEvent:
    timestamp: str
    request_id: str
    mcp_client: str | None
    device: str | None
    command: str | None
    decision: Decision
    reason: str | None = None
    duration_ms: int | None = None
    output_size: int | None = None
    tool: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: AuditEvent) -> None:
        payload = {k: v for k, v in asdict(event).items() if v is not None and k != "extra"}
        if event.extra:
            payload.update(event.extra)
        line = json.dumps(payload, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        log.info(
            "audit",
            decision=event.decision,
            device=event.device,
            tool=event.tool,
            request_id=event.request_id,
            reason=event.reason,
            duration_ms=event.duration_ms,
            output_size=event.output_size,
        )


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
