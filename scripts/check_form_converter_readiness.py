from __future__ import annotations

import json
from pathlib import Path

from dmc_sidecar.ai.registry import build_provider_registry


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_DOC = REPO_ROOT / "docs" / "form-converter-ocr-policy.md"
READINESS_DOC = REPO_ROOT / "docs" / "form-converter-production-readiness.md"


class _ReadinessSecretStore:
    """Provider-registration double that deliberately never accesses a keyring."""

    def get(self, provider: str) -> str | None:
        return None

    def set(self, provider: str, secret: str) -> None:
        return None

    def delete(self, provider: str) -> bool:
        return False


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    try:
        from keyring.backends.Windows import WinVaultKeyring
    except Exception as exc:
        raise SystemExit("Windows Credential Manager keyring backend is unavailable.") from exc

    registry = build_provider_registry(_ReadinessSecretStore())
    require(registry.supported_provider_ids() == ["gemini"], "Only the local Gemini OCR provider must be registered.")
    require(callable(WinVaultKeyring), "Windows Credential Manager keyring backend is unavailable.")
    require(POLICY_DOC.exists(), "Form converter OCR policy doc is missing.")
    require(READINESS_DOC.exists(), "Form converter readiness doc is missing.")

    print(
        json.dumps(
            {
                "status": "ok",
                "providers": registry.supported_provider_ids(),
                "credential_backend": "keyring.backends.Windows.WinVaultKeyring",
                "credential_read_performed": False,
                "real_provider_connection_test_performed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
