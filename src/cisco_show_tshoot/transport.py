import os
from datetime import datetime, timezone
from time import monotonic
from netmiko import ConnectHandler
from .errors import DeviceError
from .guardrails import limit_output


def execute_show(device, command: str) -> dict:
    username, password = os.getenv("CISCO_USERNAME"), os.getenv("CISCO_PASSWORD")
    if not username or not password:
        raise DeviceError("CISCO_USERNAME and CISCO_PASSWORD must be set.")
    timeout = int(os.getenv("CISCO_COMMAND_TIMEOUT_SECONDS", "15"))
    max_bytes = int(os.getenv("CISCO_MAX_OUTPUT_BYTES", "200000"))
    started = monotonic()
    connection = None
    collected_at = datetime.now(timezone.utc).isoformat()
    try:
        connection = ConnectHandler(
            device_type=device.device_type, host=device.host,
            username=username, password=password,
            conn_timeout=timeout, auth_timeout=timeout,
            banner_timeout=timeout, read_timeout=timeout, fast_cli=False,
        )
        raw = connection.send_command(command, read_timeout=timeout,
                                      strip_prompt=True, strip_command=True)
        output, truncated = limit_output(raw, max_bytes)
        return {"device": device.alias, "command": command, "output": output,
                "collected_at": collected_at,
                "duration_ms": int((monotonic() - started) * 1000),
                "truncated": truncated, "status": "success"}
    except Exception as exc:
        raise DeviceError(
            f"Execution failed for device {device.alias!r} ({type(exc).__name__})."
        ) from exc
    finally:
        if connection is not None:
            try:
                connection.disconnect()
            except Exception:
                pass
