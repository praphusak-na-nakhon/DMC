from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import settings


def canonical_config_payload(version: str, payload: dict[str, object]) -> bytes:
    return json.dumps(
        {
            "version": version,
            "config": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def load_signing_private_key() -> Ed25519PrivateKey:
    key_hex = settings.config_signing_private_key_hex.strip()
    if not key_hex:
        raise RuntimeError("config signing private key is not configured")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key_hex))


def sign_config_payload(version: str, payload: dict[str, object]) -> str:
    key = load_signing_private_key()
    signature = key.sign(canonical_config_payload(version, payload))
    encoded = base64.b64encode(signature).decode("ascii")
    return f"ed25519:{settings.config_signing_key_id}:{encoded}"
