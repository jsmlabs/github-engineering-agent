from __future__ import annotations

import argparse
from pathlib import Path
import json
from contextlib import redirect_stdout
from io import StringIO
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from gh_agent import cli
from gh_agent.core import (AgentError, assert_checkout, check_path, guarded_file, private_json_write, read_selected, sha, tracked_sources, validate_edits, validate_selection, authorized_files, validate_source_sensitivity, validate_content_syntax, remote_branch_sha, run_git)
from gh_agent.services import GitHub, Model
from gh_agent.verification import check_gate, run_isolated, verification_path


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        git(self.checkout, "init", "-b", "main")
        git(self.checkout, "config", "core.autocrlf", "false")
        git(self.checkout, "config", "user.email", "tester@example.invalid")
        git(self.checkout, "config", "user.name", "Tester")
        (self.checkout / "app.py").write_text("x = 1\n", encoding="utf-8", newline="")
        git(self.checkout, "add", "app.py")
        git(self.checkout, "commit", "-m", "initial")
        self.base = git(self.checkout, "rev-parse", "HEAD")
        git(self.checkout, "remote", "add", "origin", "https://github.com/example/safe-repo.git")
        git(self.checkout, "update-ref", "refs/remotes/origin/main", self.base)
        self.planfile = self.root / "plan.json"

    def proposal(self):
        original = (self.checkout / "app.py").read_text()
        return {
            "schema": 2, "authorized_files": ["app.py"], "repo": "example/safe-repo", "issue": 7, "base": "main", "base_sha": self.base,
            "issue_updated_at": "2026-10-15T00:00:00Z", "model": "stub", "summary": "Change value",
            "edits": [{"path": "app.py", "base_sha256": sha(original.encode()), "content": "x = 2\n"}],
        }

    def test_home_and_guide_are_read_only(self):
        for argv, expected in (([], "GET STARTED"), (["guide"], "SAFE FIVE-STEP")):
            with self.subTest(argv=argv), redirect_stdout(StringIO()) as stdout:
                with (patch.object(cli, "GitHub") as gh,
                      patch.object(cli, "Model") as model,
                      patch.object(cli, "run_git") as local_git):
                    self.assertEqual(cli.main(argv), 0)
                    gh.assert_not_called()
                    model.assert_not_called()
                    local_git.assert_not_called()
                self.assertIn(expected, stdout.getvalue())
                self.assertIn("gh-engineer", stdout.getvalue())

    def test_menu_refuses_noninteractive_input_without_side_effects(self):
        from contextlib import redirect_stderr
        with (redirect_stdout(StringIO()), redirect_stderr(StringIO()) as stderr,
              patch.object(cli, "plan") as plan, patch.object(cli, "publish") as publish,
              patch("builtins.input") as prompt):
            self.assertEqual(cli.main(["menu", "--checkout", str(self.checkout)]), 2)
            prompt.assert_not_called()
            plan.assert_not_called()
            publish.assert_not_called()
        self.assertIn("interactive terminal", stderr.getvalue())

    def test_menu_navigation_is_bounded_and_read_only(self):
        class FakeTTY(StringIO):
            def isatty(self):
                return True

        private_json_write(self.planfile, self.proposal())
        before = self.planfile.read_bytes()
        terminal_in = FakeTTY("9\n1\n2\n3\n" + str(self.planfile) + "\n4\n\n5\n0\n")
        terminal_out = FakeTTY()
        with (patch.object(cli.sys, "stdin", terminal_in),
              patch.object(cli.sys, "stdout", terminal_out),
              patch.object(cli, "GitHub") as github,
              patch.object(cli, "Model") as model,
              patch.object(cli, "apply") as apply,
              patch.object(cli, "publish") as publish,
              patch.object(cli, "run_auto") as run_auto):
            self.assertEqual(cli.main(["menu", "--checkout", str(self.checkout),
                                       "--repo", "example/safe-repo", "--no-color"]), 0)
            github.assert_not_called()
            model.assert_not_called()
            apply.assert_not_called()
            publish.assert_not_called()
            run_auto.assert_not_called()
        output = terminal_out.getvalue()
        for expected in ("Unknown option", "SAFE FIVE-STEP WORKFLOW",
                         "Local preflight passed", "Stage: PROPOSED",
                         "NO_APPLY_RECEIPT", "GET STARTED", "Menu closed"):
            self.assertIn(expected, output)
        self.assertNotIn("\x1b[", output)
        self.assertEqual(self.planfile.read_bytes(), before)
        self.assertFalse(Path(str(self.planfile) + ".applied.json").exists())
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_menu_color_is_optional_and_respects_no_color(self):
        class FakeTTY(StringIO):
            def isatty(self):
                return True

        with patch.object(cli.sys, "stdout", FakeTTY()):
            with patch.dict(os.environ, {"TERM": "xterm", "NO_COLOR": ""}):
                self.assertEqual(cli.menu_style("hello", "1;36"), "hello")
            with patch.dict(os.environ, {"TERM": "xterm"}):
                with patch.dict(os.environ, {"NO_COLOR": None}) if False else patch.dict(os.environ, {}, clear=False):
                    # A caller's NO_COLOR is handled deterministically either way.
                    self.assertEqual(cli.menu_style("hello", "1;36", no_color=True), "hello")

    def test_menu_handles_eof_and_has_iteration_limit(self):
        class FakeTTY(StringIO):
            def isatty(self):
                return True

        with (patch.object(cli.sys, "stdin", FakeTTY("")),
              patch.object(cli.sys, "stdout", FakeTTY()) as out):
            self.assertEqual(cli.main(["menu"]), 0)
        self.assertIn("Menu closed", out.getvalue())
        with (patch.object(cli.sys, "stdin", FakeTTY("9\n" * 42)),
              patch.object(cli.sys, "stdout", FakeTTY()) as out):
            self.assertEqual(cli.main(["menu"]), 0)
        self.assertIn("session limit reached", out.getvalue())

    def test_cli_checkout_defaults_and_explicit_approvals(self):
        for argv in (
            ["review", "--proposal", str(self.planfile)],
            ["status", "--proposal", str(self.planfile)],
            ["next", "--proposal", str(self.planfile)],
            ["doctor"],
            ["apply", "--proposal", str(self.planfile), "--approve",
             "--expected-sha256", "a" * 64],
            ["publish", "--proposal", str(self.planfile), "--approve-publish"],
        ):
            with self.subTest(argv=argv):
                args = cli.make_parser().parse_args(argv)
                self.assertEqual(args.checkout, ".")
        with self.assertRaises(SystemExit):
            cli.make_parser().parse_args(["apply", "--proposal", str(self.planfile),
                                           "--approve"])

    def test_doctor_offline_checks_and_dirty_worktree(self):
        args = ["doctor", "--checkout", str(self.checkout),
                "--repo", "example/safe-repo"]
        with redirect_stdout(StringIO()) as out, patch.object(cli, "GitHub") as gh:
            self.assertEqual(cli.main(args), 0)
            gh.assert_not_called()
        self.assertIn("Local preflight passed", out.getvalue())
        self.assertIn("origins match", out.getvalue())
        self.assertNotIn("example/safe-repo.git", out.getvalue())
        (self.checkout / "untracked.txt").write_text("dirty", encoding="utf-8")
        with self.assertRaisesRegex(AgentError, "not clean"):
            cli.doctor(argparse.Namespace(checkout=str(self.checkout),
                                          repo="example/safe-repo"))

    def test_next_step_tracks_local_evidence_without_mutations(self):
        with self.assertRaisesRegex(AgentError, "Proposal not found"):
            cli.next_step(argparse.Namespace(checkout=str(self.checkout),
                                             proposal=str(self.planfile)))
        private_json_write(self.planfile, self.proposal())
        args = argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile))
        with redirect_stdout(StringIO()) as out:
            cli.next_step(args)
        self.assertIn("Stage: PROPOSED", out.getvalue())
        self.assertIn("review", out.getvalue())
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")
        cli.apply(argparse.Namespace(checkout=str(self.checkout),
                                     proposal=str(self.planfile), approve=True,
                                     expected_sha256=sha(self.planfile.read_bytes())))
        with redirect_stdout(StringIO()) as out:
            cli.next_step(args)
        self.assertIn("Verification: NOT RUN", out.getvalue())
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        report = {"schema": 1, "proposal_sha256": receipt["proposal_sha256"],
                  "commit": receipt["commit"], "branch": receipt["branch"],
                  "exit_code": 0, "outcome": "PASS"}
        private_json_write(verification_path(self.planfile), report)
        with redirect_stdout(StringIO()) as out:
            cli.next_step(args)
        self.assertIn("Verification: PASS", out.getvalue())
        self.assertIn("status --proposal PATH --remote", out.getvalue())
        report["outcome"] = "FAIL"
        verification_path(self.planfile).write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(AgentError, "test failure"):
            cli.next_step(args)

    def test_publish_gate_rejects_missing_verification(self):
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                                     approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        with self.assertRaisesRegex(AgentError, "Missing commit-bound"):
            check_gate(self.planfile, receipt, override=False, reason=None)
        with self.assertRaisesRegex(AgentError, "requires --unverified-reason"):
            check_gate(self.planfile, receipt, override=True, reason="short")
        self.assertIn("EXCEPTION:", check_gate(self.planfile, receipt, override=True,
                                              reason="Tests cannot run in this restricted environment"))

    def test_verify_commit_records_exact_commit_and_allows_gate(self):
        from gh_agent.verification import verify_commit
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                                     approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        image = "trusted/image@sha256:" + "a" * 64
        with patch("gh_agent.verification.run_isolated", return_value={
            "exit_code": 0, "stdout_excerpt": "ok", "stderr_excerpt": ""}):
            report = verify_commit(self.checkout, self.planfile, self.proposal(), receipt,
                                   image, ["python", "-m", "unittest"], 30)
        self.assertEqual(report["commit"], receipt["commit"])
        self.assertEqual(report["outcome"], "PASS")
        self.assertEqual(check_gate(self.planfile, receipt, override=False, reason=None), "PASS")
        with self.assertRaisesRegex(AgentError, "already exists"):
            verify_commit(self.checkout, self.planfile, self.proposal(), receipt,
                          image, ["python", "-m", "unittest"], 30)

    def test_gate_commit_binding_and_failure_are_fail_closed(self):
        receipt = {"proposal_sha256": "a" * 64, "commit": "b" * 40, "branch": "agent/example"}
        report = {"schema": 1, **receipt, "exit_code": 0, "outcome": "PASS"}
        private_json_write(verification_path(self.planfile), report)
        self.assertEqual(check_gate(self.planfile, receipt, override=False, reason=None), "PASS")
        report["commit"] = "c" * 40
        verification_path(self.planfile).write_text(json.dumps(report))
        with self.assertRaisesRegex(AgentError, "Stale"):
            check_gate(self.planfile, receipt, override=True, reason="Cannot execute tests here")
        report["commit"] = receipt["commit"]
        report["outcome"] = "FAIL"
        report["exit_code"] = 1
        verification_path(self.planfile).write_text(json.dumps(report))
        with self.assertRaisesRegex(AgentError, "test failure"):
            check_gate(self.planfile, receipt, override=True, reason="Cannot execute tests here")

    def test_gate_rejects_boolean_and_malformed_exit_codes(self):
        receipt = {"proposal_sha256": "a" * 64, "commit": "b" * 40, "branch": "agent/example"}
        path = verification_path(self.planfile)
        report = {"schema": 1, **receipt, "outcome": "PASS", "exit_code": 0}
        for malformed in (False, True, "0", None):
            with self.subTest(exit_code=malformed):
                report["exit_code"] = malformed
                path.write_text(json.dumps(report), encoding="utf-8")
                with self.assertRaisesRegex(AgentError, "invalid verification record"):
                    check_gate(self.planfile, receipt, override=True, reason="Tests not available")
        report["exit_code"] = 0
        report["schema"] = True
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(AgentError, "invalid verification record"):
            check_gate(self.planfile, receipt, override=False, reason=None)
        report["schema"] = 1
        path.write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual(check_gate(self.planfile, receipt, override=False, reason=None), "PASS")

    @unittest.skipUnless(os.name == "posix", "Docker verification is POSIX-only")
    def test_isolated_test_rejects_unsafe_configuration(self):
        image = "trusted/image@sha256:" + "a" * 64
        with self.assertRaisesRegex(AgentError, "sha256"):
            run_isolated(self.checkout, "python:latest", ["python", "-V"], 10)
        with self.assertRaisesRegex(AgentError, "JSON string array"):
            run_isolated(self.checkout, image, ["python", ""], 10)
        with self.assertRaisesRegex(AgentError, "timeout"):
            run_isolated(self.checkout, image, ["python", "-V"], 999)
        with patch("gh_agent.verification.subprocess.run", side_effect=FileNotFoundError()):
            with self.assertRaisesRegex(AgentError, "Docker unavailable"):
                run_isolated(self.checkout, image, ["python", "-V"], 10)

    @unittest.skipUnless(os.name == "posix", "Docker verification is POSIX-only")
    def test_isolated_test_rejects_control_characters_in_mount_path(self):
        image = "example/test@sha256:" + "a" * 64
        for character in ("\n", "\r", ","):
            with self.subTest(character=repr(character)), patch("gh_agent.verification.subprocess.run") as run:
                with self.assertRaisesRegex(AgentError, "POSIX path without mount delimiters"):
                    run_isolated(Path(str(self.checkout) + character + "unsafe"), image, ["python", "-V"], 10)
                run.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Docker verification is POSIX-only")
    def test_isolated_test_enforces_container_flags(self):
        image = "trusted/image@sha256:" + "a" * 64
        captured = {}
        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, b"ok", b"")
        with patch("gh_agent.verification.subprocess.run", side_effect=fake_run):
            result = run_isolated(self.checkout, image, ["python", "-V"], 15)
        self.assertEqual(result["exit_code"], 0)
        for option in ("--network=none", "--read-only", "--cap-drop=ALL",
                       "--pids-limit=64", "--memory=512m", "--pull=never"):
            self.assertIn(option, captured["argv"])
        self.assertEqual(captured["argv"][-3:], [image, "python", "-V"])

    @unittest.skipUnless(os.name == "posix", "Docker verification is POSIX-only")
    def test_isolated_test_timeout_fails_closed(self):
        image = "trusted/image@sha256:" + "a" * 64
        with patch("gh_agent.verification.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(["docker"], 2)):
            with self.assertRaisesRegex(AgentError, "timed out"):
                run_isolated(self.checkout, image, ["python"], 2)

    def test_status_read_only_incomplete_receipt(self):
        output = StringIO()
        with redirect_stdout(output):
            cli.status(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                                         remote=False))
        self.assertIn("NO_APPLY_RECEIPT", output.getvalue())
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")

    def test_repository_identifier_rejects_non_string_values(self):
        from gh_agent.core import require_repo
        for value in (None, 123, [], {}, True):
            with self.subTest(value=value), self.assertRaisesRegex(AgentError, "Expected repository identifier"):
                require_repo(value)
        self.assertEqual(require_repo("example/safe-repo"), "example/safe-repo")

    def test_status_remote_rejects_missing_receipt_identity(self):
        receipt_path = Path(str(self.planfile) + ".applied.json")
        receipt_path.write_text(json.dumps({
            "schema": 2, "commit": self.base, "branch": "main",
        }), encoding="utf-8")
        with redirect_stdout(StringIO()):
            with self.assertRaisesRegex(AgentError, "Remote status requires valid"):
                cli.status(argparse.Namespace(checkout=str(self.checkout),
                                              proposal=str(self.planfile), remote=True))
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")

    def test_path_escape_and_protected(self):
        for p in ["../foo.py", ".env", ".github/secrets.yml", ".github/workflows/.hidden.yml", "node_modules/a.js", "src/../../a.py", "/tmp/a.py", "src/.hidden/a.py", "credentials/a.py", "app.exe"]:
            with self.subTest(p=p), self.assertRaises(AgentError):
                check_path(p)
        self.assertEqual(check_path("src/app.py"), "src/app.py")
        for path in (".github/workflows/ci.yml", "Dockerfile", "Makefile", ".gitignore", "package-lock.json"):
            self.assertEqual(check_path(path), path)
        (self.checkout / "src").mkdir()
        (self.checkout / "src" / "bad.py").symlink_to(self.checkout / "app.py")
        with self.assertRaises(AgentError):
            guarded_file(self.checkout, "src/bad.py", allow_new=False)

    def test_strict_json_rejects_overflow_and_unpaired_surrogates(self):
        from gh_agent.core import strict_json_loads
        valid = '{"value": 1e2, "key": "\\ud83d\\ude00"}'
        self.assertEqual(strict_json_loads(valid), {"value": 100.0, "key": "\U0001f600"})
        for raw in (
            '{"value": 1e999}',
            '{"value": -1e999}',
            '{"value": 1e-9999, "bad": "\\ud800"}',
            '{"\\udc00": true}',
            '{"nested": ["\\ud800"]}',
        ):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "Non-finite|Unicode"):
                strict_json_loads(raw)
            with self.subTest(source=raw), self.assertRaisesRegex(AgentError, "Invalid Python/JSON"):
                validate_content_syntax("config.json", raw)

    def test_local_json_file_size_is_bounded(self):
        from gh_agent.core import MAX_STATE_BYTES, load_json
        self.planfile.write_bytes(b" " * (MAX_STATE_BYTES + 1))
        with self.assertRaisesRegex(AgentError, "exceeds size budget"):
            load_json(self.planfile)
        self.planfile.write_text('{"schema": 2}', encoding="utf-8")
        self.assertEqual(load_json(self.planfile), {"schema": 2})

    def test_json_source_rejects_ambiguous_or_nonstandard_values(self):
        valid = '{"nested": {"x": 1}, "items": [true, null, 2.5]}'
        validate_content_syntax("config.json", valid)
        for content in (
            '{"key": 1, "key": 2}',
            '{"outer": {"x": 1, "x": 2}}',
            '{"value": NaN}',
            '{"value": Infinity}',
            '{"value": -Infinity}',
        ):
            with self.subTest(content=content), self.assertRaisesRegex(
                AgentError, "Invalid Python/JSON syntax"
            ):
                validate_content_syntax("config.json", content)
        validate_content_syntax("module.py", "value = 1")

    def test_git_repo_identity_and_dirty(self):
        self.assertEqual(assert_checkout(self.checkout, "example/safe-repo", "main", require_base=True), self.base)
        with self.assertRaises(AgentError):
            assert_checkout(self.checkout, "evil/other", "main", require_base=True)
        (self.checkout / "stray.txt").write_text("dirty")
        with self.assertRaises(AgentError):
            assert_checkout(self.checkout, "example/safe-repo", "main", require_base=True)

    def test_validation_rejects_mismatches(self):
        originals = read_selected(self.checkout, ["app.py"])
        bad = [{"path": "app.py", "base_sha256": "0" * 64, "content": "x=2\n"}]
        with self.assertRaises(AgentError):
            validate_edits(self.checkout, bad, originals, {"app.py"})
        with self.assertRaises(AgentError):
            validate_selection(self.checkout, ["app.py"] * 2, {"app.py"})
        with self.assertRaises(AgentError):
            validate_edits(self.checkout, [{"path": "app.py", "base_sha256": sha(b"x = 1\n"), "content": "x = 1\n"}], originals, {"app.py"})

    def test_apply_requires_approval(self):
        private_json_write(self.planfile, self.proposal())
        with self.assertRaises(AgentError):
            cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=False, expected_sha256=sha(self.planfile.read_bytes())))
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_scoped_new_file_creates_directory_and_exact_commit(self):
        path = "src/new_module/feature.py"
        record = self.proposal()
        record["authorized_files"] = [path]
        record["edits"] = [{"path": path, "base_sha256": sha(b""), "content": "VALUE = 42\n"}]
        private_json_write(self.planfile, record)
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                                     approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        self.assertEqual((self.checkout / path).read_text(), "VALUE = 42\n")
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")
        from gh_agent.core import committed_blob
        self.assertEqual(committed_blob(self.checkout, git(self.checkout, "rev-parse", "HEAD"), path), b"VALUE = 42\n")

    def test_new_paths_reject_untracked_file_and_symlink(self):
        untracked = self.checkout / "new.py"
        untracked.write_text("preserve\n")
        with self.assertRaisesRegex(AgentError, "untracked"):
            authorized_files(self.checkout, ["new.py"], {"app.py"})
        untracked.unlink()
        (self.checkout / "alias").symlink_to(self.checkout)
        with self.assertRaisesRegex(AgentError, "Symlink"):
            authorized_files(self.checkout, ["alias/new.py"], {"app.py"})
        self.assertEqual(read_selected(self.checkout, ["src/new_module/feature.py"]),
                         {"src/new_module/feature.py": ""})

    def test_extended_file_budget_remains_bounded(self):
        from gh_agent.core import MAX_FILES
        self.assertGreater(MAX_FILES, 5)
        paths = [f"src/new_{i}.py" for i in range(MAX_FILES)]
        validate_selection(self.checkout, paths, {"app.py"}, set(paths))
        with self.assertRaisesRegex(AgentError, "distinct paths"):
            validate_selection(self.checkout, paths + ["src/extra.py"], {"app.py"})

    @unittest.skipUnless(os.name == "posix", "Docker verification is POSIX-only")
    def test_isolated_workspace_is_writable_disposable_copy(self):
        image = "trusted/image@sha256:" + "a" * 64
        captured = {}
        def fake_run(argv, **kwargs):
            mount = next(argv[i+1] for i, value in enumerate(argv) if value == "--mount")
            self.assertNotIn(",readonly", mount)
            workspace = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            self.assertNotEqual(workspace, self.checkout)
            (workspace / "app.py").write_text("test modified\n")
            (workspace / "build.txt").write_text("generated\n")
            captured["workspace"] = workspace
            return subprocess.CompletedProcess(argv, 0)
        with patch("gh_agent.verification.subprocess.run", side_effect=fake_run):
            result = run_isolated(self.checkout, image, ["python", "-V"], 15)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual((self.checkout / "app.py").read_text(), "x = 1\n")
        self.assertFalse((self.checkout / "build.txt").exists())
        self.assertFalse(captured["workspace"].exists())

    def test_ready_pr_parser_is_explicit(self):
        args = cli.make_parser().parse_args(["publish", "--checkout", str(self.checkout),
            "--proposal", str(self.planfile), "--approve-publish", "--ready-for-review"])
        self.assertTrue(args.ready_for_review)
        default = cli.make_parser().parse_args(["publish", "--checkout", str(self.checkout),
            "--proposal", str(self.planfile), "--approve-publish"])
        self.assertFalse(default.ready_for_review)

    def test_local_apply_actual_commit_and_receipt(self):
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        branch = git(self.checkout, "branch", "--show-current")
        self.assertEqual(branch, "agent/issue-7-" + self.base[:10])
        self.assertEqual((self.checkout / "app.py").read_text(), "x = 2\n")
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        self.assertEqual(receipt["commit"], git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(receipt["proposal_sha256"], sha(self.planfile.read_bytes()))
        self.assertEqual(receipt["checks"]["git_diff_check"], "PASS")
        self.assertEqual(receipt["checks"]["target_tests"], "NOT_RUN")
        with self.assertRaises(AgentError):
            cli.publish(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=False))

    def test_apply_requires_exact_reviewed_proposal_hash(self):
        private_json_write(self.planfile, self.proposal())
        with self.assertRaisesRegex(AgentError, "SHA256 approval"):
            cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                approve=True, expected_sha256="0" * 64))
        with self.assertRaisesRegex(AgentError, "SHA256 approval"):
            cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                approve=True))
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_stale_base_blocks_apply(self):
        record = self.proposal()
        record["base_sha"] = "0" * 40
        private_json_write(self.planfile, record)
        with self.assertRaises(AgentError):
            cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_run_auto_requires_all_consents_before_side_effects(self):
        args = argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile), repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True, allowed_file=["app.py"], approve_local=False, approve_publish=True, approve_unverified=True, unverified_reason="Offline mocked publish has no executable target tests")
        with self.assertRaises(AgentError):
            cli.run_auto(args)
        self.assertFalse(self.planfile.exists())
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_autonomous_run_rejects_workflow_scope_before_side_effects(self):
        args = argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
            repo="example/safe-repo", issue=7, model="stub",
            allowed_file=[".github/workflows/publish.yml"],
            allow_source_upload=True, approve_local=True, approve_publish=True,
            approve_unverified=True,
            unverified_reason="Offline mocked publish has no executable target tests")
        with patch.object(cli, "plan") as plan:
            with self.assertRaisesRegex(AgentError, "cannot edit GitHub Actions workflows"):
                cli.run_auto(args)
            plan.assert_not_called()
        self.assertFalse(self.planfile.exists())
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_run_auto_calls_pipeline_when_opted_in(self):
        args = argparse.Namespace(checkout="repo", output=str(self.planfile), repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True, allowed_file=["app.py"], approve_local=True, approve_publish=True, approve_unverified=True, unverified_reason="Offline mocked publish has no executable target tests")
        calls = []
        def fake_plan(a):
            calls.append("plan")
            private_json_write(self.planfile, self.proposal())
        with patch.object(cli, "plan", side_effect=fake_plan), patch.object(cli, "apply", side_effect=lambda a: calls.append("apply")), patch.object(cli, "publish", side_effect=lambda a: calls.append("publish")):
            cli.run_auto(args)
        self.assertEqual(calls, ["plan", "apply", "publish"])

    def test_run_rejects_missing_test_plan_before_mutation(self):
        args = argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
            repo="example/safe-repo", issue=7, model="stub", allowed_file=["app.py"],
            allow_source_upload=True, approve_local=True, approve_publish=True)
        with self.assertRaisesRegex(AgentError, "without tests"):
            cli.run_auto(args)
        self.assertFalse(self.planfile.exists())
        args.test_image = "test@sha256:" + "a" * 64
        with self.assertRaisesRegex(AgentError, "both"):
            cli.run_auto(args)
        self.assertFalse(self.planfile.exists())

    def test_data_disclosure_requires_opt_in(self):
        with self.assertRaises(AgentError):
            cli.plan(argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile), repo="example/safe-repo", issue=7, model="stub", allow_source_upload=False))
        self.assertFalse(self.planfile.exists())

    def test_push_url_must_match_repo(self):
        git(self.checkout, "remote", "set-url", "--push", "origin", "https://github.com/other/target.git")
        with self.assertRaises(AgentError):
            assert_checkout(self.checkout, "example/safe-repo", "main", require_base=True)

    def test_multiple_push_destinations_are_blocked(self):
        git(self.checkout, "config", "--add", "remote.origin.pushurl", "https://github.com/example/safe-repo.git")
        git(self.checkout, "config", "--add", "remote.origin.pushurl", "https://github.com/example/second.git")
        with self.assertRaises(AgentError):
            assert_checkout(self.checkout, "example/safe-repo", "main", require_base=True)

    def test_plan_with_mock_services_no_external_calls(self):
        class MockGH:
            def __init__(self, token, repo):
                self.repo = repo
            def metadata(self):
                return {"default_branch": "main"}
            def issue(self, number):
                return {"number": number, "title": "Set value", "body": "x=2", "state": "open", "updated_at": "2026-10-15T00:00:00Z"}
        class MockModel:
            count = 0
            def __init__(self, token, model):
                pass
            def ask(self, *args):
                MockModel.count += 1
                return {"summary": "change", "edits": [{"path": "app.py", "base_sha256": sha(b"x = 1\n"), "content": "x = 2\n"}]}
        with patch.object(cli, "GitHub", MockGH), patch.object(cli, "Model", MockModel):
            cli.plan(argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile), repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True, allowed_file=["app.py"]))
        self.assertEqual(json.loads(self.planfile.read_text())["base_sha"], self.base)
        self.assertEqual((self.checkout / "app.py").read_text(), "x = 1\n")
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")

    def test_publish_with_mocked_network_reconciles_draft(self):
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        remote = {"branch_sha": None, "pr": None, "push_count": 0}
        original_git = cli.run_git

        def mock_git(checkout, *argv, **kwargs):
            if argv[0] == "push":
                self.assertIn(f"--force-with-lease=refs/heads/{receipt['branch']}:", argv)
                remote["push_count"] += 1
                remote["branch_sha"] = receipt["commit"]
                return ""
            return original_git(checkout, *argv, **kwargs)

        def mock_remote_branch(checkout, branch):
            return self.base if branch == "main" else remote["branch_sha"]

        class MockGH:
            def __init__(self, token, repo):
                pass
            def metadata(self):
                return {"default_branch": "main"}
            def issue(self, issue):
                return {"updated_at": "2026-10-15T00:00:00Z"}
            def existing_pr(self, branch, base):
                return remote["pr"]
            def post(self, route, data):
                self_test.assertEqual(data["draft"], True)
                remote["pr"] = {"state": "open", "draft": True, "html_url": "https://github.com/example/safe-repo/pull/1", "head": {"sha": receipt["commit"]}}
        self_test = self
        args = argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=True, approve_unverified=True, unverified_reason="Offline mocked publish has no executable target tests")
        with patch.object(cli, "run_git", mock_git), patch.object(cli, "remote_branch_sha", mock_remote_branch), patch.object(cli, "GitHub", MockGH):
            cli.publish(args)
            cli.publish(args)  # retry discovers existing PR; no second push or PR
        self.assertEqual(remote["push_count"], 1)

    def test_ready_pr_creation_and_reconciliation(self):
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                                     approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        remote = {"sha": None, "pr": None, "created": 0}
        original_git = cli.run_git
        def mock_git(checkout, *args, **kwargs):
            if args[0] == "push":
                remote["sha"] = receipt["commit"]
                return ""
            return original_git(checkout, *args, **kwargs)
        def mock_ref(checkout, branch):
            return self.base if branch == "main" else remote["sha"]
        class MockGH:
            def __init__(self, *args): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, *args): return {"updated_at": "2026-10-15T00:00:00Z"}
            def existing_pr(self, *args): return remote["pr"]
            def post(self, route, data):
                self_test.assertFalse(data["draft"])
                remote["created"] += 1
                remote["pr"] = {"state": "open", "draft": False,
                                "head": {"sha": receipt["commit"]}, "html_url": "https://example.invalid/1"}
        self_test = self
        args = argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile),
                                  approve_publish=True, approve_unverified=True,
                                  unverified_reason="Offline mocked publish has no executable target tests",
                                  ready_for_review=True)
        with patch.object(cli, "run_git", mock_git), patch.object(cli, "remote_branch_sha", mock_ref), patch.object(cli, "GitHub", MockGH):
            cli.publish(args)
            cli.publish(args)
            args.ready_for_review = False
            with self.assertRaisesRegex(AgentError, "unexpected review state"):
                cli.publish(args)
        self.assertEqual(remote["created"], 1)

    def test_exact_remote_branch_ref_rejects_suffix_ambiguity(self):
        with patch("gh_agent.core.run_git", return_value=self.base + "\trefs/heads/other/main"):
            with self.assertRaisesRegex(AgentError, "Unexpected remote branch response"):
                remote_branch_sha(self.checkout, "main")
        with patch("gh_agent.core.run_git", return_value=self.base + "\trefs/heads/main\n" + self.base + "\trefs/heads/main"):
            with self.assertRaisesRegex(AgentError, "Ambiguous"):
                remote_branch_sha(self.checkout, "main")

    def test_publish_aborts_when_remote_base_moves_after_push(self):
        private_json_write(self.planfile, self.proposal())
        with redirect_stdout(StringIO()):
            cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        state = {"checks": 0, "branch": None, "pr_created": False}
        actual_git = cli.run_git

        def remote_branch(checkout, branch):
            if branch == "main":
                state["checks"] += 1
                return self.base if state["checks"] == 1 else "a" * 40
            return state["branch"]

        def mock_git(checkout, *argv, **kwargs):
            if argv[0] == "push":
                state["branch"] = receipt["commit"]
                return ""
            return actual_git(checkout, *argv, **kwargs)

        class MockGH:
            def __init__(self, *args): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, i): return {"updated_at": "2026-10-15T00:00:00Z"}
            def existing_pr(self, *args):
                state["pr_created"] = True
                raise AssertionError("PR must not be queried after base moves")

        with patch.object(cli, "run_git", mock_git), patch.object(cli, "remote_branch_sha", remote_branch), patch.object(cli, "GitHub", MockGH):
            with self.assertRaisesRegex(AgentError, "Remote base moved during publication"):
                cli.publish(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=True, approve_unverified=True, unverified_reason="Offline mocked publish has no executable target tests"))
        self.assertFalse(state["pr_created"])
        self.assertEqual(state["branch"], receipt["commit"])

    def test_pr_page_boundary_fails_closed(self):
        gh = GitHub("token", "example/safe-repo")
        with patch.object(gh, "get", return_value=[{}] * 100):
            with self.assertRaisesRegex(AgentError, "incomplete"):
                gh.existing_pr("agent/example", "main")

    def test_malformed_pr_search_records_fail_closed(self):
        gh = GitHub("token", "example/safe-repo")
        malformed = [
            None,
            {},
            {"head": None, "base": {"ref": "main"}, "state": "open"},
            {"head": {"ref": "agent/test"}, "base": None, "state": "open"},
            {"head": {"ref": 42}, "base": {"ref": "main"}, "state": "open"},
            {"head": {"ref": "agent/test"}, "base": {"ref": "main"}, "state": None},
        ]
        for entry in malformed:
            with self.subTest(entry=entry), patch.object(gh, "get", return_value=[entry]):
                with self.assertRaisesRegex(AgentError, "Malformed PR search entry"):
                    gh.existing_pr("agent/test", "main")

    def test_valid_pr_search_results_preserve_matching_behavior(self):
        gh = GitHub("token", "example/safe-repo")
        unrelated = {"head": {"ref": "other"}, "base": {"ref": "main"}, "state": "open"}
        matching = {"head": {"ref": "agent/test"}, "base": {"ref": "main"}, "state": "open", "draft": True}
        with patch.object(gh, "get", return_value=[unrelated, matching]):
            self.assertIs(gh.existing_pr("agent/test", "main"), matching)
        with patch.object(gh, "get", return_value=[unrelated]):
            self.assertIsNone(gh.existing_pr("agent/test", "main"))

    def test_duplicate_matching_prs_fail_closed(self):
        gh = GitHub("token", "example/safe-repo")
        first = {"head": {"ref": "agent/test"}, "base": {"ref": "main"}, "state": "open", "draft": True}
        second = {"head": {"ref": "agent/test"}, "base": {"ref": "main"}, "state": "open", "draft": True}
        with patch.object(gh, "get", return_value=[first, second]):
            with self.assertRaisesRegex(AgentError, "Ambiguous PR search"):
                gh.existing_pr("agent/test", "main")

    def test_create_only_push_lease_is_enforced_by_git(self):
        # Real local Git remote: the lease allows an absent ref but must deny
        # any subsequent overwrite, including a fast-forward update.
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        branch = "agent/issue-7-test"
        run_git(self.checkout, "push", f"--force-with-lease=refs/heads/{branch}:", str(remote), f"HEAD:refs/heads/{branch}")
        (self.checkout / "app.py").write_text("x = 42\n", encoding="utf-8", newline="")
        git(self.checkout, "add", "app.py")
        git(self.checkout, "commit", "-m", "second")
        with self.assertRaisesRegex(AgentError, "Git push failed"):
            run_git(self.checkout, "push", f"--force-with-lease=refs/heads/{branch}:", str(remote), f"HEAD:refs/heads/{branch}")

    def test_repository_metadata_rejects_malformed_identity(self):
        gh = GitHub("test-token", "example/safe-repo")
        for name in (None, 123, [], {}, "other/repo"):
            with self.subTest(full_name=name):
                with patch("gh_agent.services.json_request", return_value={
                    "full_name": name, "default_branch": "main", "archived": False,
                }):
                    with self.assertRaisesRegex(AgentError, "Repository identity mismatch"):
                        gh.metadata()
        with patch("gh_agent.services.json_request", return_value={
            "full_name": "example/safe-repo", "default_branch": "main", "archived": False,
        }):
            self.assertEqual(gh.metadata()["default_branch"], "main")

    def test_repository_metadata_requires_safe_branch_and_boolean_archive(self):
        gh = GitHub("test-token", "example/safe-repo")
        valid = {"full_name": "example/safe-repo", "archived": False,
                 "default_branch": "release/2026.10"}
        with patch("gh_agent.services.json_request", return_value=valid):
            self.assertEqual(gh.metadata()["default_branch"], "release/2026.10")
        for bad in (None, False, 1, "", "-main", "main\\nunsafe", "main..evil",
                    "main//branch", "main.lock", "feature/", "main@{1}"):
            with self.subTest(default_branch=bad):
                with patch("gh_agent.services.json_request",
                           return_value={**valid, "default_branch": bad}):
                    with self.assertRaisesRegex(AgentError, "Invalid default branch"):
                        gh.metadata()
        for bad in (None, 0, "false", [], True):
            with self.subTest(archived=bad):
                with patch("gh_agent.services.json_request",
                           return_value={**valid, "archived": bad}):
                    with self.assertRaisesRegex(AgentError, "Repository identity mismatch"):
                        gh.metadata()

    def test_github_refuses_issue_as_pr_and_closed(self):
        gh = GitHub("test-token", "example/safe-repo")
        with patch.object(gh, "get", return_value={"number": 5, "state": "open", "title": "X", "pull_request": {}}):
            with self.assertRaises(AgentError): gh.issue(5)
        with patch.object(gh, "get", return_value={"number": 5, "state": "closed", "title": "X"}):
            with self.assertRaises(AgentError): gh.issue(5)

    def test_github_rejects_boolean_issue_number(self):
        gh = GitHub("test-token", "example/safe-repo")
        valid = {"number": 1, "state": "open", "title": "Test", "body": "",
                 "updated_at": "2026-10-16T00:00:00Z"}
        with patch.object(gh, "get", return_value={**valid, "number": True}):
            with self.assertRaisesRegex(AgentError, "Expected open issue"):
                gh.issue(1)
        with patch.object(gh, "get", return_value=valid):
            self.assertEqual(gh.issue(1)["number"], 1)

    def test_github_issue_body_requires_null_or_string(self):
        gh = GitHub("test-token", "example/safe-repo")
        valid = {"number": 7, "state": "open", "title": "Task",
                 "updated_at": "2026-10-16T00:00:00Z"}
        for bad in (False, 0, [], {}):
            with self.subTest(body=bad):
                with patch.object(gh, "get", return_value={**valid, "body": bad}):
                    with self.assertRaisesRegex(AgentError, "Invalid issue fields"):
                        gh.issue(7)
        for good in (None, "", "Description"):
            with self.subTest(body=good):
                with patch.object(gh, "get", return_value={**valid, "body": good}):
                    self.assertEqual(gh.issue(7).get("body"), good)

    def test_model_rejects_malformed_message_content(self):
        for malformed in (None, "text", {"type": "output_text"}, 123, [None]):
            with self.subTest(content=malformed):
                response = {"status": "completed", "output": [
                    {"type": "message", "content": malformed},
                ]}
                with patch("gh_agent.services.json_request", return_value=response):
                    with self.assertRaisesRegex(AgentError, "Malformed model message content"):
                        Model("key", "name").ask("instructions", {"a": 1}, {"type": "object"}, "test")

    def test_model_rejects_refusal_even_with_structured_text(self):
        for parts in (
            [{"type": "refusal", "refusal": "Cannot comply"}],
            [{"type": "output_text", "text": '{"ok": true}'},
             {"type": "refusal", "refusal": "Cannot comply"}],
        ):
            with self.subTest(parts=parts):
                response = {"status": "completed", "output": [
                    {"type": "message", "content": parts},
                ]}
                with patch("gh_agent.services.json_request", return_value=response):
                    with self.assertRaisesRegex(AgentError, "Model response refused"):
                        Model("key", "name").ask("instructions", {}, {"type": "object"}, "test")

    def test_model_accepts_single_structured_message(self):
        response = {"status": "completed", "output": [
            {"type": "reasoning", "content": None},
            {"type": "message", "content": [{"type": "output_text", "text": '{"ok": true}'}]},
        ]}
        with patch("gh_agent.services.json_request", return_value=response):
            self.assertEqual(Model("key", "name").ask("instructions", {}, {"type": "object"}, "test"), {"ok": True})

    def test_model_rejects_unexpected_output_items(self):
        valid = {"type": "message", "content": [{"type": "output_text", "text": '{"ok": true}'}]}
        for extra in (
            None,
            {"type": "function_call", "name": "unsafe", "arguments": "{}"},
            {"type": "unexpected"},
        ):
            with self.subTest(extra=extra):
                response = {"status": "completed", "output": [extra, valid]}
                with patch("gh_agent.services.json_request", return_value=response):
                    with self.assertRaisesRegex(AgentError, "model output item"):
                        Model("key", "name").ask("instructions", {}, {"type": "object"}, "test")

    def test_model_rejects_non_text_message_parts_and_incomplete_message(self):
        for message, error in (
            ({"type": "message", "content": [
                {"type": "output_text", "text": '{"ok": true}'},
                {"type": "input_text", "text": "unexpected"}]}, "Unexpected model message content"),
            ({"type": "message", "status": "in_progress", "content": [
                {"type": "output_text", "text": '{"ok": true}'}]}, "Model message incomplete"),
        ):
            with self.subTest(error=error):
                with patch("gh_agent.services.json_request", return_value={
                    "status": "completed", "output": [message],
                }):
                    with self.assertRaisesRegex(AgentError, error):
                        Model("key", "name").ask("instructions", {}, {"type": "object"}, "test")

    def test_outbound_json_surrogates_fail_before_network(self):
        from gh_agent.services import json_request
        with patch("gh_agent.services.build_opener") as opener:
            with self.assertRaisesRegex(AgentError, "Invalid API request JSON"):
                json_request("https://api.github.com/repos/example/safe-repo",
                             token="fake", github=True, payload={"text": "\ud800"})
            opener.assert_not_called()
        with patch("gh_agent.services.json_request") as send:
            with self.assertRaisesRegex(AgentError, "Invalid model context JSON"):
                Model("key", "name").ask("instructions", {"text": "\ud800"},
                                         {"type": "object"}, "test")
            send.assert_not_called()

    def test_json_request_and_model_reject_nonfinite_outbound_data(self):
        from gh_agent.services import json_request
        with patch("gh_agent.services.build_opener") as opener:
            with self.assertRaisesRegex(AgentError, "Invalid API request JSON"):
                json_request("https://api.github.com/repos/example/safe-repo",
                             token="fake", github=True, payload={"value": float("nan")})
            opener.assert_not_called()
        with patch("gh_agent.services.json_request") as send:
            with self.assertRaisesRegex(AgentError, "Invalid model context JSON"):
                Model("key", "name").ask("instructions", {"value": float("inf")},
                                         {"type": "object"}, "test")
            send.assert_not_called()

    def test_model_rejects_surrogate_and_overflow_output(self):
        for value in ('1e999', '"\\ud800"'):
            with self.subTest(value=value):
                response = {"status": "completed", "output": [{
                    "type": "message", "content": [{
                        "type": "output_text", "text": '{"value": ' + value + '}',
                    }],
                }]}
                with patch("gh_agent.services.json_request", return_value=response):
                    with self.assertRaisesRegex(AgentError, "Invalid structured model output"):
                        Model("key", "name").ask("instructions", {}, {"type": "object"}, "test")

    def test_model_rejects_ambiguous_structured_json(self):
        for payload in (
            '{"ok": true, "ok": false}',
            '{"nested": {"key": 1, "key": 2}}',
            '{"value": NaN}',
            '{"value": Infinity}',
            '{"value": -Infinity}',
        ):
            with self.subTest(payload=payload):
                response = {"status": "completed", "output": [
                    {"type": "message", "content": [
                        {"type": "output_text", "text": payload}
                    ]}
                ]}
                with patch("gh_agent.services.json_request", return_value=response):
                    with self.assertRaisesRegex(AgentError, "Invalid structured model output"):
                        Model("key", "name").ask("instructions", {}, {"type": "object"}, "test")

    def test_saved_state_rejects_ambiguous_json(self):
        from gh_agent.core import load_json
        for raw in (
            '{"schema": 2, "schema": 1}',
            '{"outer": {"commit": "a", "commit": "b"}}',
            '{"result": NaN}',
            '{"result": Infinity}',
            '{"result": -Infinity}',
            '{"bad":',
        ):
            with self.subTest(raw=raw):
                self.planfile.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(AgentError, "Cannot read valid JSON"):
                    load_json(self.planfile)
        self.planfile.write_text('{"schema": 2}', encoding="utf-8")
        self.assertEqual(load_json(self.planfile), {"schema": 2})

    def test_api_json_rejects_duplicate_keys_and_nonfinite_values(self):
        from gh_agent.services import json_request
        class Response:
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return None
            def read(self, _limit):
                return self.body

        for raw in (
            b'{"ok": true, "ok": false}',
            b'{"nested": {"x": 1, "x": 2}}',
            b'{"value": NaN}',
            b'{"value": Infinity}',
            b'{"value": -Infinity}',
        ):
            with self.subTest(raw=raw), patch("gh_agent.services.build_opener") as opener:
                opener.return_value.open.return_value = Response(raw)
                with self.assertRaisesRegex(AgentError, "invalid JSON"):
                    json_request("https://api.github.com/repos/example/safe-repo",
                                 token="fake", github=True)
        with patch("gh_agent.services.build_opener") as opener:
            opener.return_value.open.return_value = Response(b'{"ok": true}')
            self.assertEqual(
                json_request("https://api.github.com/repos/example/safe-repo",
                             token="fake", github=True), {"ok": True})

    def test_model_incomplete_is_blocked(self):
        with patch("gh_agent.services.json_request", return_value={"status": "incomplete", "output": []}):
            with self.assertRaises(AgentError):
                Model("key", "name").ask("instructions", {"a": 1}, {"type": "object"}, "test")


    def test_authorized_scope_rejects_missing_duplicate_and_outside(self):
        tracked = {"app.py"}
        with self.assertRaises(AgentError):
            authorized_files(self.checkout, None, tracked)
        with self.assertRaises(AgentError):
            authorized_files(self.checkout, ["app.py", "app.py"], tracked)
        with self.assertRaises(AgentError):
            validate_selection(self.checkout, ["app.py"], tracked, {"another.py"})
        with self.assertRaises(AgentError):
            validate_selection(self.checkout, [["app.py"]], tracked)

    def test_source_secret_guard_blocks_likely_credentials(self):
        for content in ["OPENAI_API_KEY=sk-" + "Z" * 35,
                        "token = github_pat_" + "a" * 35,
                        "-----BEGIN PRIVATE KEY-----\nABC\n"]:
            with self.subTest(content=content[:14]), self.assertRaises(AgentError):
                validate_source_sensitivity("app.py", content)
        validate_source_sensitivity("app.py", "def f(): return 1\n")

    def test_terminal_control_payload_blocked(self):
        with self.assertRaisesRegex(AgentError, "Control character"):
            validate_source_sensitivity("app.py", "print('ok')\x1b[2J")
        with self.assertRaisesRegex(AgentError, "Control character"):
            validate_edits(self.checkout, [{"path": "app.py", "base_sha256": sha(b"x = 1\n"),
                "content": "x = 2\n# malicious\x1b[2J\n"}], {"app.py": "x = 1\n"}, {"app.py"})

    def test_remote_ref_exact_lookup_on_local_bare_git(self):
        bare = self.root / "exact.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        git(self.checkout, "remote", "set-url", "origin", str(bare))
        run_git(self.checkout, "push", "origin", "HEAD:refs/heads/prefix/main")
        self.assertIsNone(remote_branch_sha(self.checkout, "main"))
        run_git(self.checkout, "push", "origin", "HEAD:refs/heads/main")
        self.assertEqual(remote_branch_sha(self.checkout, "main"), self.base)

    def test_syntax_validation_rejects_broken_python_and_json(self):
        for path, content in [("app.py", "def broken(:\n"), ("config.json", "{broken")]:
            with self.subTest(path=path), self.assertRaises(AgentError):
                validate_content_syntax(path, content)
        validate_content_syntax("app.py", "x=123\n")
        validate_content_syntax("data.json", '{"ok": true}')

    def test_review_does_not_change_worktree(self):
        private_json_write(self.planfile, self.proposal())
        buf = StringIO()
        with redirect_stdout(buf):
            cli.review(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile)))
        self.assertIn("PROPOSAL_REVIEW", buf.getvalue())
        self.assertIn("Proposal SHA256", buf.getvalue())
        self.assertIn("+x = 2", buf.getvalue())
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")

    def test_publish_rejects_changed_proposal_before_remote_access(self):
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        obj = json.loads(self.planfile.read_text())
        obj["summary"] = "tampered after approval"
        self.planfile.write_text(json.dumps(obj))
        with self.assertRaisesRegex(AgentError, "Proposal changed"):
            cli.publish(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=True, approve_unverified=True, unverified_reason="Offline mocked publish has no executable target tests"))

    def test_legacy_schema_cannot_bypass_scoped_authorization(self):
        record = self.proposal()
        record["schema"] = 1
        record.pop("authorized_files")
        private_json_write(self.planfile, record)
        with self.assertRaisesRegex(AgentError, "Unsupported proposal schema"):
            cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_plan_rejects_model_outside_scope_without_output(self):
        class MockGH:
            def __init__(self, *args): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, i): return {"number": i, "title": "Change", "body": "", "updated_at": "stamp"}
        class OutOfScopeModel:
            def __init__(self, *args): pass
            def ask(self, *args): return {"summary": "wrong scope", "edits": [
                {"path": "other.py", "base_sha256": sha(b""), "content": "x = 3\n"}]}
        with patch.object(cli, "GitHub", MockGH), patch.object(cli, "Model", OutOfScopeModel):
            with self.assertRaises(AgentError):
                cli.plan(argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
                            repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True,
                            allowed_file=["app.py"]))
        self.assertFalse(self.planfile.exists())

    def test_closed_pr_cannot_be_reused(self):
        gh = GitHub("token", "example/safe-repo")
        closed = {"head": {"ref": "agent/test"}, "base": {"ref": "main"}, "state": "closed", "draft": True}
        with patch.object(gh, "get", return_value=[closed]):
            with self.assertRaisesRegex(AgentError, "closed"):
                gh.existing_pr("agent/test", "main")

    def test_no_output_for_suspicious_source_before_model_call(self):
        (self.checkout / "app.py").write_text("OPENAI_API_KEY=sk-" + "x" * 40 + "\n", newline="")
        git(self.checkout, "add", "app.py")
        git(self.checkout, "commit", "-m", "test sensitive")
        new_sha = git(self.checkout, "rev-parse", "HEAD")
        git(self.checkout, "update-ref", "refs/remotes/origin/main", new_sha)
        class MockGH:
            def __init__(self, *args): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, n): return {"number": n, "title": "task", "body": "", "updated_at": "timestamp"}
        with patch.object(cli, "GitHub", MockGH), patch.object(cli, "Model") as model:
            with self.assertRaisesRegex(AgentError, "credential"):
                cli.plan(argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
                            repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True,
                            allowed_file=["app.py"]))
            model.assert_not_called()
        self.assertFalse(self.planfile.exists())

    def test_run_auto_plan_apply_publish_integration_with_stubs(self):
        class MockGH:
            def __init__(self, token, repo): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, i): return {"number": i, "title": "fix", "body": "set x 2", "updated_at": "timestamp"}
        class MockModel:
            calls = 0
            def __init__(self, *args): pass
            def ask(self, *args):
                MockModel.calls += 1
                return {"summary": "fix", "edits": [{"path": "app.py", "base_sha256": sha(b"x = 1\n"), "content": "x = 2\n"}]}
        args = argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
            repo="example/safe-repo", issue=7, model="stub", allowed_file=["app.py"],
            allow_source_upload=True, approve_local=True, approve_publish=True, approve_unverified=True, unverified_reason="Offline mocked publish has no executable target tests")
        published = []
        with patch.object(cli, "GitHub", MockGH), patch.object(cli, "Model", MockModel), \
             patch.object(cli, "publish", side_effect=lambda a: published.append(a)):
            cli.run_auto(args)
        self.assertEqual(len(published), 1)
        self.assertEqual((self.checkout / "app.py").read_text(), "x = 2\n")
        self.assertTrue(Path(str(self.planfile) + ".applied.json").exists())


    def test_issue_without_timestamp_rejected(self):
        gh = GitHub("token", "example/safe-repo")
        with patch.object(gh, "get", return_value={"number": 7, "title": "issue", "body": "", "state": "open"}):
            with self.assertRaisesRegex(AgentError, "timestamp"):
                gh.issue(7)

    def test_cli_plan_requires_scope(self):
        with self.assertRaises(SystemExit):
            cli.make_parser().parse_args(["plan", "--repo", "example/safe-repo", "--issue", "7",
                "--checkout", str(self.checkout), "--model", "stub", "--output", str(self.planfile)])

    def test_output_source_not_automatically_printed_by_plan(self):
        class MockGH:
            def __init__(self, *args): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, i): return {"number": i, "title": "fix", "body": "set x", "updated_at": "stamp"}
        class MockModel:
            calls = 0
            def __init__(self, *args): pass
            def ask(self, *args):
                MockModel.calls += 1
                return {"summary": "private", "edits": [{"path": "app.py", "base_sha256": sha(b"x = 1\n"), "content": "x = 8888\n"}]}
        output = StringIO()
        with patch.object(cli, "GitHub", MockGH), patch.object(cli, "Model", MockModel), redirect_stdout(output):
            cli.plan(argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
                repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True, allowed_file=["app.py"]))
        self.assertNotIn("x = 8888", output.getvalue())
        self.assertIn("x = 8888", self.planfile.read_text())

    def test_committed_blob_bytes_match_proposal(self):
        from gh_agent.core import committed_blob
        private_json_write(self.planfile, self.proposal())
        cli.apply(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve=True, expected_sha256=sha(self.planfile.read_bytes())))
        receipt = json.loads(Path(str(self.planfile) + ".applied.json").read_text())
        self.assertEqual(committed_blob(self.checkout, receipt["commit"], "app.py"), b"x = 2\n")
        with self.assertRaises(AgentError):
            committed_blob(self.checkout, receipt["commit"], ".env")

    def test_api_transport_disconnects_fail_with_sanitized_error(self):
        from http.client import HTTPException
        from gh_agent.services import json_request
        for failure in (ConnectionResetError("closed by peer"),
                        HTTPException("malformed response")):
            with self.subTest(failure=type(failure).__name__):
                with patch("gh_agent.services.build_opener") as opener:
                    opener.return_value.open.side_effect = failure
                    with self.assertRaisesRegex(AgentError, "API request failed or returned invalid JSON"):
                        json_request("https://api.github.com/repos/example/safe-repo",
                                     token="dummy", github=True)
                    opener.return_value.open.assert_called_once()

    def test_api_endpoint_allowlist(self):
        from gh_agent.services import json_request
        with self.assertRaisesRegex(AgentError, "allowlisted"):
            json_request("https://api.github.com.evil.example/repos/repo", token="test", github=True)

    def test_plan_rejects_credential_in_issue_before_model(self):
        class MockGH:
            def __init__(self, *args): pass
            def metadata(self): return {"default_branch": "main"}
            def issue(self, n):
                return {"number": n, "title": "token", "body": "GITHUB_TOKEN=" + "a" * 50, "updated_at": "stamp"}
        with patch.object(cli, "GitHub", MockGH), patch.object(cli, "Model") as model:
            with self.assertRaisesRegex(AgentError, "credential"):
                cli.plan(argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
                    repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True,
                    allowed_file=["app.py"]))
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
