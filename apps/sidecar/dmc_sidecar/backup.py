from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from . import config
from .db import get_database_metadata, migrate_database


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_backup_path() -> Path:
    return config.backups_dir() / f"sidecar-backup-{_timestamp_slug()}.zip"


def _snapshot_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        target_connection = sqlite3.connect(target)
        source_connection.backup(target_connection)
        target_connection.commit()
        target_connection.close()


def _iter_data_files() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    data_dir = config.default_data_dir()
    for root in (config.configs_dir(), config.reports_dir(), config.profiles_dir()):
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            files.append((path, path.relative_to(data_dir).as_posix()))
    return files


def create_backup_archive(output_path: Path | None = None) -> Path:
    source_db = config.sqlite_path()
    migrate_database(source_db)

    destination = output_path or default_backup_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dmc-sidecar-backup-") as temp_dir:
        temp_root = Path(temp_dir)
        db_snapshot = temp_root / "desktop.sqlite3"
        _snapshot_sqlite_database(source_db, db_snapshot)

        manifest = {
                "kind": "dmc-sidecar-backup",
                "created_at": utc_now(),
                "sidecar_version": __version__,
                "schema": get_database_metadata(source_db),
                "data_dir": str(config.default_data_dir()),
                "files": ["desktop.sqlite3", *[relative for _, relative in _iter_data_files()]],
            }

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(db_snapshot, arcname="desktop.sqlite3")
            for source_path, relative_path in _iter_data_files():
                archive.write(source_path, arcname=relative_path)

    return destination


def restore_backup_archive(archive_path: Path) -> dict[str, str]:
    if not archive_path.exists():
        raise RuntimeError("BACKUP_NOT_FOUND")

    current_data_dir = config.default_data_dir()
    current_data_dir.mkdir(parents=True, exist_ok=True)
    safety_backup = create_backup_archive()

    with tempfile.TemporaryDirectory(prefix="dmc-sidecar-restore-") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(temp_root)

        manifest_path = temp_root / "manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("BACKUP_MANIFEST_INVALID")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("kind") != "dmc-sidecar-backup":
            raise RuntimeError("BACKUP_KIND_INVALID")

        restored_db = temp_root / "desktop.sqlite3"
        if not restored_db.exists():
            raise RuntimeError("BACKUP_DATABASE_MISSING")

        for folder in (config.configs_dir(), config.reports_dir(), config.profiles_dir()):
            if folder.exists():
                shutil.rmtree(folder)

        sqlite_target = config.sqlite_path()
        sqlite_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(restored_db, sqlite_target)

        for relative in manifest.get("files", []):
            if relative in {"manifest.json", "desktop.sqlite3"}:
                continue
            source_path = temp_root / relative
            if not source_path.exists() or not source_path.is_file():
                continue
            destination_path = current_data_dir / relative
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    migrate_database(config.sqlite_path())
    return {
        "restored_from": str(archive_path),
        "safety_backup_path": str(safety_backup),
        "database_path": str(config.sqlite_path()),
    }
