"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from nxos_mcp.guardrails.policy import load_policy
from nxos_mcp.guardrails.redaction import load_redactor
from nxos_mcp.guardrails.validator import CommandValidator
from nxos_mcp.inventory import load_inventory
from nxos_mcp.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


@pytest.fixture
def policy():
    return load_policy(CONFIG / "guardrails.yaml")


@pytest.fixture
def validator(policy):
    return CommandValidator(policy)


@pytest.fixture
def redactor():
    return load_redactor(CONFIG / "redaction.yaml")


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    src = CONFIG / "inventory.example.yaml"
    dest = tmp_path / "inventory.yaml"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("NXOS_USERNAME", "testuser")
    monkeypatch.setenv("NXOS_PASSWORD", "testpass")
    return load_inventory(dest)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NXOS_USERNAME", "testuser")
    monkeypatch.setenv("NXOS_PASSWORD", "testpass")
    inv = tmp_path / "inventory.yaml"
    inv.write_text(
        (CONFIG / "inventory.example.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return Settings(
        username="testuser",
        password="testpass",
        inventory=inv,
        guardrails=CONFIG / "guardrails.yaml",
        redaction=CONFIG / "redaction.yaml",
        dry_run=True,
        audit_log_path=tmp_path / "audit.jsonl",
        allow_http=True,
    )
