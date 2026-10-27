import json
import os
from datetime import datetime, timezone


def audit_event(path: str, **fields) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\\n")
