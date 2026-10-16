"""Offline regression checks for installer GUI input validation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from installer_gui import validate_release_input, maintenance_message


class InstallerGuiValidationTests(unittest.TestCase):
    def test_action_specific_local_status(self):
        self.assertEqual(maintenance_message("verify", True), "Verify completed locally")
        self.assertEqual(maintenance_message("rollback", False), "Rollback failed · review the details below")

    def test_missing_wheel(self):
        self.assertIn("wheel", validate_release_input(" ", "a" * 64))

    def test_rejects_malformed_digests(self):
        for digest in ("", "z" * 64, "a" * 63, "a" * 65, "a" * 63 + "\nxyz"):
            with self.subTest(digest=digest):
                self.assertIsNotNone(validate_release_input("release.whl", digest))

    def test_accepts_hexadecimal_digest(self):
        self.assertIsNone(validate_release_input("release.whl", "aB" * 32))
        self.assertIsNone(validate_release_input("release.whl", " " + "a" * 64 + " "))


if __name__ == "__main__":
    unittest.main()
