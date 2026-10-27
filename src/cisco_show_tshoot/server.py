import json
import os
from mcp.server.fastmcp import FastMCP
from .audit import audit_event
from .command_policy import validate_command
from .errors import DeviceError, PolicyError
from .guardrails import validate_batch
from .inventory import get_device, list_devices
from .transport import execute_show

mcp = FastMCP("cisco-show-tshoot-mcp")


def run_one(alias: str, command: str, tool: str) -> dict:
    device = get_device(alias)
    command = validate_command(command)
    try:
        result = execute_show(device, command)
        audit_event(os.getenv("CISCO_AUDIT_PATH", "./audit.jsonl"),
                    actor="mcp-client", device=alias, tool=tool,
                    command=command, status="success",
                    duration_ms=result["duration_ms"])
        return result
    except Exception as exc:
        audit_event(os.getenv("CISCO_AUDIT_PATH", "./audit.jsonl"),
                    actor="mcp-client", device=alias, tool=tool,
                    command=command, status="error",
                    reason=type(exc).__name__)
        raise


@mcp.tool()
def cisco_list_devices() -> str:
    """List configured device aliases; no credentials are returned."""
    return json.dumps(list_devices(), indent=2)


@mcp.tool()
def cisco_show_command(device: str, command: str) -> str:
    """Execute one allowlisted read-only show command."""
    try:
        return json.dumps(run_one(device, command, "cisco_show_command"), indent=2)
    except (PolicyError, DeviceError) as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def cisco_show_batch(device: str, commands: list[str]) -> str:
    """Run a bounded batch after validating every command before execution."""
    try:
        safe = validate_batch(commands)
        get_device(device)
        results = [run_one(device, command, "cisco_show_batch") for command in safe]
        return json.dumps({"status": "success", "results": results}, indent=2)
    except (PolicyError, DeviceError) as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)


@mcp.tool()
def cisco_tshoot_interface(device: str, interface: str) -> str:
    """Collect read-only first-pass interface evidence."""
    if not interface or len(interface) > 64 or not all(
        c.isalnum() or c in "/.:_-" for c in interface
    ):
        return json.dumps({"status": "error", "error": "Invalid interface argument."})
    commands = ["show ip interface brief", f"show interfaces {interface}",
                "show interfaces counters errors"]
    try:
        safe = validate_batch(commands)
        get_device(device)
        evidence = [run_one(device, command, "cisco_tshoot_interface") for command in safe]
        return json.dumps({
            "status": "success", "device": device, "interface": interface,
            "evidence": evidence,
            "interpretation": "Correlate local and peer evidence. These outputs alone "
                              "may not establish root cause. No configuration changes were made."
        }, indent=2)
    except (PolicyError, DeviceError) as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
