from __future__ import annotations

import json
from typing import Any

import pytest

from nxos_mcp.server import BearerAuthMiddleware


class _Recorder:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.messages.append(message)


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.disconnect"}


@pytest.mark.parametrize(
    ("auth_header", "expected_status"),
    [
        ("Bearer correct-token", None),  # None = request passed through
        ("Bearer wrong-token", 401),
        ("", 401),
        ("Basic dXNlcjpwYXNz", 401),
    ],
)
async def test_bearer_auth(auth_header: str, expected_status: int | None) -> None:
    reached_app = False

    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        nonlocal reached_app
        reached_app = True

    headers: list[tuple[bytes, bytes]] = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))

    scope = {"type": "http", "headers": headers}
    send = _Recorder()
    middleware = BearerAuthMiddleware(downstream, "correct-token")  # type: ignore[arg-type]

    await middleware(scope, _noop_receive, send)  # type: ignore[arg-type]

    if expected_status is None:
        assert reached_app
        assert not send.messages
    else:
        assert not reached_app
        assert send.messages[0]["status"] == expected_status
        assert json.loads(send.messages[1]["body"]) == {"error": "unauthorized"}


async def test_bearer_auth_non_http_scope_passthrough() -> None:
    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        pass

    middleware = BearerAuthMiddleware(downstream, "t")  # type: ignore[arg-type]
    # Lifespan scopes have no headers — must pass through untouched.
    await middleware({"type": "lifespan"}, _noop_receive, _Recorder())  # type: ignore[arg-type]


async def test_healthz_unauthenticated() -> None:
    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        raise AssertionError("downstream must not be reached for /healthz")

    middleware = BearerAuthMiddleware(downstream, "t")  # type: ignore[arg-type]
    send = _Recorder()
    await middleware(
        {"type": "http", "path": "/healthz", "headers": []},  # type: ignore[arg-type]
        _noop_receive,
        send,  # type: ignore[arg-type]
    )
    assert send.messages[0]["status"] == 200
    assert json.loads(send.messages[1]["body"]) == {"status": "ok"}
