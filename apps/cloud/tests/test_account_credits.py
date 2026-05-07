from __future__ import annotations

import sys
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from fastapi.testclient import TestClient
import base64
import hashlib

from app.config import settings
from app.db import connect
from app.main import app
from app.schemas import OcrFieldResponse, OcrFormConverterResponse, OcrRecordResponse
from app.telemetry_store import TelemetryStore

_SCRIPT_SPEC = spec_from_file_location(
    "manage_accounts",
    Path(__file__).resolve().parents[1] / "scripts" / "manage_accounts.py",
)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
manage_accounts = module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(manage_accounts)


client = TestClient(app)


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "cloud-account.sqlite3"))
    monkeypatch.setattr(settings, "api_bearer_token", "dmc-test-token")


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer dmc-test-token"}


def _create_user(monkeypatch, tmp_path: Path) -> str:
    _configure(monkeypatch, tmp_path)
    response = client.post(
        "/v1/admin/users",
        headers=_admin_headers(),
        json={
            "email": "teacher@example.test",
            "password": "correct-password",
            "display_name": "Teacher",
            "status": "active",
        },
    )
    assert response.status_code == 200
    return str(response.json()["user_id"])


def _login() -> str:
    response = client.post(
        "/v1/auth/login",
        json={
            "email": "teacher@example.test",
            "password": "correct-password",
            "device_id": "device-1",
            "device_name": "desktop-1",
            "app_version": "0.1.0",
        },
    )
    assert response.status_code == 200
    return str(response.json()["token"])


def test_account_login_success_fail_logout(monkeypatch, tmp_path: Path) -> None:
    _create_user(monkeypatch, tmp_path)

    failed = client.post(
        "/v1/auth/login",
        json={
            "email": "teacher@example.test",
            "password": "wrong-password",
            "device_id": "device-1",
            "device_name": "desktop-1",
            "app_version": "0.1.0",
        },
    )
    assert failed.status_code == 401

    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/v1/auth/me", headers=headers).status_code == 200
    with connect(Path(settings.sqlite_path)) as connection:
        connection.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = ?",
            ("2020-01-01T00:00:00Z", token),
        )
    assert client.get("/v1/auth/me", headers=headers).status_code == 401

    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_admin_password_change_revokes_existing_sessions(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/v1/auth/me", headers=headers).status_code == 200

    response = client.patch(
        f"/v1/admin/users/{user_id}",
        headers=_admin_headers(),
        json={"password": "new-correct-password"},
    )
    assert response.status_code == 200
    assert client.get("/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/v1/auth/login",
            json={
                "email": "teacher@example.test",
                "password": "correct-password",
                "device_id": "device-1",
                "device_name": "desktop-1",
                "app_version": "0.1.0",
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/auth/login",
            json={
                "email": "teacher@example.test",
                "password": "new-correct-password",
                "device_id": "device-1",
                "device_name": "desktop-1",
                "app_version": "0.1.0",
            },
        ).status_code
        == 200
    )


def test_failed_login_rate_limit_does_not_block_successful_login(monkeypatch, tmp_path: Path) -> None:
    _create_user(monkeypatch, tmp_path)

    payload = {
        "email": "teacher@example.test",
        "password": "wrong-password",
        "device_id": "device-1",
        "device_name": "desktop-1",
        "app_version": "0.1.0",
    }
    for _ in range(10):
        assert client.post("/v1/auth/login", json=payload).status_code == 401
    assert client.post("/v1/auth/login", json=payload).status_code == 429

    payload["password"] = "correct-password"
    assert client.post("/v1/auth/login", json=payload).status_code == 200


def test_manual_topup_wallet_and_reservation_flow(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    topup = client.post(
        f"/v1/admin/users/{user_id}/credits/topup",
        headers=_admin_headers(),
        json={"amount": 5, "idempotency_key": "topup-1", "note": "manual payment"},
    )
    assert topup.status_code == 200
    assert topup.json()["balance"] == 5
    assert topup.json()["available"] == 5

    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    reserve = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "job-credit-1",
            "module": "graduation",
            "units": 3,
            "idempotency_key": "reserve-1",
        },
    )
    assert reserve.status_code == 200
    reservation = reserve.json()
    assert reservation["units_reserved"] == 3
    assert reservation["wallet"] == {"user_id": user_id, "balance": 5, "reserved": 3, "available": 2}

    repeated = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "job-credit-1",
            "module": "graduation",
            "units": 3,
            "idempotency_key": "reserve-1",
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["reservation_id"] == reservation["reservation_id"]

    same_job_new_key = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "job-credit-1",
            "module": "graduation",
            "units": 3,
            "idempotency_key": "reserve-1-new-key",
        },
    )
    assert same_job_new_key.status_code == 409

    new_job_same_key = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "job-credit-1-new-job",
            "module": "graduation",
            "units": 3,
            "idempotency_key": "reserve-1",
        },
    )
    assert new_job_same_key.status_code == 409

    capture = client.post(
        f"/v1/credits/reservations/{reservation['reservation_id']}/capture",
        headers=headers,
        json={"units": 2, "idempotency_key": "capture-1"},
    )
    assert capture.status_code == 200
    assert capture.json()["units_captured"] == 2
    assert capture.json()["wallet"] == {"user_id": user_id, "balance": 3, "reserved": 1, "available": 2}

    release = client.post(
        f"/v1/credits/reservations/{reservation['reservation_id']}/release",
        headers=headers,
        json={"units": 1, "idempotency_key": "release-1"},
    )
    assert release.status_code == 200
    assert release.json()["status"] == "captured"
    assert release.json()["units_released"] == 1
    assert release.json()["wallet"] == {"user_id": user_id, "balance": 3, "reserved": 0, "available": 3}

    ledger = client.get(f"/v1/admin/users/{user_id}/ledger", headers=_admin_headers())
    assert ledger.status_code == 200
    assert sorted(entry["type"] for entry in ledger.json()) == ["capture", "release", "reserve", "topup"]


def test_admin_topup_request_approval_records_audit(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    created = client.post(
        f"/v1/admin/users/{user_id}/credits/topup-requests",
        headers=_admin_headers(),
        json={"amount": 12, "payment_reference": "receipt-12", "note": "manual transfer verified"},
    )
    assert created.status_code == 200
    topup_request = created.json()
    assert topup_request["status"] == "pending"
    assert topup_request["wallet"] is None

    listed = client.get("/v1/admin/credits/topup-requests?status=pending", headers=_admin_headers())
    assert listed.status_code == 200
    assert [item["request_id"] for item in listed.json()] == [topup_request["request_id"]]

    approved = client.post(
        f"/v1/admin/credits/topup-requests/{topup_request['request_id']}/decision",
        headers=_admin_headers(),
        json={"decision": "approved", "idempotency_key": "approval-12"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["wallet"]["balance"] == 12

    repeated = client.post(
        f"/v1/admin/credits/topup-requests/{topup_request['request_id']}/decision",
        headers=_admin_headers(),
        json={"decision": "approved", "idempotency_key": "approval-12"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "approved"

    wallet = client.get(f"/v1/admin/users/{user_id}/wallet", headers=_admin_headers())
    assert wallet.status_code == 200
    assert wallet.json()["balance"] == 12

    audit = client.get("/v1/admin/audit", headers=_admin_headers())
    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()]
    assert "credit_topup_request.created" in actions
    assert "credit_topup_request.approved" in actions
    assert all(not entry["actor"].endswith("dmc-test-token") for entry in audit.json())


def test_admin_user_management_endpoints(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)

    listed = client.get("/v1/admin/users", headers=_admin_headers())
    assert listed.status_code == 200
    assert [user["user_id"] for user in listed.json()] == [user_id]

    updated = client.patch(
        f"/v1/admin/users/{user_id}",
        headers=_admin_headers(),
        json={"display_name": "Updated Teacher", "status": "disabled"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated Teacher"
    assert updated.json()["status"] == "disabled"

    login = client.post(
        "/v1/auth/login",
        json={
            "email": "teacher@example.test",
            "password": "correct-password",
            "device_id": "device-1",
            "device_name": "desktop-1",
            "app_version": "0.1.0",
        },
    )
    assert login.status_code == 403

    reenabled = client.patch(
        f"/v1/admin/users/{user_id}",
        headers=_admin_headers(),
        json={"password": "new-password", "status": "active"},
    )
    assert reenabled.status_code == 200
    assert client.get(f"/v1/admin/users/{user_id}/wallet", headers=_admin_headers()).json()["balance"] == 0

    changed_login = client.post(
        "/v1/auth/login",
        json={
            "email": "teacher@example.test",
            "password": "new-password",
            "device_id": "device-1",
            "device_name": "desktop-1",
            "app_version": "0.1.0",
        },
    )
    assert changed_login.status_code == 200


def test_admin_account_script_topup_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "manage_accounts.py",
            "create-user",
            "--email",
            "script@example.test",
            "--password",
            "correct-password",
            "--display-name",
            "Script User",
        ],
    )
    manage_accounts.main()

    for _ in range(2):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "manage_accounts.py",
                "topup",
                "--email",
                "script@example.test",
                "--amount",
                "25",
                "--idempotency-key",
                "script-topup-1",
            ],
        )
        manage_accounts.main()

    user = client.post(
        "/v1/auth/login",
        json={
            "email": "script@example.test",
            "password": "correct-password",
            "device_id": "device-1",
            "device_name": "desktop-1",
            "app_version": "0.1.0",
        },
    ).json()
    wallet = client.get("/v1/wallet", headers={"Authorization": f"Bearer {user['token']}"})
    assert wallet.status_code == 200
    assert wallet.json()["balance"] == 25


def test_admin_account_script_seed_user_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    for _ in range(2):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "manage_accounts.py",
                "seed-user",
                "--email",
                "seed@example.test",
                "--password",
                "correct-password",
                "--display-name",
                "Seed User",
            ],
        )
        manage_accounts.main()

    users = client.get("/v1/admin/users", headers=_admin_headers())
    assert users.status_code == 200
    assert [user["email"] for user in users.json()] == ["seed@example.test"]

    login = client.post(
        "/v1/auth/login",
        json={
            "email": "seed@example.test",
            "password": "correct-password",
            "device_id": "device-1",
            "device_name": "desktop-1",
            "app_version": "0.1.0",
        },
    )
    assert login.status_code == 200


def test_reserve_insufficient_credit_and_module_catalog(monkeypatch, tmp_path: Path) -> None:
    _create_user(monkeypatch, tmp_path)
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}

    catalog = client.get("/v1/modules/catalog", headers=headers)
    assert catalog.status_code == 200
    modules = {item["id"]: item for item in catalog.json()["modules"]}
    assert modules["psar"]["requires_credits"] is False
    assert modules["psar"]["credit_per_unit"] == 0
    assert all(
        item["requires_credits"] is True
        for module_id, item in modules.items()
        if module_id != "psar"
    )
    assert all(
        item["credit_per_unit"] == 1
        for module_id, item in modules.items()
        if module_id != "psar"
    )

    reserve = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "job-credit-low",
            "module": "graduation",
            "units": 1,
            "idempotency_key": "reserve-low",
        },
    )
    assert reserve.status_code == 402


def test_telemetry_accepts_account_session_but_rejects_email_pii(monkeypatch, tmp_path: Path) -> None:
    _create_user(monkeypatch, tmp_path)
    token = _login()
    store = TelemetryStore(settings.sqlite_path)
    response = client.post(
        "/v1/telemetry",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "events": [
                {
                    "event": "app_started",
                    "ts": "2026-04-22T00:00:00Z",
                    "app_version": "0.1.0",
                    "platform": "windows",
                    "email": "teacher@example.test",
                }
            ]
        },
    )
    assert response.status_code == 422
    assert store.count() == 0


def test_form_converter_ocr_requires_login_and_returns_mock_records(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    topup = client.post(
        f"/v1/admin/users/{user_id}/credits/topup",
        headers=_admin_headers(),
        json={"amount": 5, "idempotency_key": "topup-ocr"},
    )
    assert topup.status_code == 200
    token = _login()
    reservation = client.post(
        "/v1/credits/reservations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-cloud-1",
            "module": "formConverter",
            "units": 1,
            "idempotency_key": "reserve-ocr",
        },
    )
    assert reservation.status_code == 200
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF"
    payload = {
        "job_id": "form-job-cloud-1",
        "module": "formConverter",
        "template_type": "student_history_v1",
        "page_count": 1,
        "credit_reservation_id": reservation.json()["reservation_id"],
        "document_sha256": hashlib.sha256(document).hexdigest(),
        "document_base64": base64.b64encode(document).decode("ascii"),
    }
    telemetry = TelemetryStore(settings.sqlite_path)

    unauthenticated = client.post("/v1/ocr/form-converter", json=payload)
    assert unauthenticated.status_code == 401

    response = client.post("/v1/ocr/form-converter", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["module"] == "formConverter"
    assert body["provider"] == "mock-form-ocr-v1"
    assert body["records"][0]["status"] == "needs_review"
    assert {field["field_name"] for field in body["records"][0]["fields"]} >= {
        "student_id",
        "first_name",
        "last_name",
    }
    wallet = client.get("/v1/wallet", headers={"Authorization": f"Bearer {token}"})
    assert wallet.status_code == 200
    assert wallet.json()["balance"] == 4
    assert wallet.json()["reserved"] == 0
    assert telemetry.count() == 0


def test_form_converter_ocr_openai_provider_uses_pdf_file_input(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 5, "idempotency_key": "topup-openai-ocr"},
        ).status_code
        == 200
    )
    token = _login()
    reservation = client.post(
        "/v1/credits/reservations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-openai-1",
            "module": "formConverter",
            "units": 1,
            "idempotency_key": "reserve-openai-ocr",
        },
    ).json()
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF"
    captured_payloads: list[dict[str, object]] = []

    class FakeOpenAiResponse:
        def __enter__(self) -> "FakeOpenAiResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "records": [
                                {
                                    "record_id": "page-1",
                                    "page_number": 1,
                                    "status": "needs_review",
                                    "fields": [
                                        {
                                            "field_name": "student_id",
                                            "label_th": "เลขประจำตัวนักเรียน",
                                            "value": "12345",
                                            "confidence": 0.92,
                                            "status": "needs_review",
                                            "alternatives": [],
                                        }
                                    ],
                                }
                            ]
                        }
                    )
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout: int) -> FakeOpenAiResponse:
        assert timeout == 90
        captured_payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeOpenAiResponse()

    monkeypatch.setattr(settings, "ocr_provider", "openai")
    monkeypatch.setattr(settings, "ocr_openai_api_key", "test-openai-key")
    monkeypatch.setattr("app.ocr_service.urllib.request.urlopen", fake_urlopen)

    response = client.post(
        "/v1/ocr/form-converter",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-openai-1",
            "module": "formConverter",
            "template_type": "student_history_v1",
            "page_count": 1,
            "credit_reservation_id": reservation["reservation_id"],
            "document_sha256": hashlib.sha256(document).hexdigest(),
            "document_base64": base64.b64encode(document).decode("ascii"),
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"].startswith("openai-responses:")
    content = captured_payloads[0]["input"][0]["content"]  # type: ignore[index]
    file_item = content[0]  # type: ignore[index]
    assert file_item["type"] == "input_file"  # type: ignore[index]
    assert file_item["file_data"].startswith("data:application/pdf;base64,")  # type: ignore[index]


def test_form_converter_ocr_gemini_provider_uploads_pdf_and_deletes_file(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 5, "idempotency_key": "topup-gemini-ocr"},
        ).status_code
        == 200
    )
    token = _login()
    reservation = client.post(
        "/v1/credits/reservations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-gemini-1",
            "module": "formConverter",
            "units": 1,
            "idempotency_key": "reserve-gemini-ocr",
        },
    ).json()
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF"
    calls: list[tuple[str, str, bytes | None]] = []
    generate_payloads: list[dict[str, object]] = []

    class FakeGeminiResponse:
        def __init__(self, payload: dict[str, object], headers: dict[str, str] | None = None) -> None:
            self._payload = payload
            self.headers = headers or {}

        def __enter__(self) -> "FakeGeminiResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

    def fake_urlopen(request, timeout: int) -> FakeGeminiResponse:
        assert timeout in {20, 90}
        method = request.get_method()
        url = request.full_url
        data = request.data
        calls.append((method, url, data))
        if "/upload/v1beta/files" in url:
            headers = dict(request.header_items())
            assert headers["X-goog-upload-protocol"] == "resumable"
            assert headers["X-goog-upload-header-content-type"] == "application/pdf"
            return FakeGeminiResponse({}, {"X-Goog-Upload-URL": "https://upload.example.test/session"})
        if url == "https://upload.example.test/session":
            assert data == document
            return FakeGeminiResponse(
                {
                    "file": {
                        "name": "files/form-test",
                        "uri": "https://generativelanguage.googleapis.com/v1beta/files/form-test",
                    }
                }
            )
        if ":generateContent" in url:
            assert data is not None
            payload = json.loads(data.decode("utf-8"))
            generate_payloads.append(payload)
            return FakeGeminiResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "records": [
                                                    {
                                                        "record_id": "page-1",
                                                        "page_number": 1,
                                                        "status": "needs_review",
                                                        "fields": [
                                                            {
                                                                "field_name": "student_id",
                                                                "label_th": "เลขประจำตัวนักเรียน",
                                                                "value": "12345",
                                                                "confidence": 0.92,
                                                                "status": "needs_review",
                                                                "alternatives": [],
                                                            }
                                                        ],
                                                    }
                                                ]
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
        if method == "DELETE" and "/v1beta/files/form-test" in url:
            return FakeGeminiResponse({})
        raise AssertionError(f"Unexpected Gemini request: {method} {url}")

    monkeypatch.setattr(settings, "ocr_provider", "gemini")
    monkeypatch.setattr(settings, "ocr_gemini_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "ocr_gemini_model", "gemini-2.5-flash-lite")
    monkeypatch.setattr("app.ocr_service.urllib.request.urlopen", fake_urlopen)

    response = client.post(
        "/v1/ocr/form-converter",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-gemini-1",
            "module": "formConverter",
            "template_type": "student_history_v1",
            "page_count": 1,
            "credit_reservation_id": reservation["reservation_id"],
            "document_sha256": hashlib.sha256(document).hexdigest(),
            "document_base64": base64.b64encode(document).decode("ascii"),
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"].startswith("gemini-generate-content:")
    assert [call[0] for call in calls] == ["POST", "POST", "POST", "DELETE"]
    parts = generate_payloads[0]["contents"][0]["parts"]  # type: ignore[index]
    assert parts[0]["text"].startswith("Read the scanned Thai DMC student history form PDF.")  # type: ignore[index]
    assert parts[1]["fileData"] == {  # type: ignore[index]
        "mimeType": "application/pdf",
        "fileUri": "https://generativelanguage.googleapis.com/v1beta/files/form-test",
    }


def test_form_converter_ocr_gemini_provider_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 5, "idempotency_key": "topup-gemini-key"},
        ).status_code
        == 200
    )
    token = _login()
    reservation = client.post(
        "/v1/credits/reservations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-gemini-missing-key",
            "module": "formConverter",
            "units": 1,
            "idempotency_key": "reserve-gemini-key",
        },
    ).json()
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF"
    monkeypatch.setattr(settings, "ocr_provider", "gemini")
    monkeypatch.setattr(settings, "ocr_gemini_api_key", "")

    response = client.post(
        "/v1/ocr/form-converter",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-gemini-missing-key",
            "module": "formConverter",
            "template_type": "student_history_v1",
            "page_count": 1,
            "credit_reservation_id": reservation["reservation_id"],
            "document_sha256": hashlib.sha256(document).hexdigest(),
            "document_base64": base64.b64encode(document).decode("ascii"),
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OCR_GEMINI_API_KEY_MISSING"


def test_form_converter_ocr_enforces_pdf_limits(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 5, "idempotency_key": "topup-ocr-limits"},
        ).status_code
        == 200
    )
    token = _login()
    reservation = client.post(
        "/v1/credits/reservations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "job_id": "form-job-limits-1",
            "module": "formConverter",
            "units": 2,
            "idempotency_key": "reserve-ocr-limits",
        },
    ).json()
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF"
    payload = {
        "job_id": "form-job-limits-1",
        "module": "formConverter",
        "template_type": "student_history_v1",
        "page_count": 2,
        "credit_reservation_id": reservation["reservation_id"],
        "document_sha256": hashlib.sha256(document).hexdigest(),
        "document_base64": base64.b64encode(document).decode("ascii"),
    }

    monkeypatch.setattr(settings, "ocr_max_pages_per_job", 1)
    response = client.post("/v1/ocr/form-converter", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response.status_code == 413
    assert response.json()["detail"] == "OCR_PAGE_LIMIT_EXCEEDED"

    monkeypatch.setattr(settings, "ocr_max_pages_per_job", 100)
    monkeypatch.setattr(settings, "ocr_max_pdf_bytes", 4)
    payload["page_count"] = 1
    response = client.post("/v1/ocr/form-converter", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response.status_code == 413
    assert response.json()["detail"] == "OCR_DOCUMENT_TOO_LARGE"


def test_form_converter_ocr_credit_ledger_end_to_end(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 3, "idempotency_key": "topup-form-e2e"},
        ).status_code
        == 200
    )
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    reservation = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "form-job-ledger-1",
            "module": "formConverter",
            "units": 2,
            "idempotency_key": "reserve-form-ledger-1",
        },
    ).json()
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n%%EOF"
    ocr = client.post(
        "/v1/ocr/form-converter",
        headers=headers,
        json={
            "job_id": "form-job-ledger-1",
            "module": "formConverter",
            "template_type": "student_history_v1",
            "page_count": 2,
            "credit_reservation_id": reservation["reservation_id"],
            "document_sha256": hashlib.sha256(document).hexdigest(),
            "document_base64": base64.b64encode(document).decode("ascii"),
        },
    )
    assert ocr.status_code == 200
    assert len(ocr.json()["records"]) == 2

    second_ocr = client.post(
        "/v1/ocr/form-converter",
        headers=headers,
        json={
            "job_id": "form-job-ledger-1",
            "module": "formConverter",
            "template_type": "student_history_v1",
            "page_count": 1,
            "credit_reservation_id": reservation["reservation_id"],
            "document_sha256": hashlib.sha256(document).hexdigest(),
            "document_base64": base64.b64encode(document).decode("ascii"),
        },
    )
    assert second_ocr.status_code == 402
    assert client.get("/v1/wallet", headers=headers).json() == {
        "user_id": user_id,
        "balance": 1,
        "reserved": 0,
        "available": 1,
    }

    ledger = client.get(f"/v1/admin/users/{user_id}/ledger", headers=_admin_headers())
    assert ledger.status_code == 200
    ledger_pairs = {(entry["type"], entry["module"]) for entry in ledger.json()}
    assert ledger_pairs == {
        ("topup", None),
        ("reserve", "formConverter"),
        ("capture", "formConverter"),
    }


def test_form_converter_ocr_retry_uses_cached_response_without_double_capture(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 3, "idempotency_key": "topup-form-retry"},
        ).status_code
        == 200
    )
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    reservation = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "form-job-retry-1",
            "module": "formConverter",
            "units": 2,
            "idempotency_key": "reserve-form-retry-1",
        },
    ).json()
    calls = {"count": 0}

    def fake_ocr(_request) -> OcrFormConverterResponse:  # noqa: ANN001
        calls["count"] += 1
        return OcrFormConverterResponse(
            job_id="form-job-retry-1",
            module="formConverter",
            template_type="student_history_v1",
            provider="test-provider",
            records=[
                OcrRecordResponse(
                    record_id="record-1",
                    page_number=1,
                    status="ready",
                    fields=[
                        OcrFieldResponse(
                            field_name="student_id",
                            label_th="เลขประจำตัว",
                            value="1001",
                            confidence=0.99,
                            status="ready",
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr("app.routes.ocr.run_form_converter_ocr", fake_ocr)
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n%%EOF"
    payload = {
        "job_id": "form-job-retry-1",
        "module": "formConverter",
        "template_type": "student_history_v1",
        "page_count": 2,
        "credit_reservation_id": reservation["reservation_id"],
        "document_sha256": hashlib.sha256(document).hexdigest(),
        "document_base64": base64.b64encode(document).decode("ascii"),
    }

    first = client.post("/v1/ocr/form-converter", headers=headers, json=payload)
    second = client.post("/v1/ocr/form-converter", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert calls["count"] == 1
    assert client.get("/v1/wallet", headers=headers).json() == {
        "user_id": user_id,
        "balance": 1,
        "reserved": 0,
        "available": 1,
    }
    ledger = client.get(f"/v1/admin/users/{user_id}/ledger", headers=_admin_headers()).json()
    capture_entries = [entry for entry in ledger if entry["type"] == "capture"]
    assert len(capture_entries) == 1
    assert capture_entries[0]["amount"] == 2


def test_form_converter_ocr_stale_captured_request_does_not_call_provider(monkeypatch, tmp_path: Path) -> None:
    user_id = _create_user(monkeypatch, tmp_path)
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/credits/topup",
            headers=_admin_headers(),
            json={"amount": 3, "idempotency_key": "topup-form-stale"},
        ).status_code
        == 200
    )
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    reservation = client.post(
        "/v1/credits/reservations",
        headers=headers,
        json={
            "job_id": "form-job-stale-1",
            "module": "formConverter",
            "units": 2,
            "idempotency_key": "reserve-form-stale-1",
        },
    ).json()
    document = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n%%EOF"
    document_sha = hashlib.sha256(document).hexdigest()
    capture_key = (
        f"ocr:form-converter:form-job-stale-1:{reservation['reservation_id']}:"
        f"student_history_v1:{document_sha}:2:capture"
    )
    capture = client.post(
        f"/v1/credits/reservations/{reservation['reservation_id']}/capture",
        headers=headers,
        json={"units": 2, "idempotency_key": capture_key},
    )
    assert capture.status_code == 200

    def fake_ocr(_request) -> OcrFormConverterResponse:  # noqa: ANN001
        raise AssertionError("provider should not be called after a captured OCR request")

    monkeypatch.setattr("app.routes.ocr.run_form_converter_ocr", fake_ocr)
    response = client.post(
        "/v1/ocr/form-converter",
        headers=headers,
        json={
            "job_id": "form-job-stale-1",
            "module": "formConverter",
            "template_type": "student_history_v1",
            "page_count": 2,
            "credit_reservation_id": reservation["reservation_id"],
            "document_sha256": document_sha,
            "document_base64": base64.b64encode(document).decode("ascii"),
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "OCR request was already captured but cached response is unavailable"
