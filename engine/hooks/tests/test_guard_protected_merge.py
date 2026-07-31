#!/usr/bin/env python3
"""Tests for guard_protected_merge — the owner guardrail.

Owner rule: Claude never merges or writes to main/master anywhere.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import bash_payload, make_kit, patched, run_hook

MOD = _support.load_hook("guard_protected_merge")

KIT = make_kit()  # protected_branches: ["main", "master"]


def run_bash(command, current_branch):
    with patched(
        MOD,
        load_kit=lambda force_reload=False: KIT,
        get_current_branch=lambda cwd=None: current_branch,
    ):
        return run_hook(MOD, bash_payload(command))


class MergeIntoProtectedTest(unittest.TestCase):
    def test_merge_into_main_blocked(self):
        code, _out, err = run_bash("git merge feature/add-widget", current_branch="main")
        self.assertEqual(code, 2)
        self.assertIn("owner", err.lower())

    def test_merge_into_master_blocked(self):
        code, _out, _err = run_bash("git merge fix/bug", current_branch="master")
        self.assertEqual(code, 2)

    def test_rebase_on_main_blocked(self):
        code, _out, _err = run_bash("git rebase feature/x", current_branch="main")
        self.assertEqual(code, 2)

    def test_merge_on_feature_branch_allowed(self):
        code, _out, err = run_bash("git merge main", current_branch="feature/add-widget")
        self.assertEqual(code, 0, err)

    def test_rebase_main_from_feature_branch_allowed(self):
        code, _out, err = run_bash("git rebase main", current_branch="feature/add-widget")
        self.assertEqual(code, 0, err)

    def test_merge_abort_allowed_even_on_main(self):
        code, _out, err = run_bash("git merge --abort", current_branch="main")
        self.assertEqual(code, 0, err)

    def test_chained_checkout_main_then_merge_blocked(self):
        code, _out, _err = run_bash(
            "git checkout main && git merge feature/add-widget",
            current_branch="feature/add-widget",
        )
        self.assertEqual(code, 2)

    def test_chained_switch_back_to_feature_then_merge_allowed(self):
        code, _out, err = run_bash(
            "git switch feature/add-widget && git merge origin/develop",
            current_branch="main",
        )
        self.assertEqual(code, 0, err)


class GhPrMergeTest(unittest.TestCase):
    def test_gh_pr_merge_blocked(self):
        code, _out, err = run_bash("gh pr merge 42 --squash", current_branch="feature/x")
        self.assertEqual(code, 2)
        self.assertIn("owner", err.lower())

    def test_gh_pr_merge_in_chain_blocked(self):
        code, _out, _err = run_bash(
            "gh pr checks 42 && gh pr merge 42 --merge", current_branch="feature/x"
        )
        self.assertEqual(code, 2)

    def test_gh_pr_view_allowed(self):
        code, _out, err = run_bash("gh pr view 42 --json state", current_branch="feature/x")
        self.assertEqual(code, 0, err)


class PushRefspecTest(unittest.TestCase):
    def test_push_refspec_to_main_blocked(self):
        code, _out, _err = run_bash("git push origin HEAD:main", current_branch="feature/x")
        self.assertEqual(code, 2)

    def test_push_branch_to_main_refspec_blocked(self):
        code, _out, _err = run_bash("git push origin feature/x:main", current_branch="feature/x")
        self.assertEqual(code, 2)

    def test_push_explicit_main_blocked(self):
        code, _out, _err = run_bash("git push origin main", current_branch="feature/x")
        self.assertEqual(code, 2)

    def test_push_refs_heads_main_blocked(self):
        code, _out, _err = run_bash(
            "git push origin HEAD:refs/heads/main", current_branch="feature/x"
        )
        self.assertEqual(code, 2)

    def test_push_delete_main_blocked(self):
        code, _out, _err = run_bash("git push origin :main", current_branch="feature/x")
        self.assertEqual(code, 2)

    def test_push_delete_flag_main_blocked(self):
        code, _out, _err = run_bash("git push --delete origin main", current_branch="feature/x")
        self.assertEqual(code, 2)

    def test_push_feature_branch_allowed(self):
        code, _out, err = run_bash("git push origin feature/x", current_branch="feature/x")
        self.assertEqual(code, 0, err)

    def test_push_upstream_feature_branch_allowed(self):
        code, _out, err = run_bash("git push -u origin feature/x", current_branch="feature/x")
        self.assertEqual(code, 0, err)

    def test_bare_push_on_main_blocked(self):
        code, _out, _err = run_bash("git push", current_branch="main")
        self.assertEqual(code, 2)

    def test_bare_push_on_feature_branch_allowed(self):
        code, _out, err = run_bash("git push", current_branch="feature/x")
        self.assertEqual(code, 0, err)


class McpMirrorTest(unittest.TestCase):
    def _run_mcp(self, tool_name, tool_input):
        with patched(MOD, load_kit=lambda force_reload=False: KIT):
            return run_hook(MOD, {"tool_name": tool_name, "tool_input": tool_input})

    def test_merge_pull_request_blocked(self):
        code, _out, err = self._run_mcp("mcp__github__merge_pull_request",
                                        {"owner": "x", "repo": "y", "pullNumber": 1})
        self.assertEqual(code, 2)
        self.assertIn("owner-only", err)

    def test_push_files_to_main_blocked(self):
        code, _out, _err = self._run_mcp("mcp__github__push_files", {"branch": "main"})
        self.assertEqual(code, 2)

    def test_create_or_update_file_on_master_blocked(self):
        code, _out, _err = self._run_mcp("mcp__github__create_or_update_file", {"branch": "Master"})
        self.assertEqual(code, 2)

    def test_delete_file_on_main_blocked(self):
        code, _out, _err = self._run_mcp("mcp__github__delete_file", {"branch": "main"})
        self.assertEqual(code, 2)

    def test_push_files_to_feature_branch_allowed(self):
        code, _out, err = self._run_mcp("mcp__github__push_files", {"branch": "feature/x"})
        self.assertEqual(code, 0, err)

    def test_read_tools_allowed(self):
        code, _out, err = self._run_mcp("mcp__github__get_file_contents", {"ref": "main"})
        self.assertEqual(code, 0, err)


class FastPathTest(unittest.TestCase):
    def test_non_git_command_never_queries_branch(self):
        def boom(cwd=None):
            raise AssertionError("get_current_branch must not run for non-git commands")

        with patched(MOD, load_kit=lambda force_reload=False: KIT, get_current_branch=boom):
            code, _out, err = run_hook(MOD, bash_payload("ls -la"))
        self.assertEqual(code, 0, err)

    def test_custom_protected_branches_respected(self):
        kit = make_kit(protected_branches=["main", "master", "production"])
        with patched(
            MOD,
            load_kit=lambda force_reload=False: kit,
            get_current_branch=lambda cwd=None: "feature/x",
        ):
            code, _out, _err = run_hook(MOD, bash_payload("git push origin HEAD:production"))
        self.assertEqual(code, 2)


class ShellFormBypassTest(unittest.TestCase):
    """Regression: a push escaped the guard by hiding behind shell syntax.

    Reported 2026-08-01 from a homeassistant session that had already pushed to
    master three times. Two causes combined: something outside Claude checked
    out master after a PR merge (so the session believed it was on a feature
    branch), and `git push | tail -2` — a habitual output-trimming form —
    parsed as ONE command whose push arguments were ['|','tail','-2'], making
    `tail` read as an explicit, unprotected destination.

    Every form below must block while the checkout is ON a protected branch.
    """

    FORMS = [
        "git push | tail -2",            # the reported bypass
        "git push | cat",
        "git push |& tail",
        "git push &",                    # backgrounded
        "git push\ngit status",          # newline-separated
        "(git push)",                    # subshell
        "$(git push)",                   # command substitution
        "`git push`",                    # backticks
        "{ git push; }",                 # brace group
        "for f in a b; do git push; done",   # keyword becomes the command word
        "if true; then git push; fi",
        "sudo git push",                 # wrapper prefixes
        "command git push",
        "nohup git push",
        "env git push",
        "FOO=bar git push",              # env assignment prefix
        "cd repo && (git push | tail -1)",
    ]

    def test_every_shell_form_blocks_on_a_protected_branch(self):
        for form in self.FORMS:
            with self.subTest(form=form):
                code, _out, _err = run_bash(form, current_branch="master")
                self.assertEqual(code, 2, f"{form!r} was ALLOWED on master")

    def test_piped_push_to_protected_refspec_blocks_from_a_feature_branch(self):
        code, _out, _err = run_bash("git push origin HEAD:main | tail -2",
                                    current_branch="feature/x")
        self.assertEqual(code, 2)

    def test_piped_feature_push_still_allowed(self):
        # The fix must not turn the habitual form into a false positive.
        code, _out, err = run_bash("git push origin feature/x | tail -2",
                                   current_branch="feature/x")
        self.assertEqual(code, 0, err)

    def test_redirection_form_still_allowed_on_a_feature_branch(self):
        code, _out, err = run_bash("git push 2>&1", current_branch="feature/x")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
