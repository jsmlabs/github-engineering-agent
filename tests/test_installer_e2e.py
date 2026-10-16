"""Offline integration exercise: real virtualenv + local wheel activation and rollback."""
from __future__ import annotations

import hashlib
import subprocess
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "installer.py"
spec = importlib.util.spec_from_file_location("installer_e2e", MODULE)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def stub_wheel(directory: Path, version: str) -> tuple[Path, str]:
    dist = f"github_engineering_agent-{version}.dist-info"
    wheel = directory / f"github_engineering_agent-{version}-py3-none-any.whl"
    files = {
        "gh_agent/__init__.py": "",
        "gh_agent/__main__.py": "print('Stub CLI ready')\n",
        f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: github-engineering-agent\nVersion: {version}\n",
        f"{dist}/WHEEL": "Wheel-Version: 1.0\nGenerator: offline-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{dist}/RECORD": "",
    }
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return wheel, hashlib.sha256(wheel.read_bytes()).hexdigest()


class InstallerE2ETests(unittest.TestCase):
    def test_fresh_install_update_rollback_and_uninstall_offline(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            base = Path(directory)
            target = base / "application"
            first, first_hash = stub_wheel(base, "0.2.0")
            second, second_hash = stub_wheel(base, "0.2.1")
            self.assertIn("0.2.0", installer.install(target, first, first_hash))
            self.assertIn("0.2.0", installer.verify(target))
            self.assertIn("no reinstall", installer.install(target, first, first_hash))
            python = installer.python_in(target / "releases" / first_hash)
            entry = subprocess.check_output(
                [str(python), "-c", "import gh_agent; print(gh_agent.__file__)"],
                text=True,
            ).strip()
            Path(entry).with_name("__main__.py").unlink()
            with self.assertRaises(subprocess.CalledProcessError):
                installer.verify(target)
            self.assertIn("0.2.0", installer.install(target, first, first_hash, repair=True))
            self.assertIn("0.2.0", installer.verify(target))
            self.assertIn("0.2.1", installer.install(target, second, second_hash))
            self.assertIn("0.2.1", installer.verify(target))
            self.assertIn("0.2.0", installer.rollback(target))
            self.assertIn("0.2.0", installer.verify(target))
            self.assertIn("removed", installer.uninstall(target, "UNINSTALL"))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
