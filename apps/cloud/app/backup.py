from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .config import settings
from .db import get_database_metadata, migrate_database


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_backup_path() -> Path:
    sqlite_path = Path(settings.sqlite_path)
    return sqlite_path.parent / f"cloud-backup-{_timestamp_slug()}.zip"


def _snapshot_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()


def _restore_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()


def create_backup_archive(output_path: Path | None = None) -> Path:
    source_db = Path(settings.sqlite_path)
    migrate_database(source_db)

    destination = output_path or default_backup_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dmc-cloud-backup-") as temp_dir:
        temp_root = Path(temp_dir)
        db_snapshot = temp_root / "cloud-state.sqlite3"
        _snapshot_sqlite_database(source_db, db_snapshot)
        manifest = {
            "kind": "dmc-cloud-backup",
            "created_at": utc_now(),
            "app_version": settings.version,
            "schema": get_database_metadata(source_db),
            "sqlite_path": str(source_db),
            "files": ["cloud-state.sqlite3"],
        }
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(db_snapshot, arcname="cloud-state.sqlite3")
    return destination


def restore_backup_archive(archive_path: Path) -> dict[str, str]:
    if not archive_path.exists():
        raise RuntimeError("BACKUP_NOT_FOUND")

    sqlite_target = Path(settings.sqlite_path)
    sqlite_target.parent.mkdir(parents=True, exist_ok=True)
    safety_backup = create_backup_archive()

    with tempfile.TemporaryDirectory(prefix="dmc-cloud-restore-") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(temp_root)

        manifest_path = temp_root / "manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("BACKUP_MANIFEST_INVALID")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("kind") != "dmc-cloud-backup":
            raise RuntimeError("BACKUP_KIND_INVALID")

        restored_db = temp_root / "cloud-state.sqlite3"
        if not restored_db.exists():
            raise RuntimeError("BACKUP_DATABASE_MISSING")

        _restore_sqlite_database(restored_db, sqlite_target)

    migrate_database(sqlite_target)
    return {
        "restored_from": str(archive_path),
        "safety_backup_path": str(safety_backup),
        "database_path": str(sqlite_target),
    }
