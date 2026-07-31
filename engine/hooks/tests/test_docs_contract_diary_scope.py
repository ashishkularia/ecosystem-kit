#!/usr/bin/env python3
"""Tests for branch-scoped diaries and the commit-time diary checkpoint.

Contract (owner change, 2026-08-01):
  - `diary_scope: "branch"` (default) puts a change's diary in ONE file per
    branch — `YYYY-MM-DD-<branch-slug>.md`, dated when the branch's diary
    started and REUSED for the branch's whole life, so a change spanning days
    keeps its discussion together.
  - Falls back to the dated file (`YYYY-MM-DD.md`) under `diary_scope:
    "daily"`, on a detached HEAD, and outside a git repo.
  - PreToolUse on `git commit`: when a `decision`/`discussion` flag is pending
    and the diary has not been touched since, BLOCK (exit 2) — the reasoning
    goes in the diary at the commit that carries it, not at session end.
    A plain `code_change` never gates here (it rides to the Stop gate), so
    ordinary commits are not interrupted.
"""
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import make_kit, run_hook

MOD = _support.load_hook("docs_contract")
TODAY = date.today().isoformat()


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


class DiaryScopeTestBase(unittest.TestCase):
    scope = "branch"
    init_git = True
    branch = "fix/hygiene-findings-trio"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-diary-scope-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.memory = os.path.join(self.tmp, ".memory")
        self.diary_dir = os.path.join(self.memory, "diary")
        self.cache = os.path.join(self.memory, "cache")
        os.makedirs(self.diary_dir)
        os.makedirs(self.cache)

        if self.init_git:
            git("init", "-q", cwd=self.tmp)
            git("config", "user.email", "t@t.t", cwd=self.tmp)
            git("config", "user.name", "t", cwd=self.tmp)
            git("commit", "-q", "--allow-empty", "-m", "init", cwd=self.tmp)
            if self.branch:
                git("checkout", "-q", "-b", self.branch, cwd=self.tmp)

        kit = make_kit(diary=True)
        kit["diary_scope"] = self.scope
        self._stack = contextlib.ExitStack()
        self.addCleanup(self._stack.close)
        self._stack.enter_context(_support.patched(
            MOD,
            PROJECT_ROOT=self.tmp,
            MEMORY_DIR=self.memory,
            CACHE_DIR=self.cache,
            PENDING_FILE=os.path.join(self.cache, "pending.json"),
            load_kit=lambda force_reload=False: kit,
        ))


class BranchDiaryPathTest(DiaryScopeTestBase):
    def test_path_is_dated_branch_slug(self):
        self.assertEqual(
            os.path.basename(MOD.diary_path()),
            f"{TODAY}-fix-hygiene-findings-trio.md",
        )

    def test_existing_entry_is_reused_whatever_its_date(self):
        # The branch started days ago; today's work appends to THAT file rather
        # than opening a second entry for the same change.
        old = os.path.join(self.diary_dir, "2026-07-28-fix-hygiene-findings-trio.md")
        open(old, "w").close()
        self.assertEqual(MOD.diary_path(), old)

    def test_unrelated_branch_entries_are_not_reused(self):
        open(os.path.join(self.diary_dir, "2026-07-28-feature-other.md"), "w").close()
        self.assertEqual(
            os.path.basename(MOD.diary_path()),
            f"{TODAY}-fix-hygiene-findings-trio.md",
        )

    def test_slash_and_unsafe_chars_are_slugged(self):
        git("checkout", "-q", "-b", "feature/ODD name+chars", cwd=self.tmp)
        base = os.path.basename(MOD.diary_path())
        self.assertTrue(base.startswith(TODAY + "-"), base)
        self.assertNotIn("/", base)
        self.assertNotIn(" ", base)
        self.assertNotIn("+", base)


class DailyScopeTest(DiaryScopeTestBase):
    scope = "daily"

    def test_daily_scope_keeps_legacy_dated_file(self):
        self.assertEqual(os.path.basename(MOD.diary_path()), f"{TODAY}.md")


class DetachedHeadTest(DiaryScopeTestBase):
    branch = None

    def test_detached_head_falls_back_to_dated_file(self):
        sha = git("rev-parse", "HEAD", cwd=self.tmp).stdout.strip()
        git("checkout", "-q", sha, cwd=self.tmp)
        self.assertEqual(MOD.diary_path(), os.path.join(self.diary_dir, f"{TODAY}.md"))


class NonGitTest(DiaryScopeTestBase):
    init_git = False

    def test_outside_a_git_repo_falls_back_to_dated_file(self):
        self.assertEqual(MOD.diary_path(), os.path.join(self.diary_dir, f"{TODAY}.md"))


class PreCommitCheckpointTest(DiaryScopeTestBase):
    def commit_payload(self, command="git commit -m 'x'"):
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": self.tmp,
        }

    def touch_diary(self, when=None):
        path = MOD.diary_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write("entry\n")
        if when is not None:
            os.utime(path, (when, when))
        return path

    def test_pending_decision_with_stale_diary_blocks_the_commit(self):
        MOD.set_flag("decision", "chose X over Y")
        code, out, err = run_hook(MOD, self.commit_payload())
        self.assertEqual(code, 2)
        self.assertIn("diary", (err + out).lower())
        # Names the exact file to write, so the block is actionable.
        self.assertIn(f"{TODAY}-fix-hygiene-findings-trio.md", err + out)

    def test_writing_the_diary_unblocks_the_commit(self):
        MOD.set_flag("decision", "chose X over Y")
        self.touch_diary()
        code, _, _ = run_hook(MOD, self.commit_payload())
        self.assertEqual(code, 0)

    def test_diary_written_in_the_same_second_as_the_decision_counts(self):
        # Filesystem mtime granularity is not guaranteed finer than 1s, so a
        # strict float compare intermittently called a diary written
        # milliseconds AFTER the flag "older" and blocked correct work — the
        # fast path, since /decide writes the diary in the same turn. Repeated
        # because the original bug was timing-dependent and passed ~7 runs in 8.
        for i in range(25):
            MOD.save_pending({"flags": {}, "first_flag_ts": None})
            path = MOD.diary_path()
            if os.path.exists(path):
                os.unlink(path)
            MOD.set_flag("decision", f"call {i}")
            self.touch_diary()
            code, _, err = run_hook(MOD, self.commit_payload())
            self.assertEqual(code, 0, f"blocked on iteration {i}: {err}")

    def test_diary_older_than_the_decision_still_blocks(self):
        # An entry written BEFORE the decision does not record it.
        self.touch_diary(when=time.time() - 3600)
        MOD.set_flag("decision", "chose X over Y")
        code, _, _ = run_hook(MOD, self.commit_payload())
        self.assertEqual(code, 2)

    def test_code_change_alone_never_blocks_a_commit(self):
        # Ordinary commits must not be interrupted — code_change rides to Stop.
        MOD.set_flag("code_change", "src/app.py")
        code, _, _ = run_hook(MOD, self.commit_payload())
        self.assertEqual(code, 0)

    def test_non_commit_bash_commands_pass_through(self):
        MOD.set_flag("decision", "chose X over Y")
        for cmd in ("git status", "git add -A", "ls",
                    # `git commit` as an ARGUMENT is not a commit — this hook
                    # blocks, so a loose substring match would wedge unrelated
                    # commands.
                    "echo git commit", "grep -n 'git commit' notes.md"):
            code, _, _ = run_hook(MOD, self.commit_payload(cmd))
            self.assertEqual(code, 0, cmd)

    def test_commit_after_a_command_separator_is_caught(self):
        MOD.set_flag("decision", "chose X over Y")
        for cmd in ("git add -A && git commit -m 'x'",
                    "cd sub; git commit -m 'x'",
                    "git add -A\ngit commit -m 'x'"):
            code, _, _ = run_hook(MOD, self.commit_payload(cmd))
            self.assertEqual(code, 2, cmd)

    def test_git_dash_c_commit_form_is_caught(self):
        MOD.set_flag("discussion", "rejected approach B")
        code, _, _ = run_hook(MOD, self.commit_payload("git -C /repo commit -m 'x'"))
        self.assertEqual(code, 2)

    def test_no_flags_means_no_gate(self):
        code, _, _ = run_hook(MOD, self.commit_payload())
        self.assertEqual(code, 0)

    def test_diary_disabled_skips_the_gate(self):
        kit = make_kit(diary=False)
        kit["diary_scope"] = "branch"
        with _support.patched(MOD, load_kit=lambda force_reload=False: kit):
            MOD.set_flag("decision", "chose X over Y")
            code, _, _ = run_hook(MOD, self.commit_payload())
            self.assertEqual(code, 0)


class DiaryPathCliTest(DiaryScopeTestBase):
    def test_diary_path_is_reported_repo_relative(self):
        rel = os.path.relpath(MOD.diary_path(), self.tmp)
        self.assertEqual(rel, f".memory/diary/{TODAY}-fix-hygiene-findings-trio.md")


if __name__ == "__main__":
    unittest.main()
