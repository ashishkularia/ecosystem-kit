#!/usr/bin/env python3
"""Tests for the repo-local scratch exemption.

Scratch work lives in `<repo>/.claude/scratch/`, never in /tmp. That puts
throwaway scripts INSIDE the repo, where the "is this source?" gates would
otherwise treat them as real changes: docs_contract would demand a CHANGELOG
and diary entry for a one-off helper, and tdd_gate (enforce) would block it for
want of a test. `_constants.is_scratch_path` is the one predicate both gates
share, so the boundary is defined once.

Every gate test carries controls — a real source file and a lookalike
`.claude/scratchy/` directory must STILL count as source — so a predicate that
over-matches fails here instead of silently disabling the gates.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import make_kit, run_hook, write_payload

CONSTANTS = _support.load_hook("_constants")
DOCS_CONTRACT = _support.load_hook("docs_contract")
TDD_GATE = _support.load_hook("tdd_gate")

SESSION = "scratch-session"
SCRATCH_FILE = ".claude/scratch/probe.py"
LOOKALIKE_FILE = ".claude/scratchy/probe.py"
SOURCE_FILE = "src/app.py"


class IsScratchPathTest(unittest.TestCase):
    def test_files_under_scratch_are_scratch(self):
        for rel in (".claude/scratch/a.py", ".claude/scratch/sub/dir/b.sh",
                    ".claude/scratch/.gitignore"):
            self.assertTrue(CONSTANTS.is_scratch_path(rel), rel)

    def test_sibling_with_shared_prefix_is_not_scratch(self):
        for rel in (".claude/scratchy/a.py", ".claude/scratch.py"):
            self.assertFalse(CONSTANTS.is_scratch_path(rel), rel)

    def test_other_claude_paths_are_not_scratch(self):
        for rel in (".claude/hooks/x.py", ".claude/settings.json", ".claude/kit.json"):
            self.assertFalse(CONSTANTS.is_scratch_path(rel), rel)

    def test_scratch_is_only_at_the_repo_root(self):
        # A nested `.claude/scratch` is somebody's source tree, not ours.
        for rel in ("docs/.claude/scratch/a.py", "src/.claude/scratch/a.py"):
            self.assertFalse(CONSTANTS.is_scratch_path(rel), rel)


class _TempRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-scratch-")
        self.cache = os.path.join(self.tmp, ".memory", "cache")
        os.makedirs(self.cache)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def abs(self, rel):
        return os.path.join(self.tmp, rel)


class DocsContractScratchTest(_TempRepo):
    def setUp(self):
        super().setUp()
        # Unanchored on purpose: the dangerous kind of profile regex.
        kit = make_kit(source_patterns=[r"\.py$"], diary=True)
        attrs = {
            "PROJECT_ROOT": self.tmp,
            "MEMORY_DIR": os.path.join(self.tmp, ".memory"),
            "load_kit": lambda force_reload=False: kit,
        }
        if hasattr(DOCS_CONTRACT, "CACHE_DIR"):
            attrs["CACHE_DIR"] = self.cache
        patch = _support.patched(DOCS_CONTRACT, **attrs)
        patch.__enter__()
        self.addCleanup(patch.__exit__, None, None, None)

    def _post_edit(self, rel):
        return run_hook(DOCS_CONTRACT, {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": self.abs(rel)},
            "session_id": SESSION,
            "cwd": self.tmp,
        })

    def _flagged(self):
        pending = os.path.join(self.cache, "pending", f"{SESSION}.json")
        if not os.path.exists(pending):
            return False
        with open(pending, encoding="utf-8") as f:
            return "code_change" in json.load(f).get("flags", {})

    def test_scratch_script_never_raises_a_code_change_flag(self):
        code, out, _err = self._post_edit(SCRATCH_FILE)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertFalse(self._flagged())

    def test_real_source_still_flags(self):
        self._post_edit(SOURCE_FILE)
        self.assertTrue(self._flagged())

    def test_lookalike_directory_still_flags(self):
        self._post_edit(LOOKALIKE_FILE)
        self.assertTrue(self._flagged())


class TddGateScratchTest(_TempRepo):
    def setUp(self):
        super().setUp()
        # No source_patterns: forces the extension fallback, which would match
        # any scratch .py. tdd=enforce makes a false match a hard block.
        kit = make_kit(source_patterns=[], principles={"tdd": "enforce"})
        patch = _support.patched(
            TDD_GATE,
            PROJECT_ROOT=self.tmp,
            MEMORY_DIR=os.path.join(self.tmp, ".memory"),
            load_kit=lambda force_reload=False: kit,
        )
        patch.__enter__()
        self.addCleanup(patch.__exit__, None, None, None)

    def _write(self, rel):
        return run_hook(TDD_GATE, write_payload(
            self.abs(rel), "x = 1\n", session_id=SESSION))[0]

    def test_scratch_script_is_never_blocked(self):
        self.assertEqual(self._write(SCRATCH_FILE), 0)

    def test_real_source_is_still_blocked_without_a_test_edit(self):
        self.assertEqual(self._write(SOURCE_FILE), 2)

    def test_lookalike_directory_is_still_blocked(self):
        self.assertEqual(self._write(LOOKALIKE_FILE), 2)

    def test_scratch_test_file_does_not_unlock_source_edits(self):
        # A throwaway test_*.py in scratch is not a real test edit; counting it
        # would let any session dodge enforce by scribbling one in scratch.
        self.assertEqual(self._write(".claude/scratch/test_probe.py"), 0)
        self.assertEqual(self._write(SOURCE_FILE), 2)


if __name__ == "__main__":
    unittest.main()
