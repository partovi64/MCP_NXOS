"""Normalize NX-API JSON into compact, LLM-friendly structures."""

from __future__ import annotations

from typing import Any

from nxos_mcp.nxapi.models import normalize_table_rows


def rows(payload: Any, *table_hints: str) -> list[dict[str, Any]]:
    if not table_hints:
        return normalize_table_rows(payload)
    current = payload
    for hint in table_hints:
        if isinstance(current, dict) and hint in current:
            current = current[hint]
        else:
            return normalize_table_rows(payload)
    return normalize_table_rows(current)


def pick(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def summarize_peers(
    rows_in: list[dict[str, Any]], state_keys: tuple[str, ...] = ("state",)
) -> dict[str, Any]:
    up = 0
    down = 0
    for row in rows_in:
        state = str(pick(row, *state_keys, default="")).lower()
        if state in {"up", "established", "peer-up", "oper-up"}:
            up += 1
        elif state:
            down += 1
    return {"count": len(rows_in), "up": up, "down": down, "anomalies": down}


def page(
    items: list[Any],
    *,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Any], dict[str, Any]]:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    sliced = items[offset : offset + limit]
    meta = {
        "offset": offset,
        "limit": limit,
        "returned": len(sliced),
        "total": len(items),
        "has_more": offset + limit < len(items),
    }
    return sliced, meta
