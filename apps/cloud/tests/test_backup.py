from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.backup import create_backup_archive, restore_backup_archive
from app.config import settings
from app.db import get_database_metadata, migrate_database
from app.license_service import LicenseRepository
from app.schemas import CloudLicenseUpsertRequest


def test_cloud_migrations_report_latest_version(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "cloud.sqlite3"
    monkeypatch.setattr(settings, "sqlite_path", str(sqlite_path))

    version = migrate_database(sqlite_path)
    metadata = get_database_metadata(sqlite_path)

    assert version == 3
    assert metadata["schema_version"] == 3
    assert "licenses" in metadata["tables"]
    assert "schema_migrations" in metadata["tables"]


def test_cloud_backup_archive_round_trip(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "cloud.sqlite3"
    monkeypatch.setattr(settings, "sqlite_path", str(sqlite_path))

    repo = LicenseRepository(sqlite_path=str(sqlite_path))
    repo.upsert_license(
        license_key="DMC-CLOUD-001",
        request=CloudLicenseUpsertRequest(
            license_key="DMC-CLOUD-001",
                license_tier="school_le_500",
                school_size_tier="le_500",
                billing_interval="annual",
            student_count_total=500,
            max_devices=5,
            status="active",
            expires_at="2027-04-22T00:00:00Z",
            modules_enabled=["graduation"],
        ),
    )

    archive_path = create_backup_archive(tmp_path / "cloud-backup.zip")
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["kind"] == "dmc-cloud-backup"
        assert manifest["schema"]["schema_version"] == 3

    repo.upsert_license(
        license_key="DMC-CLOUD-001",
        request=CloudLicenseUpsertRequest(
            license_key="DMC-CLOUD-001",
            license_tier="trial",
            school_size_tier="le_500",
            billing_interval=None,
            student_count_total=100,
            max_devices=1,
            status="suspended",
            expires_at="2027-04-22T00:00:00Z",
            modules_enabled=["graduation"],
        ),
    )

    result = restore_backup_archive(archive_path)
    restored = repo.get_license("DMC-CLOUD-001")

    assert restored is not None
    assert restored.license_tier == "school_le_500"
    assert restored.max_devices == 5
    assert Path(result["safety_backup_path"]).exists()
