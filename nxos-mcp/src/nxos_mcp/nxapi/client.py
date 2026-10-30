"""Async NX-API client (JSON-RPC + ins_api cli_show)."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Literal

import httpx
import structlog

from nxos_mcp.inventory import Device
from nxos_mcp.nxapi.errors import (
    AuthError,
    CommandRejected,
    DeviceUnreachable,
    NxapiNotEnabled,
    ProtocolError,
    Timeout,
)
from nxos_mcp.nxapi.models import InsApiRequest, JsonRpcRequest
from nxos_mcp.settings import Settings

log = structlog.get_logger(__name__)

OutputFormat = Literal["json", "text"]


class NxapiClient:
    """Connection-pooled, retrying NX-API client. Show commands only."""

    def __init__(
        self,
        settings: Settings,
        *,
        username: str,
        password: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._username = username
        self._password = password
        self._owns_client = client is None
        verify = settings.tls_verify
        if settings.allow_insecure:
            log.warning(
                "tls_verify_disabled",
                hint="NXOS_ALLOW_INSECURE=true; do not use in production",
            )
        self._client = client or httpx.AsyncClient(
            auth=(username, password),
            verify=verify,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout_s,
                read=settings.read_timeout_s,
                write=settings.read_timeout_s,
                pool=settings.connect_timeout_s,
            ),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> NxapiClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def show(
        self,
        device: Device,
        command: str,
        *,
        output_format: OutputFormat = "json",
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        if device.protocol == "http" and not self._settings.allow_http:
            raise ProtocolError(
                "HTTP NX-API is disabled",
                hint="Set NXOS_ALLOW_HTTP=true only for isolated lab use",
            )
        style = device.api_style or "jsonrpc"
        if style == "jsonrpc":
            # JSON-RPC cli returns structured JSON; text fallback uses ins_api
            if output_format == "text":
                return await self._ins_api(device, command, output_format="text", auth=auth)
            return await self._jsonrpc(device, command, auth=auth)
        return await self._ins_api(device, command, output_format=output_format, auth=auth)

    async def _jsonrpc(
        self,
        device: Device,
        command: str,
        *,
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        body = JsonRpcRequest.show(command).model_dump()
        data = await self._post_with_retry(device, body, auth=auth)
        if "error" in data:
            err = data["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            data_obj = err.get("data") if isinstance(err, dict) else None
            detail = ""
            if isinstance(data_obj, dict):
                detail = str(data_obj.get("msg") or data_obj.get("message") or "")
            raise CommandRejected(
                f"NX-API rejected command: {msg}",
                hint=detail or "Check syntax, feature enablement, and read-only privileges",
            )
        result = data.get("result")
        if result is None:
            return {"body": {}, "empty": True}
        if isinstance(result, dict):
            # Often {"body": {...}} or nested
            return result
        return {"body": result}

    async def _ins_api(
        self,
        device: Device,
        command: str,
        *,
        output_format: OutputFormat,
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        body = InsApiRequest(input=command, output_format=output_format).payload()
        data = await self._post_with_retry(device, body, auth=auth)
        ins = data.get("ins_api")
        if not isinstance(ins, dict):
            raise ProtocolError("unexpected ins_api response shape")
        outputs = ins.get("outputs", {}).get("output")
        # Multi-command can return list; we only send one
        if isinstance(outputs, list):
            if not outputs:
                return {"body": {}, "empty": True}
            outputs = outputs[0]
        if not isinstance(outputs, dict):
            return {"body": outputs, "empty": outputs in (None, "", {})}

        code = str(outputs.get("code", "200"))
        msg = str(outputs.get("msg", ""))
        if code not in {"200", "0"}:
            if "not enabled" in msg.lower() or code == "501":
                raise NxapiNotEnabled(
                    "NX-API appears disabled or command type unsupported",
                    hint="On the switch: feature nxapi; nxapi https port 443; "
                    "nxapi use-vrf management",
                )
            raise CommandRejected(
                f"ins_api error code={code}: {msg}",
                hint="Verify command supports JSON output or retry with output_format=text",
            )
        body_out = outputs.get("body", outputs.get("clierror"))
        if body_out in (None, "", {}):
            return {"body": {}, "empty": True, "msg": msg}
        return {"body": body_out, "msg": msg, "code": code}

    async def _post_with_retry(
        self,
        device: Device,
        body: dict[str, Any],
        *,
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        url = device.base_url
        last_exc: Exception | None = None
        attempts = max(1, self._settings.retry_max)
        for attempt in range(attempts):
            transient = False
            try:
                response = await self._client.post(
                    url, json=body, auth=auth if auth is not None else httpx.USE_CLIENT_DEFAULT
                )
            except httpx.ConnectError as exc:
                last_exc = DeviceUnreachable(
                    f"cannot reach {device.name} at {device.host}",
                    hint="Check mgmt connectivity, VRF, and NX-API listener",
                )
                transient = True
                if attempt + 1 >= attempts:
                    raise last_exc from exc
            except httpx.TimeoutException as exc:
                last_exc = Timeout(
                    f"timeout talking to {device.name}",
                    hint="Increase read timeout or narrow the show command",
                )
                transient = True
                if attempt + 1 >= attempts:
                    raise last_exc from exc
            except httpx.HTTPError as exc:
                raise DeviceUnreachable(f"HTTP error for {device.name}: {exc}") from exc
            else:
                if response.status_code >= 500:
                    last_exc = DeviceUnreachable(
                        f"server error {response.status_code} from {device.name}",
                        hint="Transient device/API failure; retry later",
                    )
                    transient = True
                    if attempt + 1 >= attempts:
                        raise last_exc
                else:
                    return self._handle_http(device, response)

            if transient:
                delay = self._settings.retry_base_s * (2**attempt) + random.uniform(0, 0.25)
                await asyncio.sleep(delay)

        assert last_exc is not None
        raise last_exc

    def _handle_http(self, device: Device, response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status in {401, 403}:
            raise AuthError(
                f"authentication failed for {device.name}",
                hint="Verify NXOS_USERNAME/PASSWORD and AAA role (prefer network-operator)",
            )
        if status == 404:
            raise NxapiNotEnabled(
                f"NX-API endpoint not found on {device.name}",
                hint="Enable feature nxapi and confirm /ins path",
            )
        if status == 413:
            raise CommandRejected(
                "request/response too large (413)",
                hint="Narrow the command or use pagination tools",
            )
        if status == 400:
            raise CommandRejected(
                "bad request (400)",
                hint="Command may be invalid for this NX-OS release",
            )
        if status == 501:
            raise NxapiNotEnabled(
                "NX-API method not implemented (501)",
                hint="Confirm feature nxapi and cli_show support",
            )
        if status >= 400:
            raise CommandRejected(f"HTTP {status} from {device.name}")

        try:
            data = response.json()
        except ValueError as exc:
            text = response.text[:200]
            if "html" in text.lower():
                raise NxapiNotEnabled(
                    "non-JSON response from /ins (is NX-API enabled?)",
                    hint="feature nxapi; prefer HTTPS; check mgmt VRF",
                ) from exc
            raise ProtocolError(f"invalid JSON from {device.name}") from exc
        if not isinstance(data, dict):
            raise ProtocolError("NX-API root must be a JSON object")
        return data


async def show_with_text_fallback(
    client: NxapiClient,
    device: Device,
    command: str,
    *,
    prefer: OutputFormat = "json",
) -> tuple[dict[str, Any], OutputFormat]:
    """Try JSON first; fall back to text when device lacks JSON for the command."""
    if prefer == "text":
        return await client.show(device, command, output_format="text"), "text"
    try:
        return await client.show(device, command, output_format="json"), "json"
    except CommandRejected as exc:
        msg = str(exc).lower()
        if "json" in msg or "not supported" in msg or "501" in msg:
            data = await client.show(device, command, output_format="text")
            return data, "text"
        raise
