"""Local-only setup check never exposes credentials or performs IO."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "setup_check.py"
spec = importlib.util.spec_from_file_location("setup_check", MODULE)
setup_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_check)


class SetupCheckTests(unittest.TestCase):
    def test_credentials_are_only_boolean_presence(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "secret-example-123",
                                       "OPENAI_API_KEY": "another-secret-987"}):
            result = setup_check.snapshot()
        self.assertTrue(result["github_token_present"])
        self.assertTrue(result["openai_key_present"])
        self.assertNotIn("secret-example-123", repr(result))
        self.assertNotIn("another-secret-987", repr(result))
        self.assertFalse(result["network_checked"])
        self.assertFalse(result["credentials_verified"])
        self.assertFalse(result["permissions_modified"])


if __name__ == "__main__":
    unittest.main()
