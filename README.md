# Cisco Show & Troubleshoot MCP

Read-only Cisco IOS/IOS-XE MCP starter scaffold with command allowlisting, explicit device inventory, audit records, skills, and tests. This is a starter project, not production-certified software.

## Install
Python 3.11+ required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
export CISCO_USERNAME="readonly-user"
export CISCO_PASSWORD="your-secret"
cisco-show-tshoot-mcp
```

Configure approved lab devices in `src/cisco_show_tshoot/inventory.py` before use. The inventory is empty by default. Do not commit credentials. Run `pytest` before testing against a lab device.

## Tools
- `cisco_list_devices`
- `cisco_show_command`
- `cisco_show_batch`
- `cisco_tshoot_interface`

## Safety notes
- Only allowlisted show commands are accepted.
- Batches are fully validated before execution.
- Unknown device aliases fail closed.
- No configuration-changing tools are exposed.
- Review SSH host-key verification, privilege level, audit retention, platform syntax, output sensitivity, and timeouts before production use.
- Skill files guide reasoning; server-side code enforces policy.
