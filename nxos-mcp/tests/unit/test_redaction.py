from __future__ import annotations


def test_redact_password(redactor) -> None:
    text = "username admin password hunter2"
    out = redactor.redact_text(text)
    assert "hunter2" not in out
    assert "REDACTED" in out


def test_redact_nested(redactor) -> None:
    payload = {"msg": "snmp community public", "auth": "token: abcdef"}
    out = redactor.redact(payload)
    blob = str(out)
    assert "REDACTED" in blob
    assert "abcdef" not in blob


def test_redact_preserves_structure(redactor) -> None:
    data = {"a": 1, "b": ["x", {"note": "password=secret"}]}
    out = redactor.redact(data)
    assert out["a"] == 1
    assert isinstance(out["b"], list)
    assert "secret" not in str(out["b"])
