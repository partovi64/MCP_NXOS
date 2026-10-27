"""CLI entry: python -m nxos_mcp | nxos-mcp."""

from __future__ import annotations

import argparse
import sys

from nxos_mcp.server import run
from nxos_mcp.settings import Settings, Transport, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nxos-mcp",
        description="Read-only NX-OS MCP server (NX-API / VXLAN BGP-EVPN)",
    )
    parser.add_argument(
        "--transport",
        choices=[t.value for t in Transport],
        default=None,
        help="Override NXOS_TRANSPORT (stdio | streamable-http)",
    )
    parser.add_argument("--host", default=None, help="HTTP bind host")
    parser.add_argument("--port", type=int, default=None, help="HTTP bind port")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Validate commands without executing on devices",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    updates: dict[str, object] = {}
    if args.transport:
        updates["transport"] = args.transport
    if args.host:
        updates["http_host"] = args.host
    if args.port:
        updates["http_port"] = args.port
    if args.dry_run:
        updates["dry_run"] = True
    if updates:
        settings = settings.model_copy(update=updates)
    run(settings)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
