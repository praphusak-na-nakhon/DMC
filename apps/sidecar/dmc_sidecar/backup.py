from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from . import config
from .db import get_database_metadata, migrate_database
from .errors import DomainError


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_backup_path() -> Path:
    return config.backups_dir() / f"sidecar-backup-{_timestamp_slug()}.zip"


def _snapshot_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(target)) as target_connection:
        source_connection.backup(target_connection)
        target_connection.commit()


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar_path = Path(f"{path}{suffix}")
        if sidecar_path.exists():
            sidecar_path.unlink()


def _restore_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(target)) as target_connection:
        source_connection.backup(target_connection)
        target_connection.commit()


def _iter_data_files() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    data_dir = config.default_data_dir()
    for root in (config.reports_dir(), config.ocr_cache_dir()):
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            files.append((path, path.relative_to(data_dir).as_posix()))
    return files


def _ensure_relative_member_path(root: Path, member: str) -> Path:
    if not member or Path(member).is_absolute():
        raise DomainError("BACKUP_PATH_INVALID")
    target = (root / member).resolve()
    if not target.is_relative_to(root.resolve()):
        raise DomainError("BACKUP_PATH_INVALID")
    return target


def _validate_archive_members(archive: zipfile.ZipFile, temp_root: Path) -> None:
    for info in archive.infolist():
        _ensure_relative_member_path(temp_root, info.filename)


def create_backup_archive(output_path: Path | None = None) -> Path:
    source_db = config.sqlite_path()
    migrate_database(source_db)

    destination = output_path or default_backup_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dmc-sidecar-backup-") as temp_dir:
        temp_root = Path(temp_dir)
        db_snapshot = temp_root / "desktop.sqlite3"
        _snapshot_sqlite_database(source_db, db_snapshot)

        data_files = _iter_data_files()
        manifest = {
            "kind": "dmc-sidecar-backup",
            "created_at": utc_now(),
            "sidecar_version": __version__,
            "schema": get_database_metadata(source_db),
            "data_dir": str(config.default_data_dir()),
            "files": ["desktop.sqlite3", *[relative for _, relative in data_files]],
        }

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(db_snapshot, arcname="desktop.sqlite3")
            for source_path, relative_path in data_files:
                archive.write(source_path, arcname=relative_path)

    return destination


def restore_backup_archive(archive_path: Path) -> dict[str, str]:
    if not archive_path.exists():
        raise DomainError("BACKUP_NOT_FOUND")

    current_data_dir = config.default_data_dir()
    current_data_dir.mkdir(parents=True, exist_ok=True)
    safety_backup = create_backup_archive()

    with tempfile.TemporaryDirectory(prefix="dmc-sidecar-restore-") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(archive_path, "r") as archive:
            _validate_archive_members(archive, temp_root)
            archive.extractall(temp_root)

        manifest_path = temp_root / "manifest.json"
        if not manifest_path.exists():
            raise DomainError("BACKUP_MANIFEST_INVALID")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("kind") != "dmc-sidecar-backup":
            raise DomainError("BACKUP_KIND_INVALID")

        restored_db = temp_root / "desktop.sqlite3"
        if not restored_db.exists():
            raise DomainError("BACKUP_DATABASE_MISSING")

        manifest_files = manifest.get("files", [])
        if not isinstance(manifest_files, list):
            raise DomainError("BACKUP_MANIFEST_INVALID")

        retained_roots = (config.reports_dir(), config.ocr_cache_dir())
        restore_files: list[tuple[Path, Path]] = []
        for relative in manifest_files:
            if not isinstance(relative, str):
                raise DomainError("BACKUP_MANIFEST_INVALID")
            if relative in {"manifest.json", "desktop.sqlite3"}:
                continue
            source_path = _ensure_relative_member_path(temp_root, relative)
            destination_path = _ensure_relative_member_path(current_data_dir, relative)
            if not any(destination_path.is_relative_to(root.resolve()) for root in retained_roots):
                continue
            if not source_path.exists() or not source_path.is_file():
                continue
            restore_files.append((source_path, destination_path))

        for folder in retained_roots:
            if folder.exists():
                shutil.rmtree(folder)

        sqlite_target = config.sqlite_path()
        _restore_sqlite_database(restored_db, sqlite_target)

        for source_path, destination_path in restore_files:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    migrate_database(config.sqlite_path())
    return {
        "restored_from": str(archive_path),
        "safety_backup_path": str(safety_backup),
        "database_path": str(config.sqlite_path()),
    }
