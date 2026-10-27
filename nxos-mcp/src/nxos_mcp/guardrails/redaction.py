"""Secret redaction for outputs and logs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RedactionRule(BaseModel):
    name: str
    regex: str
    replace: str


class RedactionConfig(BaseModel):
    patterns: list[RedactionRule] = Field(default_factory=list)


class Redactor:
    def __init__(self, rules: list[RedactionRule]) -> None:
        self._compiled = [(r.name, re.compile(r.regex), r.replace) for r in rules]

    def redact_text(self, text: str) -> str:
        out = text
        for _name, pattern, repl in self._compiled:
            out = pattern.sub(repl, out)
        return out

    def redact(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if isinstance(value, (int, float, bool)):
            return value
        # Fallback via JSON round-trip for pydantic models / odd types
        try:
            dumped = json.dumps(value, default=str)
            return json.loads(self.redact_text(dumped))
        except (TypeError, ValueError):
            return self.redact_text(str(value))


def load_redactor(path: Path) -> Redactor:
    if not path.exists():
        return Redactor([])
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = RedactionConfig.model_validate(raw)
    return Redactor(cfg.patterns)
