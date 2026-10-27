import pytest
from cisco_show_tshoot.errors import PolicyError
from cisco_show_tshoot.guardrails import limit_output, validate_batch


def test_batch_rejects_all_before_execution():
    with pytest.raises(PolicyError):
        validate_batch(["show version", "conf t"])


def test_batch_limit():
    with pytest.raises(PolicyError):
        validate_batch(["show version"] * 9)


def test_output_limit_is_marked():
    assert limit_output("abcdef", 3) == ("abc", True)
    assert limit_output("abc", 3) == ("abc", False)
