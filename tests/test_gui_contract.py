"""Headless GUI argument-contract regression tests."""
import unittest
import subprocess
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


    def test_subprocess_only_runs_allowlisted_local_actions(self):
        with patch("gh_agent.gui.subprocess.run") as run:
            with self.assertRaises(ValueError):
                gui.inspect_process("publish", ["--approve-publish"])
            run.assert_not_called()

    def test_subprocess_uses_argument_vector_and_json(self):
        completed = subprocess.CompletedProcess([], 0, '{"files":[]}', "")
        with patch("gh_agent.gui.subprocess.run", return_value=completed) as run:
            result = gui.inspect_process("files", ["--checkout", ".", "--search", "src", "--limit", "50"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], {"files": []})
        args, kwargs = run.call_args
        self.assertEqual(args[0][-1], "--json")
        self.assertEqual(args[0][2:4], ["gh_agent", "files"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["timeout"], 60)
        self.assertNotIn("shell", kwargs)

    def test_subprocess_timeout_and_failed_status(self):
        with patch("gh_agent.gui.subprocess.run", side_effect=subprocess.TimeoutExpired(["python"], 60)):
            self.assertIn("timed out", gui.inspect_process("workspace")["error"])
        failed = subprocess.CompletedProcess([], 2, "", "Workspace unavailable")
        with patch("gh_agent.gui.subprocess.run", return_value=failed):
            self.assertEqual(gui.inspect_process("workspace"), {"ok": False, "error": "Workspace unavailable"})

    def test_worker_exception_is_recoverable_without_leaking_details(self):
        with patch("gh_agent.gui.inspect_process", side_effect=RuntimeError("sensitive details")):
            result = gui.safe_inspect_process("workspace", ())
        self.assertFalse(result["ok"])
        self.assertIn("retry", result["error"])
        self.assertNotIn("sensitive", result["error"])

    def test_worker_preserves_successful_results(self):
        expected = {"ok": True, "data": {"ready": True}}
        with patch("gh_agent.gui.inspect_process", return_value=expected) as check:
            self.assertEqual(gui.safe_inspect_process("workspace", ()), expected)
        check.assert_called_once_with("workspace", ())

    def test_blocked_command_never_reaches_cli(self):
        with patch("gh_agent.cli.main") as cli:
            with self.assertRaises(ValueError):
                gui.inspect("publish", ["--approve-publish"])
            with self.assertRaises(ValueError):
                gui.inspect("workspace", ["--remote", "yes"])
            cli.assert_not_called()


if __name__ == "__main__":
    unittest.main()
