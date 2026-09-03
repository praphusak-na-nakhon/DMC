from __future__ import annotations

import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest

from dmc_sidecar import backup, config, db
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.errors import DomainError
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.backup import create_backup_archive, restore_backup_archive
from dmc_sidecar.db import get_database_metadata, migrate_database


def test_sidecar_migrations_report_generation_two(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    version = migrate_database(config.sqlite_path())
    metadata = get_database_metadata(config.sqlite_path())

    assert version == 2
    assert metadata["schema_generation"] == 2
    assert set(metadata["tables"]) == {"job", "job_record", "schema_metadata"}
    assert "credit_status" not in metadata["job_columns"]


def _create_legacy_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY);
            INSERT INTO schema_migrations VALUES (5);
            CREATE TABLE job (id TEXT PRIMARY KEY, credit_status TEXT);
            INSERT INTO job VALUES ('old-job', 'reserved');
            CREATE TABLE account_session (token TEXT);
            INSERT INTO account_session VALUES ('obsolete-session');
            CREATE TABLE telemetry_queue (event_json TEXT);
        """)


def test_legacy_database_is_reset_to_retained_local_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    _create_legacy_database(config.sqlite_path())

    migrate_database(config.sqlite_path())

    metadata = get_database_metadata(config.sqlite_path())
    assert metadata["schema_generation"] == 2
    assert set(metadata["tables"]) == {"job", "job_record", "schema_metadata"}
    assert "credit_status" not in metadata["job_columns"]
    assert JobStore().list_jobs() == []
    JobStore().create_pending_job("new-job", "graduation", "source.xlsx")
    assert JobStore().get_status("new-job")["status"] == "pending"


def test_generation_mismatch_resets_but_same_generation_preserves_jobs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("retained", "graduation", "source.xlsx")
    assert get_database_metadata()["schema_generation"] == 2
    migrate_database()
    assert store.get_status("retained")["status"] == "pending"
    with db.connect() as connection:
        connection.execute("UPDATE schema_metadata SET generation = 1")

    migrate_database()

    assert get_database_metadata()["schema_generation"] == 2
    assert store.list_jobs() == []


def test_reset_failure_rolls_back_original_tables_and_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    _create_legacy_database(config.sqlite_path())
    original_baseline = db._baseline_schema

    def fail_after_baseline(connection: sqlite3.Connection) -> None:
        original_baseline(connection)
        raise RuntimeError("injected reset failure")

    monkeypatch.setattr(db, "_baseline_schema", fail_after_baseline)
    with pytest.raises(RuntimeError, match="injected reset failure"):
        migrate_database()

    with closing(sqlite3.connect(config.sqlite_path())) as connection:
        assert connection.execute("SELECT * FROM job").fetchall() == [("old-job", "reserved")]
        assert connection.execute("SELECT * FROM account_session").fetchall() == [("obsolete-session",)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'schema_metadata'").fetchall() == []


@pytest.mark.parametrize("replacement", ["empty", "legacy"])
def test_replaced_database_at_same_path_is_initialized(monkeypatch, tmp_path: Path, replacement: str) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    JobStore().create_pending_job("previous", "graduation", "source.xlsx")
    config.sqlite_path().unlink()
    if replacement == "legacy":
        _create_legacy_database(config.sqlite_path())

    JobStore().create_pending_job("replacement", "graduation", "source.xlsx")

    assert get_database_metadata()["schema_generation"] == 2
    assert JobStore().get_status("replacement")["status"] == "pending"
    assert JobStore().get_status("previous") is None


def test_sidecar_backup_archive_round_trip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("backup-job", "graduation", "source.xlsx")
    checkpoint = JobCheckpoint(level_label="M3", base_url="http://localhost", next_page=3, processed=1, succeeded=1)
    store.save_checkpoint("backup-job", checkpoint)
    store.append_results("backup-job", [{"page": 2, "portal_row_index": 1, "matched_order": 4, "note": "dry_run"}])
    sample_report = config.reports_dir() / "report.json"
    sample_report.write_text('{"ok":true}', encoding="utf-8")
    sample_config = config.configs_dir() / "graduation.json"
    sample_config.write_text("{}", encoding="utf-8")
    sample_ocr = config.ocr_cache_dir() / "gemini" / "result.json"
    sample_ocr.parent.mkdir(parents=True, exist_ok=True)
    sample_ocr.write_text('{"records":[]}', encoding="utf-8")
    sample_credentials = tmp_path / "credentials" / "secret"
    sample_credentials.parent.mkdir()
    sample_credentials.write_text("fake-secret", encoding="utf-8")
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
        assert "ocr/gemini/result.json" in manifest["files"]
        assert all(not item.startswith(("profiles/", "configs/", "credentials/")) for item in archive.namelist())
        assert set(manifest["files"]) == {"desktop.sqlite3", "reports/report.json", "ocr/gemini/result.json"}

    store.set_status("backup-job", "failed")
    sample_report.write_text('{"ok":false}', encoding="utf-8")
    sample_ocr.write_text("changed", encoding="utf-8")
    sample_config.write_text("keep-local-config", encoding="utf-8")
    stale_ocr = config.ocr_cache_dir() / "stale.json"
    stale_ocr.write_text("stale", encoding="utf-8")

    result = restore_backup_archive(archive_path)
    restored = store.get_status("backup-job")

    assert restored is not None
    assert restored["status"] == "pending"
    assert sample_report.read_text(encoding="utf-8") == '{"ok":true}'
    assert sample_ocr.read_text(encoding="utf-8") == '{"records":[]}'
    assert not stale_ocr.exists()
    assert sample_config.read_text(encoding="utf-8") == "keep-local-config"
    assert sample_profile_cache.read_bytes() == b"browser-cache"
    assert sample_credentials.read_text(encoding="utf-8") == "fake-secret"
    restored_checkpoint = store.load_checkpoint("backup-job")
    assert restored_checkpoint is not None
    assert restored_checkpoint.next_page == 3
    assert restored_checkpoint.processed == 1
    assert restored_checkpoint.results == [{"page": 2, "portal_row_index": 1, "matched_order": 4, "note": "dry_run"}]
    assert Path(result["safety_backup_path"]).exists()


@pytest.mark.parametrize("member", ["configs/old.json", "profiles/session", "credentials/secret", "account/token", "reports/../configs/old.json"])
def test_restore_never_copies_unretained_auxiliary_files(monkeypatch, tmp_path: Path, member: str) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    archive_path = create_backup_archive(tmp_path / "untrusted.zip")
    with zipfile.ZipFile(archive_path, "a") as archive:
        archive.writestr(member, "obsolete-secret")
        # Replace the manifest in a separate archive to avoid duplicate ZIP entries.
        manifest = json.loads(archive.read("manifest.json"))
    manifest["files"].append(member)
    rewritten = tmp_path / "rewritten.zip"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(rewritten, "w") as target:
        for name in source.namelist():
            target.writestr(name, json.dumps(manifest) if name == "manifest.json" else source.read(name))

    restore_backup_archive(rewritten)

    assert not (tmp_path / member).resolve().exists()


def test_restore_rejects_traversal_without_changing_local_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("untouched", "graduation", "source.xlsx")
    archive_path = create_backup_archive(tmp_path / "traversal.zip")
    with zipfile.ZipFile(archive_path, "a") as archive:
        archive.writestr("../escape.txt", "invalid")

    with pytest.raises(DomainError, match="BACKUP_PATH_INVALID"):
        restore_backup_archive(archive_path)

    assert store.get_status("untouched")["status"] == "pending"
    assert not (tmp_path.parent / "escape.txt").exists()


@pytest.mark.parametrize("copy_database", [backup._snapshot_sqlite_database, backup._restore_sqlite_database])
def test_database_copy_closes_source_when_target_cannot_open(monkeypatch, tmp_path: Path, copy_database) -> None:
    source = tmp_path / "source.sqlite3"
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def track_connection(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track_connection)
    with pytest.raises(sqlite3.OperationalError):
        copy_database(source, tmp_path)

    # Retain the real connection object so garbage collection cannot mask leaks.
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
