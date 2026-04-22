from __future__ import annotations

import re
from typing import Any


PII_FIELD_PATTERN = re.compile(r"^(student(?:_|$)|first_name$|last_name$|citizen(?:_|$))")


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
