from .command_policy import validate_command
from .errors import PolicyError


def validate_batch(commands: list[str], max_commands: int = 8) -> list[str]:
    if not isinstance(commands, list) or not commands:
        raise PolicyError("Batch must contain at least one command.")
    if len(commands) > max_commands:
        raise PolicyError(f"Batch exceeds maximum of {max_commands} commands.")
    # Validate all commands before the caller executes any of them.
    return [validate_command(command) for command in commands]


def limit_output(output: str, max_bytes: int) -> tuple[str, bool]:
    data = output.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return output, False
    return data[:max_bytes].decode("utf-8", errors="ignore"), True
