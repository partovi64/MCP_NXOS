"""FastMCP application — registers tools, resources, and prompts."""

from __future__ import annotations

import hmac
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
import uvicorn
from mcp.server.fastmcp import FastMCP

from nxos_mcp.resources import register_resources_and_prompts
from nxos_mcp.runtime import Runtime
from nxos_mcp.settings import Settings, Transport, load_settings
from nxos_mcp.tools.generic import register_generic_tools
from nxos_mcp.tools.health import register_health_tools
from nxos_mcp.tools.underlay import register_underlay_tools
from nxos_mcp.tools.vpc_l2 import register_vpc_l2_tools
from nxos_mcp.tools.vrf import register_vrf_tools
from nxos_mcp.tools.vxlan import register_vxlan_tools

log = structlog.get_logger(__name__)

# Minimal ASGI types (avoids depending on asgiref/starlette type stubs).
Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[..., Awaitable[None]]


class BearerAuthMiddleware:
    """Pure-ASGI middleware enforcing a constant-time bearer-token check."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }
            provided = headers.get("authorization", "").encode()
            if not hmac.compare_digest(provided, self._expected):
                body = json.dumps({"error": "unauthorized"}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self._app(scope, receive, send)


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), level.upper(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_mcp(rt: Runtime | None = None, settings: Settings | None = None) -> FastMCP:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    runtime = rt or Runtime.create(settings)

    mcp = FastMCP(
        name="nxos-mcp",
        instructions=(
            "Read-only Cisco NX-OS MCP server for VXLAN BGP-EVPN troubleshooting. "
            "Never attempt configuration changes. Prefer specialized tools and skills "
            "(prompts/resources under nxos://skills/). Credentials are never accepted "
            "as tool arguments."
        ),
    )

    register_generic_tools(mcp, runtime)
    register_vxlan_tools(mcp, runtime)
    register_vrf_tools(mcp, runtime)
    register_underlay_tools(mcp, runtime)
    register_vpc_l2_tools(mcp, runtime)
    register_health_tools(mcp, runtime)
    register_resources_and_prompts(mcp, runtime)

    log.info(
        "server_created",
        devices=len(runtime.inventory.devices),
        dry_run=settings.dry_run,
        transport=settings.transport.value,
    )
    return mcp


def run(settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    if settings.allow_insecure:
        log.warning("startup_insecure_tls", msg="NXOS_ALLOW_INSECURE=true")
    if settings.transport == Transport.STREAMABLE_HTTP and not settings.http_bearer_token:
        raise SystemExit(
            "NXOS_HTTP_BEARER_TOKEN is required for streamable-http transport"
        )

    mcp = create_mcp(settings=settings)

    if settings.transport == Transport.STDIO:
        mcp.run(transport="stdio")
        return

    # streamable-http — bearer-token auth enforced on every request; bind localhost by default
    app = BearerAuthMiddleware(mcp.streamable_http_app(), settings.http_bearer_token)
    log.info("starting_http", host=settings.http_host, port=settings.http_port)
    uvicorn.run(app, host=settings.http_host, port=settings.http_port, log_level="warning")
