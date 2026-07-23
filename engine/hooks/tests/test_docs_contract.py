#!/usr/bin/env python3
"""Tests for docs_contract flag lifecycle — written against the SPEC contract:

  - PostToolUse Edit|Write on a file matching kit.json source_patterns records
    a pending "code_change" flag in .memory/cache/pending.json.
  - Stop blocks (JSON {"decision": "block", ...} on stdout) while a pending
    flag's roster file (code_change -> CHANGELOG.md) is older than the flag,
    and — when kit.diary is true — until today's diary entry exists and was
    touched after the session's first flag.
  - Satisfied flags are cleared; stop_hook_active is a loop-guard (never
    block when true).

Skipped automatically until engine-core's docs_contract.py lands.
"""
import contextlib
import datetime
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import make_kit, run_hook

DOCS_CONTRACT_PATH = os.path.join(_support.HOOKS_DIR, "docs_contract.py")
HAVE_MODULE = os.path.exists(DOCS_CONTRACT_PATH)

if HAVE_MODULE:
    MOD = _support.load_hook("docs_contract")
else:
    MOD = None

TEST_KIT = make_kit(source_patterns=[r"src/.*\.py$"], diary=True)

# Module attributes we re-point at the temp repo when the module defines them.
DIR_ATTRS = {
    "PROJECT_ROOT": "",
    "MEMORY_DIR": ".memory",
    "CACHE_DIR": ".memory/cache",
}
FILE_ATTRS = {
    "PENDING_FILE": ".memory/cache/pending.json",
    "PENDING_PATH": ".memory/cache/pending.json",
    "PENDING_JSON": ".memory/cache/pending.json",
}


@unittest.skipUnless(HAVE_MODULE, "docs_contract.py not present yet (engine-core)")
class DocsContractLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-docs-contract-")
        self.memory = os.path.join(self.tmp, ".memory")
        self.cache = os.path.join(self.memory, "cache")
        self.diary_dir = os.path.join(self.memory, "diary")
        os.makedirs(self.cache)
        os.makedirs(self.diary_dir)

        self.changelog = os.path.join(self.memory, "CHANGELOG.md")
        self.decisions = os.path.join(self.memory, "DECISIONS.md")
        past = time.time() - 3600
        for roster in (self.changelog, self.decisions):
            with open(roster, "w", encoding="utf-8") as f:
                f.write("# roster\n")
            os.utime(roster, (past, past))

        self._stack = contextlib.ExitStack()
        attrs = {}
        for attr, rel in {**DIR_ATTRS, **FILE_ATTRS}.items():
            if hasattr(MOD, attr):
                attrs[attr] = os.path.join(self.tmp, rel) if rel else self.tmp
        if hasattr(MOD, "load_kit"):
            attrs["load_kit"] = lambda force_reload=False: TEST_KIT
        self._stack.enter_context(_support.patched(MOD, **attrs))
        self.addCleanup(self._stack.close)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    # -- helpers ----------------------------------------------------------

    def _post_edit(self, rel_path="src/app.py"):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": os.path.join(self.tmp, rel_path)},
            "session_id": "test-session",
            "cwd": self.tmp,
        }
        return run_hook(MOD, payload)

    def _stop(self, stop_hook_active=False):
        payload = {
            "hook_event_name": "Stop",
            "stop_hook_active": stop_hook_active,
            "session_id": "test-session",
            "cwd": self.tmp,
        }
        return run_hook(MOD, payload)

    def _pending_text(self):
        pending = os.path.join(self.cache, "pending.json")
        if not os.path.exists(pending):
            return ""
        with open(pending, "r", encoding="utf-8") as f:
            return f.read()

    def _stop_blocks(self, stdout):
        stripped = stdout.strip()
        if not stripped:
            return False
        try:
            data = json.loads(stripped)
        except ValueError:
            return '"decision"' in stripped and '"block"' in stripped
        return data.get("decision") == "block"

    def _satisfy_roster(self):
        future = time.time() + 100
        with open(self.changelog, "a", encoding="utf-8") as f:
            f.write("- change documented\n")
        os.utime(self.changelog, (future, future))
        today = datetime.date.today().strftime("%Y-%m-%d")
        diary = os.path.join(self.diary_dir, f"{today}.md")
        with open(diary, "w", encoding="utf-8") as f:
            f.write("# diary\n")
        os.utime(diary, (future, future))

    # -- tests --------------------------------------------------------------

    def test_source_edit_records_code_change_flag(self):
        code, _out, err = self._post_edit("src/app.py")
        self.assertEqual(code, 0, err)
        self.assertIn("code_change", self._pending_text())

    def test_non_source_edit_records_no_flag(self):
        code, _out, _err = self._post_edit("docs/notes.txt")
        self.assertEqual(code, 0)
        self.assertNotIn("code_change", self._pending_text())

    def test_stop_blocks_while_changelog_stale(self):
        self._post_edit("src/app.py")
        code, out, _err = self._stop()
        self.assertEqual(code, 0)  # Stop-gate blocks via JSON decision, not exit code
        self.assertTrue(self._stop_blocks(out),
                        f"expected block decision on stdout, got: {out!r}")

    def test_stop_allows_after_roster_and_diary_updated(self):
        self._post_edit("src/app.py")
        self._satisfy_roster()
        code, out, err = self._stop()
        self.assertEqual(code, 0, err)
        self.assertFalse(self._stop_blocks(out), f"should not block, got: {out!r}")

    def test_satisfied_flags_are_cleared(self):
        self._post_edit("src/app.py")
        self._satisfy_roster()
        self._stop()
        self.assertNotIn("code_change", self._pending_text())

    def test_stop_hook_active_loop_guard_never_blocks(self):
        self._post_edit("src/app.py")
        code, out, _err = self._stop(stop_hook_active=True)
        self.assertEqual(code, 0)
        self.assertFalse(self._stop_blocks(out), "loop-guard must prevent re-blocking")

    def test_stop_without_pending_flags_is_silent(self):
        code, out, _err = self._stop()
        self.assertEqual(code, 0)
        self.assertFalse(self._stop_blocks(out))


if __name__ == "__main__":
    unittest.main()
