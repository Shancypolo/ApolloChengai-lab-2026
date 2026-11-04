"""Offline checks for local data locations and safe legacy copying."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from archive_storage import ArchiveStore
from run import missing_modules
from data_paths import (
    ARCHIVE_FILE_NAME,
    DATA_DIRECTORY_NAME,
    LOG_FILE_NAME,
    PathMigrationError,
    default_data_directory,
    migrate_data_files,
)


class DataPathTests(unittest.TestCase):
    """Check filename defaults and migrations without network services."""

    def test_default_folder_name(self) -> None:
        """Use the named folder beside the app when no override is set."""
        with patch.dict("os.environ", {}, clear=True), tempfile.TemporaryDirectory() as folder:
            self.assertEqual(default_data_directory(folder), Path(folder) / DATA_DIRECTORY_NAME)

    def test_copies_and_validates_legacy_files(self) -> None:
        """Copy old archive and log while preserving their source files."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / "instance"
            target = root / DATA_DIRECTORY_NAME
            legacy.mkdir()
            old_archive = legacy / "pageone.json"
            ArchiveStore(old_archive).update(lambda archive: None)
            old_log = legacy / "pageone.log"
            old_log.write_text("previous diagnostic\n", encoding="utf-8")

            messages = migrate_data_files(target, legacy)

            self.assertEqual(len(messages), 2)
            self.assertEqual(ArchiveStore(target / ARCHIVE_FILE_NAME).read()["schema_version"], 2)
            self.assertEqual((target / LOG_FILE_NAME).read_text(encoding="utf-8"), "previous diagnostic\n")
            self.assertTrue(old_archive.exists())
            self.assertTrue(old_log.exists())

    def test_receipt_allows_restart_after_new_archive_changes(self) -> None:
        """Recognize the copied legacy bytes after the new archive is edited."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / "instance"
            target = root / DATA_DIRECTORY_NAME
            legacy.mkdir()
            ArchiveStore(legacy / "pageone.json").update(lambda archive: None)

            migrate_data_files(target, legacy)
            ArchiveStore(target / ARCHIVE_FILE_NAME).update(
                lambda archive: archive.update(summary_preferences="edited preference")
            )
            messages = migrate_data_files(target, legacy)

            self.assertEqual(messages, [])
            self.assertEqual(
                ArchiveStore(target / ARCHIVE_FILE_NAME).read()["summary_preferences"],
                "edited preference",
            )

    def test_refuses_archive_collision_without_overwriting(self) -> None:
        """Keep both archives unchanged when the destination already exists."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_archive = root / "pageone.json"
            target_archive = root / ARCHIVE_FILE_NAME
            ArchiveStore(old_archive).update(lambda archive: None)
            ArchiveStore(target_archive).update(lambda archive: archive.update(summary_preferences="new data"))
            old_bytes = old_archive.read_bytes()
            target_bytes = target_archive.read_bytes()

            with self.assertRaisesRegex(PathMigrationError, "receipt"):
                migrate_data_files(root)

            self.assertEqual(old_archive.read_bytes(), old_bytes)
            self.assertEqual(target_archive.read_bytes(), target_bytes)

    def test_changed_legacy_archive_is_not_silently_imported_again(self) -> None:
        """Keep both archives when the preserved source changes after migration."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_archive = root / "pageone.json"
            ArchiveStore(old_archive).update(lambda archive: None)
            migrate_data_files(root)
            ArchiveStore(old_archive).update(lambda archive: archive.update(summary_preferences="changed old data"))
            destination = root / ARCHIVE_FILE_NAME
            saved_bytes = destination.read_bytes()
            with self.assertRaises(PathMigrationError):
                migrate_data_files(root)
            self.assertEqual(destination.read_bytes(), saved_bytes)
            self.assertTrue(old_archive.exists())

    def test_launcher_accepts_either_extractor(self) -> None:
        """Allow startup with yt-dlp or pytubefix while rejecting no extractor."""
        for extractor in ("yt_dlp", "pytubefix", None):
            with self.subTest(extractor=extractor):
                available = {"flask", "openai", extractor}
                with patch("run.importlib.util.find_spec", side_effect=lambda module: object() if module in available else None):
                    missing = missing_modules()
                self.assertEqual(missing, [] if extractor else ["yt_dlp or pytubefix"])

    def test_explicit_directory_does_not_import_elsewhere(self) -> None:
        """Migrate only names found in the explicitly selected folder."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            default_legacy = root / "instance"
            explicit = root / "custom"
            default_legacy.mkdir()
            ArchiveStore(default_legacy / "pageone.json").update(lambda archive: None)

            migrate_data_files(explicit)

            self.assertFalse((explicit / ARCHIVE_FILE_NAME).exists())


if __name__ == "__main__":
    unittest.main()
