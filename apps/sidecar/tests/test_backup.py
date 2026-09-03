from __future__ import annotations

import json
import zipfile
from pathlib import Path

from dmc_sidecar import config
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.backup import create_backup_archive, restore_backup_archive
from dmc_sidecar.db import get_database_metadata, migrate_database


def test_sidecar_migrations_report_latest_version(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    version = migrate_database(config.sqlite_path())
    metadata = get_database_metadata(config.sqlite_path())

    assert version == 5
    assert metadata["schema_version"] == 5
    assert "job" in metadata["tables"]
    assert "job_record" in metadata["tables"]
    assert "schema_migrations" in metadata["tables"]


def test_sidecar_backup_archive_round_trip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("backup-job", "graduation", "source.xlsx")
    sample_report = config.reports_dir() / "report.json"
    sample_report.write_text('{"ok":true}', encoding="utf-8")
    sample_config = config.configs_dir() / "graduation.json"
    sample_config.write_text("{}", encoding="utf-8")
    sample_profile_cache = config.profiles_dir() / "profile-1" / "Cache" / "blob"
    sample_profile_cache.parent.mkdir(parents=True, exist_ok=True)
    sample_profile_cache.write_bytes(b"browser-cache")

    archive_path = create_backup_archive(tmp_path / "backup.zip")
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["kind"] == "dmc-sidecar-backup"
        assert "desktop.sqlite3" in manifest["files"]
        assert "reports/report.json" in manifest["files"]
        assert all(not item.startswith("profiles/") for item in manifest["files"])

    store.set_status("backup-job", "failed")
    sample_report.write_text('{"ok":false}', encoding="utf-8")

    result = restore_backup_archive(archive_path)
    restored = store.get_status("backup-job")

    assert restored is not None
    assert restored["status"] == "pending"
    assert sample_report.read_text(encoding="utf-8") == '{"ok":true}'
    assert Path(result["safety_backup_path"]).exists()
