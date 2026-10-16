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
