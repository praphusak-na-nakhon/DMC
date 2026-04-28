from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.db import connect
from app.main import app
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
    assert all(item["requires_credits"] is True for item in catalog.json()["modules"])
    assert all(item["credit_per_unit"] == 1 for item in catalog.json()["modules"])

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
