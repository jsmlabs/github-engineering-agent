"""Headless GUI argument-contract regression tests."""
import unittest
from unittest.mock import patch

from gh_agent import gui


class GuiContractTests(unittest.TestCase):
    def test_known_actions_are_all_configured(self):
        self.assertEqual(set(gui.OPTIONS), set(gui.READ_ONLY))

    def test_supported_read_only_arguments(self):
        examples = {
            "workspace": ["--checkout", "."],
            "files": ["--checkout", ".", "--search", "src", "--limit", "20"],
            "dashboard": ["--checkout", ".", "--proposal", "../proposal.json"],
            "prepare": ["--checkout", ".", "--repo", "example/repo", "--issue", "7",
                        "--model", "test-model", "--allowed-file", "src/app.py",
                        "--allowed-file", "tests/test_app.py", "--output", "../proposal.json"],
            "commands": ["--search", "approval"],
            "recipes": ["--topic", "scope"],
            "guide": [],
        }
        for action, args in examples.items():
            with self.subTest(action=action):
                gui.validate_arguments(action, args)

    def test_unexpected_options_and_values_are_rejected(self):
        invalid = (
            ("workspace", ["--remote", "yes"]),
            ("files", ["--checkout", ".", "--approve"]),
            ("files", ["--checkout", ".", "--search", "--approve-publish"]),
            ("guide", ["--checkout", "."]),
            ("prepare", ["--checkout", ".", "--allow-source-upload", "yes"]),
            ("commands", ["--search"]),
            ("recipes", ["--topic", "x\nunsafe"]),
            ("workspace", ["--json", "true"]),
            ("workspace", [None]),
        )
        for action, args in invalid:
            with self.subTest(action=action, args=args), self.assertRaises(ValueError):
                gui.validate_arguments(action, args)

    def test_result_formatting_handles_unicode_and_stable_keys(self):
        self.assertEqual(gui.format_result("ready"), "ready")
        self.assertEqual(gui.format_result({"z": "Grün", "a": 1}),
                         '{\n  "a": 1,\n  "z": "Grün"\n}')

    def test_selection_tracks_resolved_checkout(self):
        from pathlib import Path
        checkout = str(Path(".").resolve())
        self.assertFalse(gui.selection_is_current([], checkout, checkout))
        self.assertTrue(gui.selection_is_current(["src/app.py"], checkout, checkout))
        self.assertFalse(gui.selection_is_current(["src/app.py"], checkout, "../another-checkout"))

    def test_blocked_command_never_reaches_cli(self):
        with patch("gh_agent.cli.main") as cli:
            with self.assertRaises(ValueError):
                gui.inspect("publish", ["--approve-publish"])
            with self.assertRaises(ValueError):
                gui.inspect("workspace", ["--remote", "yes"])
            cli.assert_not_called()


if __name__ == "__main__":
    unittest.main()
