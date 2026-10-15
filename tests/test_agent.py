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
        git(self.checkout, "config", "user.email", "tester@example.invalid")
        git(self.checkout, "config", "user.name", "Tester")
        (self.checkout / "app.py").write_text("x = 1\n", encoding="utf-8")
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

    def test_path_escape_and_protected(self):
        for p in ["../foo.py", ".env", ".github/workflows/ci.yml", "node_modules/a.js", "src/../../a.py", "/tmp/a.py", "src/.hidden/a.py", "credentials/a.py", "app.exe", "Dockerfile"]:
            with self.subTest(p=p), self.assertRaises(AgentError):
                check_path(p)
        self.assertEqual(check_path("src/app.py"), "src/app.py")
        (self.checkout / "src").mkdir()
        (self.checkout / "src" / "bad.py").symlink_to(self.checkout / "app.py")
        with self.assertRaises(AgentError):
            guarded_file(self.checkout, "src/bad.py", allow_new=False)

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
        args = argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile), repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True, allowed_file=["app.py"], approve_local=False, approve_publish=True)
        with self.assertRaises(AgentError):
            cli.run_auto(args)
        self.assertFalse(self.planfile.exists())
        self.assertEqual(git(self.checkout, "branch", "--show-current"), "main")

    def test_run_auto_calls_pipeline_when_opted_in(self):
        args = argparse.Namespace(checkout="repo", output=str(self.planfile), repo="example/safe-repo", issue=7, model="stub", allow_source_upload=True, allowed_file=["app.py"], approve_local=True, approve_publish=True)
        calls = []
        def fake_plan(a):
            calls.append("plan")
            private_json_write(self.planfile, self.proposal())
        with patch.object(cli, "plan", side_effect=fake_plan), patch.object(cli, "apply", side_effect=lambda a: calls.append("apply")), patch.object(cli, "publish", side_effect=lambda a: calls.append("publish")):
            cli.run_auto(args)
        self.assertEqual(calls, ["plan", "apply", "publish"])

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
                if MockModel.count == 1:
                    return {"rationale": "edit app", "paths": ["app.py"]}
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
        args = argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=True)
        with patch.object(cli, "run_git", mock_git), patch.object(cli, "remote_branch_sha", mock_remote_branch), patch.object(cli, "GitHub", MockGH):
            cli.publish(args)
            cli.publish(args)  # retry discovers existing PR; no second push or PR
        self.assertEqual(remote["push_count"], 1)

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
                cli.publish(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=True))
        self.assertFalse(state["pr_created"])
        self.assertEqual(state["branch"], receipt["commit"])

    def test_pr_page_boundary_fails_closed(self):
        gh = GitHub("token", "example/safe-repo")
        with patch.object(gh, "get", return_value=[{}] * 100):
            with self.assertRaisesRegex(AgentError, "incomplete"):
                gh.existing_pr("agent/example", "main")

    def test_create_only_push_lease_is_enforced_by_git(self):
        # Real local Git remote: the lease allows an absent ref but must deny
        # any subsequent overwrite, including a fast-forward update.
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        branch = "agent/issue-7-test"
        run_git(self.checkout, "push", f"--force-with-lease=refs/heads/{branch}:", str(remote), f"HEAD:refs/heads/{branch}")
        (self.checkout / "app.py").write_text("x = 42\n", encoding="utf-8")
        git(self.checkout, "add", "app.py")
        git(self.checkout, "commit", "-m", "second")
        with self.assertRaisesRegex(AgentError, "Git push failed"):
            run_git(self.checkout, "push", f"--force-with-lease=refs/heads/{branch}:", str(remote), f"HEAD:refs/heads/{branch}")

    def test_github_refuses_issue_as_pr_and_closed(self):
        gh = GitHub("test-token", "example/safe-repo")
        with patch.object(gh, "get", return_value={"number": 5, "state": "open", "title": "X", "pull_request": {}}):
            with self.assertRaises(AgentError): gh.issue(5)
        with patch.object(gh, "get", return_value={"number": 5, "state": "closed", "title": "X"}):
            with self.assertRaises(AgentError): gh.issue(5)

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
            cli.publish(argparse.Namespace(checkout=str(self.checkout), proposal=str(self.planfile), approve_publish=True))

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
            def ask(self, *args): return {"rationale": "change other path", "paths": ["other.py"]}
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
        (self.checkout / "app.py").write_text("OPENAI_API_KEY=sk-" + "x" * 40 + "\n")
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
                if MockModel.calls == 1: return {"rationale": "app", "paths": ["app.py"]}
                return {"summary": "fix", "edits": [{"path": "app.py", "base_sha256": sha(b"x = 1\n"), "content": "x = 2\n"}]}
        args = argparse.Namespace(checkout=str(self.checkout), output=str(self.planfile),
            repo="example/safe-repo", issue=7, model="stub", allowed_file=["app.py"],
            allow_source_upload=True, approve_local=True, approve_publish=True)
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
                if MockModel.calls == 1: return {"rationale": "app", "paths": ["app.py"]}
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
