# Security Policy — nxos-mcp

## Read-only guarantee

This server is designed so that it **cannot** change device configuration:

1. **Allowlist validation.** Every command is matched against the allowlist in
   `config/guardrails.yaml` (anchored patterns) *before* it is sent to a device.
   Anything not explicitly allowed is rejected.
2. **Denylist backstop.** Even allowlisted patterns are re-checked against a
   denylist of state-changing verbs (`configure`, `conf t`, `reload`, `write`,
   `copy`, `erase`, `clear`, `debug`, `shutdown`, …) and shell escapes
   (`;`, `|`, `&&`, backticks, `$(`).
3. **Structured NX-API mode.** Commands are sent as `cli_show` (read-only
   message type) via the `ins_api` JSON-RPC format, not as raw CLI.
4. **Audit log.** Every command attempt — allowed or denied — is appended to a
   JSON-lines audit log with device, command, caller, and verdict.
5. **Rate limits + caps.** Per-device token bucket and concurrency semaphore;
   output size and fan-out limits prevent the server being used to DoS a switch.

## Threat model

- **Prompt injection via device output**: command output is treated as data,
  never as instructions; secrets are redacted via `config/redaction.yaml`
  before being returned to the LLM.
- **Credential handling**: NX-API credentials come from environment variables
  or `.env` (never committed; see `.env.example`). They are never logged,
  never included in tool results, and never sent to any host other than the
  inventory-configured device address.
- **Transport**: HTTPS is expected. Plain HTTP requires an explicit
  `NXOS_ALLOW_HTTP=true` and is intended for lab use only;
  `NXOS_ALLOW_INSECURE=true` disables TLS certificate verification (lab only).
- **streamable-http transport**: requires a bearer token
  (`NXOS_HTTP_BEARER_TOKEN`); bind to `127.0.0.1` by default.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Advisories) or
contact the maintainers directly. Do **not** open a public issue for
security-relevant bugs.
