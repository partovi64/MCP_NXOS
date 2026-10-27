import pytest
from cisco_show_tshoot.errors import PolicyError
from cisco_show_tshoot.inventory import get_device


def test_unknown_device_fails_closed():
    with pytest.raises(PolicyError):
        get_device("unknown-router")
