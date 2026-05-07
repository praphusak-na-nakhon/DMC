from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.account_service import AccountRepository
from app.backup import create_backup_archive, restore_backup_archive
from app.config import settings
from app.db import get_database_metadata, migrate_database
from app.schemas import CloudCreditTopupRequest, CloudUserCreateRequest


def test_cloud_migrations_report_latest_version(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "cloud.sqlite3"
    monkeypatch.setattr(settings, "sqlite_path", str(sqlite_path))

    version = migrate_database(sqlite_path)
    metadata = get_database_metadata(sqlite_path)

    assert version == 7
    assert metadata["schema_version"] == 7
    assert "wallets" in metadata["tables"]
    assert "admin_audit_log" in metadata["tables"]
    assert "credit_topup_requests" in metadata["tables"]
    assert "schema_migrations" in metadata["tables"]


def test_cloud_backup_archive_round_trip(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "cloud.sqlite3"
    monkeypatch.setattr(settings, "sqlite_path", str(sqlite_path))

    service = AccountRepository(sqlite_path=str(sqlite_path))
    user = service.create_user(
        CloudUserCreateRequest(
            email="teacher@example.test",
            password="correct-password",
            display_name="Teacher",
            status="active",
        )
    )
    service.topup_user(
        user.user_id,
        CloudCreditTopupRequest(amount=500, note="initial", idempotency_key="backup-initial"),
    )

    archive_path = create_backup_archive(tmp_path / "cloud-backup.zip")
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["kind"] == "dmc-cloud-backup"
        assert manifest["schema"]["schema_version"] == 7

    service.topup_user(
        user.user_id,
        CloudCreditTopupRequest(amount=100, note="changed", idempotency_key="backup-changed"),
    )

    result = restore_backup_archive(archive_path)
    restored = service.get_user_admin(user.user_id)

    assert restored is not None
    assert restored.wallet.balance == 500
    assert restored.wallet.available == 500
    assert Path(result["safety_backup_path"]).exists()
