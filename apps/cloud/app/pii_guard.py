from __future__ import annotations

import re
from typing import Any


PII_FIELD_PATTERN = re.compile(
    r"^(student(?:_|$)|first_name$|last_name$|full_name$|citizen(?:_|$)|name$|.*_name$|"
    r"email$|.*_email$|phone$|.*_phone$|address$|.*_address$|birth_date$|date_of_birth$|"
    r"national_id$|citizen_id$|thai_id$|id_card$)"
)
PII_VALUE_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    re.compile(r"(?<!\d)(?:\+66|0)\d{8,9}(?!\d)"),
    re.compile(r"(?<!\d)\d{13}(?!\d)"),
)


def _normalize_key(key: str) -> str:
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return key.replace("-", "_").lower()


def assert_payload_is_telemetry_safe(payload: Any, *, path: str = "payload") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if PII_FIELD_PATTERN.match(_normalize_key(key)):
                raise ValueError(f"PII field '{key}' is not allowed in telemetry at {path}")
            assert_payload_is_telemetry_safe(value, path=f"{path}.{key}")
        return

    if isinstance(payload, list):
        for index, item in enumerate(payload):
            assert_payload_is_telemetry_safe(item, path=f"{path}[{index}]")
        return

    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
            try:
                import json

                assert_payload_is_telemetry_safe(json.loads(stripped), path=path)
            except json.JSONDecodeError:
                pass
        for pattern in PII_VALUE_PATTERNS:
            if pattern.search(payload):
                raise ValueError(f"PII value is not allowed in telemetry at {path}")
