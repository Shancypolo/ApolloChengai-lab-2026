"""Resolve PageOne's local data files and preserve legacy files safely."""

from __future__ import annotations

import os
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from archive_storage import ArchiveStore


DATA_DIRECTORY_NAME = "user data"
ARCHIVE_FILE_NAME = "userdata.json"
LOG_FILE_NAME = "error.log"
LEGACY_ARCHIVE_FILE_NAME = "pageone.json"
LEGACY_LOG_FILE_NAME = "pageone.log"
ARCHIVE_RECEIPT_FILE_NAME = "archive-migration.json"


class PathMigrationError(ValueError):
    """Describe a safe data migration refusal without exposing file contents."""


def default_data_directory(app_directory: str | Path) -> Path:
    """Return PAGEONE_DATA_DIR or the readable local default folder."""
    configured = os.environ.get("PAGEONE_DATA_DIR")
    if configured is not None:
        return Path(configured).expanduser()
    return Path(app_directory) / DATA_DIRECTORY_NAME


def migrate_data_files(data_directory: str | Path, legacy_directory: str | Path | None = None) -> list[str]:
    """Copy legacy files without deleting originals or replacing destinations."""
    directory = Path(data_directory).expanduser()
    legacy_root = Path(legacy_directory).expanduser() if legacy_directory is not None else directory
    directory.mkdir(parents=True, exist_ok=True)
    messages: list[str] = []
    archive_target = directory / ARCHIVE_FILE_NAME
    old_archive = legacy_root / LEGACY_ARCHIVE_FILE_NAME
    if old_archive.exists():
        if archive_target.exists():
            _accept_receipted_archive(old_archive, archive_target, directory / ARCHIVE_RECEIPT_FILE_NAME)
        else:
            fingerprint = _copy_validated_archive(old_archive, archive_target)
            _write_receipt(directory / ARCHIVE_RECEIPT_FILE_NAME, fingerprint)
            messages.append("Copied legacy archive to userdata.json; kept the original.")

    old_log = legacy_root / LEGACY_LOG_FILE_NAME
    new_log = directory / LOG_FILE_NAME
    if old_log.exists() and not new_log.exists():
        _copy_file_atomically(old_log, new_log)
        messages.append("Copied legacy log to error.log; kept the original.")
    return messages


def _copy_validated_archive(source: Path, target: Path) -> str:
    """Validate copied archive data before installing it at the new path."""
    ArchiveStore(source).read()
    _copy_file_atomically(source, target)
    try:
        ArchiveStore(target).read()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return _fingerprint(source)


def _accept_receipted_archive(source: Path, target: Path, receipt_path: Path) -> None:
    """Allow known preserved legacy bytes while keeping later archive edits."""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PathMigrationError("Both legacy and new archives exist without a valid migration receipt; kept both unchanged.") from error
    expected = {"source_sha256": _fingerprint(source), "target": target.name}
    if receipt != expected:
        raise PathMigrationError("Legacy archive changed or migration receipt does not match; kept both archives unchanged.")


def _fingerprint(path: Path) -> str:
    """Return a content fingerprint for migration receipt matching."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_receipt(path: Path, fingerprint: str) -> None:
    """Install the migration receipt atomically without replacing a file."""
    content = json.dumps({"source_sha256": fingerprint, "target": ARCHIVE_FILE_NAME}, sort_keys=True) + "\n"
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix="pageone-receipt-", delete=False) as temporary:
            temporary_path = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, path)
    except FileExistsError as error:
        raise PathMigrationError("An archive migration receipt already exists; kept all files unchanged.") from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


def _copy_file_atomically(source: Path, target: Path) -> None:
    """Copy a file beside its destination and install it without clobbering."""
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix="pageone-migrate-", delete=False) as temporary:
            temporary_path = temporary.name
        shutil.copyfile(source, temporary_path)
        # Hard-linking is an atomic create-if-absent operation on the same folder.
        os.link(temporary_path, target)
    except FileExistsError as error:
        raise PathMigrationError(f"Migration destination already exists: {target.name}; kept both files unchanged.") from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)
