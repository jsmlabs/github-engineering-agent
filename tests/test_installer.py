"""Focused safety tests for the offline installation manager."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import hashlib

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "installer.py"
spec = importlib.util.spec_from_file_location("installer", MODULE)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_target_rejects_home_and_root(self):
        for path in (Path.home(), Path.home().anchor):
            with self.subTest(path=path), self.assertRaises(ValueError):
                installer.validate_target(Path(path))

    def test_target_allows_user_scoped_directory(self):
        path = Path.home() / "test-user-install" / "app"
        self.assertEqual(installer.validate_target(path), path.resolve())

    def test_wheel_hash_and_metadata_checked(self):
        with tempfile.TemporaryDirectory() as d:
            wheel = Path(d) / "github_engineering_agent-0.2.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("github_engineering_agent-0.2.0.dist-info/METADATA",
                                 "Name: github-engineering-agent\nVersion: 0.2.0\n")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            self.assertEqual(installer.validate_wheel(wheel, digest)[1], digest)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                installer.validate_wheel(wheel, "0" * 64)

    def test_wheel_rejects_archive_traversal_and_wrong_package(self):
        with tempfile.TemporaryDirectory() as d:
            wheel = Path(d) / "github_engineering_agent-0.2.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("../outside.txt", "unexpected")
                archive.writestr("github_engineering_agent-0.2.0.dist-info/METADATA",
                                 "Name: github-engineering-agent\nVersion: 0.2.0\n")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "unsafe archive"):
                installer.validate_wheel(wheel, digest)
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("github_engineering_agent-0.2.0.dist-info/METADATA",
                                 "Name: wrong-package\nVersion: 0.2.0\n")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "distribution metadata"):
                installer.validate_wheel(wheel, digest)

    def test_wheel_archive_resource_limits(self):
        with tempfile.TemporaryDirectory() as d:
            wheel = Path(d) / "github_engineering_agent-0.2.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("github_engineering_agent-0.2.0.dist-info/METADATA",
                                 "Name: github-engineering-agent\nVersion: 0.2.0\n")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            with patch.object(installer, "MAX_EXPANDED_BYTES", 5):
                with self.assertRaisesRegex(ValueError, "extraction budget"):
                    installer.validate_wheel(wheel, digest)
            with patch.object(installer, "MAX_WHEEL_BYTES", 5):
                with self.assertRaisesRegex(ValueError, "maximum allowed size"):
                    installer.validate_wheel(wheel, digest)

    def test_preview_is_read_only_and_discloses_no_credentials(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d) / "new-install"
            wheel = Path(d) / "github_engineering_agent-0.2.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("github_engineering_agent-0.2.0.dist-info/METADATA",
                                 "Name: github-engineering-agent\nVersion: 0.2.0\n")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            result = installer.preview(target, wheel, digest)
            self.assertIn('"candidate_version": "0.2.0"', result)
            self.assertIn('"executed": false', result)
            self.assertFalse(target.exists())

    def test_uninstall_refuses_unknown_files_and_requires_confirmation(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d) / "managed"
            target.mkdir()
            (target / ".gh-engineer-managed").write_text("github-engineering-agent managed installation v2\n")
            (target / "keep.txt").write_text("personal")
            with self.assertRaisesRegex(ValueError, "confirmation"):
                installer.uninstall(target, "")
            with self.assertRaisesRegex(ValueError, "Unexpected user files"):
                installer.uninstall(target, "UNINSTALL")
            self.assertTrue((target / "keep.txt").exists())

    def test_operation_lock_prevents_concurrent_mutation(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d)
            with installer.operation_lock(target):
                with self.assertRaisesRegex(ValueError, "Another installation"):
                    with installer.operation_lock(target):
                        pass
            self.assertFalse((target / ".installer.lock").exists())

    def test_symlink_installation_target_refused(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d) / "link"
            try:
                target.symlink_to(Path(d), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "symlink"):
                installer.validate_target(target)

    def test_managed_marker_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            root = Path(d)
            target = root / "managed"
            target.mkdir()
            source = root / "marker"
            source.write_text(installer.MARKER)
            try:
                (target / ".gh-engineer-managed").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "Symlinked"):
                installer.require_managed(target)

    def test_release_slot_rejects_unknown_entries(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d)
            digest = "b" * 64
            slot = target / "releases" / digest
            slot.mkdir(parents=True)
            (slot / ".slot-managed").write_text(installer.SLOT_MARKER)
            (slot / "unexpected.txt").write_text("keep")
            with self.assertRaisesRegex(ValueError, "Unexpected release files"):
                installer._install_locked(target, Path("unused.whl"), digest, "0.2.0",
                    {"schema": 1, "active": None, "previous": None, "versions": {}})
            self.assertTrue((slot / "unexpected.txt").exists())

    def test_symlinked_state_refused(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            root = Path(d)
            target = root / "managed"
            target.mkdir()
            (target / ".gh-engineer-managed").write_text(installer.MARKER)
            external = root / "external.json"
            external.write_text("{}")
            try:
                (target / "state.json").symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "Symlinked installation state"):
                installer.read_state(target)

    def test_lock_state_read_after_acquisition(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d) / "managed"
            target.mkdir()
            (target / ".gh-engineer-managed").write_text(installer.MARKER)
            with installer.operation_lock(target):
                with self.assertRaisesRegex(ValueError, "Another installation"):
                    with installer.operation_lock(target):
                        pass
            self.assertEqual(installer.read_state(target)["versions"], {})

    def test_initial_state_and_no_rollback(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d) / "installed"
            target.mkdir()
            (target / ".gh-engineer-managed").write_text(installer.MARKER)
            state = installer.read_state(target)
            self.assertIsNone(state["active"])
            with self.assertRaisesRegex(ValueError, "previous release"):
                installer.rollback(target)

    def test_atomic_state_update_and_validated_restore(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            target = Path(d) / "installed"
            target.mkdir()
            (target / ".gh-engineer-managed").write_text(installer.MARKER)
            digest = "a" * 64
            state = {"schema": 1, "active": digest, "previous": None,
                     "versions": {digest: "0.2.0"}}
            installer.write_state(target, state)
            self.assertEqual(installer.read_state(target), state)
            (target / "state.json.tmp").write_text("interrupted")
            with self.assertRaisesRegex(ValueError, "Interrupted"):
                installer.write_state(target, state)

    def test_verify_refuses_unmanaged_directory(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as d:
            with self.assertRaisesRegex(ValueError, "No managed"):
                installer.verify(Path(d))


if __name__ == "__main__":
    unittest.main()
