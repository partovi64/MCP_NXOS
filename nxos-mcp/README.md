# nxos-mcp

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server for
troubleshooting Cisco Nexus (NX-OS) switches over **NX-API (HTTP/HTTPS)**, designed
for **VXLAN BGP-EVPN fabrics with many VRFs**.

It lets an LLM client (Claude Code, Claude Desktop, etc.) safely:

1. Run **validated `show` commands** on one or many devices (fan-out).
2. Troubleshoot **VXLAN/EVPN**, **vPC**, **underlay** (OSPF/IS-IS/BGP), and
   **per-VRF reachability** (routing, ARP, BGP, ping, traceroute).
3. Follow guided **troubleshooting skills** (runbooks) that chain tools in the
   right order.

The server **never** changes device configuration: commands are validated against
a strict allowlist, and anything that could mutate state (config terminal, reload,
write, etc.) is rejected and audit-logged.

## Features

- **FastMCP-style server** using the official MCP Python SDK — `stdio` by default,
  `streamable-http` (bearer-token auth) optional.
- **NX-API client** (`httpx`, fully async, JSON-RPC / `cli_show` in the `ins_api`
  message format) with typed errors, timeouts and retries.
- **Guardrails**:
  - allowlist/denylist command validation (`config/guardrails.yaml`)
  - per-device token-bucket rate limiting + concurrency semaphore
  - secret redaction in all outputs (`config/redaction.yaml`)
  - JSON-lines audit log of every command attempted
  - output size caps and fan-out limits
- **Curated tools** per troubleshooting domain: `generic`, `vxlan`, `vrf`,
  `underlay`, `vpc_l2`, `health`.
- **Runbook skills** (`src/nxos_mcp/skills/`) exposed as MCP prompts, guiding
  the model through common failure scenarios.

## Quick start

```bash
# with uv
uv sync
cp config/inventory.example.yaml config/inventory.yaml   # edit for your fabric
cp .env.example .env                                     # set credentials

# stdio (default) — register in your MCP client:
uv run nxos-mcp
# or
uv run python -m nxos_mcp

# streamable-http with bearer auth
NXOS_TRANSPORT=streamable-http NXOS_HTTP_BEARER_TOKEN=secret uv run nxos-mcp
```

Register with Claude Code:

```bash
claude mcp add nxos-mcp -- <repo>/nxos-mcp/.venv/bin/nxos-mcp
```

### Docker

```bash
docker build -t nxos-mcp .
docker run --rm -i \
  -e NXOS_USERNAME -e NXOS_PASSWORD \
  -v "$PWD/config:/app/config:ro" \
  nxos-mcp
```

## Configuration

| File | Purpose |
| --- | --- |
| `config/inventory.yaml` | Devices (hostname, address, role spine/leaf/border, site, VRF hints) |
| `config/guardrails.yaml` | Command allowlist/denylist, rate limits, concurrency, output caps |
| `config/redaction.yaml` | Regexes for scrubbing secrets from command output |

Settings are environment-driven (prefix `NXOS_`); see `.env.example` for the full list.

## Development

```bash
uv sync --extra dev
uv run pytest            # unit tests (respx-mocked NX-API)
uv run pytest -m integration  # live device tests (NXOS_INTEGRATION=1)
uv run ruff check .
uv run mypy              # strict
```

## Security

This server is **read-only by design**. See [SECURITY.md](SECURITY.md) for the
guarantees, threat model, and how to report issues.

## License

Apache-2.0
