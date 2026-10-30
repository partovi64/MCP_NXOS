"""NX-API client tests with respx-mocked HTTP (quirks, errors, retries)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from nxos_mcp.inventory import Device
from nxos_mcp.nxapi.client import NxapiClient, show_with_text_fallback
from nxos_mcp.nxapi.errors import (
    AuthError,
    CommandRejected,
    DeviceUnreachable,
    NxapiNotEnabled,
    ProtocolError,
)
from nxos_mcp.nxapi.models import normalize_table_rows
from nxos_mcp.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_device(**overrides: Any) -> Device:
    params: dict[str, Any] = {
        "name": "leaf-01",
        "host": "10.0.0.11",
        "protocol": "https",
        "port": 443,
        "path": "/ins",
        "api_style": "jsonrpc",
    }
    params.update(overrides)
    return Device.model_validate(params)


def make_settings(**overrides: Any) -> Settings:
    params: dict[str, Any] = {
        "username": "testuser",
        "password": "testpass",
        "allow_http": True,
        "retry_max": 3,
        "retry_base_s": 0.0,
        "allow_insecure": True,
    }
    params.update(overrides)
    return Settings.model_validate(params)


async def test_jsonrpc_happy_path() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("jsonrpc_show_version.json")
            )
            result = await client.show(device, "show version")
            sent = json.loads(mock.calls[0].request.content.decode())
    body = result["body"]
    row = normalize_table_rows(body)
    assert row[0]["sys_ver_str"] == "9.3(10)"
    # Request body must be JSON-RPC cli with cmd
    assert sent["jsonrpc"] == "2.0"
    assert sent["method"] == "cli"
    assert sent["params"]["cmd"] == "show version"


async def test_ins_api_happy_path_single_row_dict() -> None:
    settings = make_settings()
    device = make_device(api_style="ins_api")
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_show_nve_vni_single_row.json")
            )
            result = await client.show(device, "show nve vni")
    # Quirk: single ROW_ is a dict, not a list — normalize_table_rows must handle both
    rows = normalize_table_rows(result["body"])
    assert len(rows) == 1
    assert rows[0]["vni"] == "10010"


async def test_ins_api_multi_command_output_list() -> None:
    """ins_api may return outputs.output as a list; first element must be used."""
    settings = make_settings()
    device = make_device(api_style="ins_api")
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_show_nve_vni_multi_row_list.json")
            )
            result = await client.show(device, "show nve vni")
    rows = normalize_table_rows(result["body"])
    assert len(rows) == 2
    assert {r["vni-state"] for r in rows} == {"Up", "Down"}


async def test_ins_api_empty_body() -> None:
    settings = make_settings()
    device = make_device(api_style="ins_api")
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_empty_body.json")
            )
            result = await client.show(device, "show nve vni")
    assert result["empty"] is True
    assert result["body"] == {}


async def test_ins_api_text_output() -> None:
    settings = make_settings()
    device = make_device(api_style="ins_api")
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_text_output.json")
            )
            result = await client.show(device, "show vrf", output_format="text")
    assert "TENANT_A" in result["body"]


async def test_jsonrpc_error_response_raises_command_rejected() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(status_code=200, json=fixture("jsonrpc_error.json"))
            with pytest.raises(CommandRejected) as exc_info:
                await client.show(device, "show vrf detail")
    assert "json" in str(exc_info.value).lower()


async def test_http_401_raises_auth_error() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="bad") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(status_code=401, json={})
            with pytest.raises(AuthError):
                await client.show(device, "show version")


async def test_http_404_raises_nxapi_not_enabled() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(status_code=404, json={})
            with pytest.raises(NxapiNotEnabled):
                await client.show(device, "show version")


async def test_ins_api_code_413_raises_command_rejected() -> None:
    settings = make_settings()
    device = make_device(api_style="ins_api")
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_error_413.json")
            )
            with pytest.raises(CommandRejected) as exc_info:
                await client.show(device, "show l2route evpn mac all")
    assert "too large" in str(exc_info.value).lower()


async def test_ins_api_code_501_raises_nxapi_not_enabled() -> None:
    settings = make_settings()
    device = make_device(api_style="ins_api")
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_error_501.json")
            )
            with pytest.raises(NxapiNotEnabled):
                await client.show(device, "show version")


async def test_http_500_retries_then_succeeds() -> None:
    settings = make_settings(retry_max=3)
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as _mock:
            route = _mock.post(device.base_url)
            route.side_effect = [
                httpx.Response(503, json={}),
                httpx.Response(503, json={}),
                httpx.Response(200, json=fixture("jsonrpc_show_version.json")),
            ]
            result = await client.show(device, "show version")
            assert "TABLE_sys_ver" in result["body"]
            assert route.call_count == 3


async def test_http_500_retries_exhausted_raises() -> None:
    settings = make_settings(retry_max=2)
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as _mock:
            route = _mock.post(device.base_url)
            route.side_effect = [
                httpx.Response(500, json={}),
                httpx.Response(500, json={}),
            ]
            with pytest.raises(DeviceUnreachable):
                await client.show(device, "show version")
            assert route.call_count == 2


async def test_4xx_never_retried() -> None:
    settings = make_settings(retry_max=3)
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as _mock:
            route = _mock.post(device.base_url)
            route.side_effect = [
                httpx.Response(403, json={}),
                httpx.Response(403, json={}),
                httpx.Response(403, json={}),
            ]
            with pytest.raises(AuthError):
                await client.show(device, "show version")
            assert route.call_count == 1


async def test_connect_error_raises_device_unreachable() -> None:
    settings = make_settings(retry_max=1)
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as _mock:
            _mock.post(device.base_url).mock(side_effect=httpx.ConnectError("no route"))
            with pytest.raises(DeviceUnreachable):
                await client.show(device, "show version")


async def test_html_response_raises_nxapi_not_enabled() -> None:
    """Switch without 'feature nxapi' often returns an HTML login page."""
    settings = make_settings()
    device = make_device()
    html = "<html><body>Login</body></html>"
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200,
                headers={"content-type": "text/html"},
                text=html,
            )
            with pytest.raises(NxapiNotEnabled):
                await client.show(device, "show version")


async def test_non_dict_json_root_raises_protocol_error() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(status_code=200, json=[1, 2, 3])
            with pytest.raises(ProtocolError):
                await client.show(device, "show version")


async def test_http_device_blocked_without_allow_http() -> None:
    settings = make_settings(allow_http=False)
    device = make_device(protocol="http", port=80)
    async with NxapiClient(settings, username="u", password="p") as client:
        with pytest.raises(ProtocolError):
            await client.show(device, "show version")


async def test_jsonrpc_text_format_uses_ins_api_fallback() -> None:
    """output_format=text on a jsonrpc device routes through ins_api."""
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("ins_api_text_output.json")
            )
            result = await client.show(device, "show vrf", output_format="text")
            sent = json.loads(mock.calls[0].request.content.decode())
    assert "TENANT_A" in result["body"]
    assert "ins_api" in sent
    assert sent["ins_api"]["output_format"] == "text"


async def test_show_with_text_fallback_stays_json_on_success() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as mock:
            mock.post(device.base_url).respond(
                status_code=200, json=fixture("jsonrpc_show_version.json")
            )
            _result, used = await show_with_text_fallback(client, device, "show version")
    assert used == "json"


async def test_show_with_text_fallback_on_json_unsupported() -> None:
    settings = make_settings()
    device = make_device()
    async with NxapiClient(settings, username="u", password="p") as client:
        with respx.mock(assert_all_called=False) as _mock:
            route = _mock.post(device.base_url)
            route.side_effect = [
                httpx.Response(200, json=fixture("jsonrpc_error.json")),
                httpx.Response(200, json=fixture("ins_api_text_output.json")),
            ]
            _result, used = await show_with_text_fallback(client, device, "show vrf")
            assert used == "text"
