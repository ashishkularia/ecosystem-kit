#!/usr/bin/env python3
"""_client.py: a hook that dies before its own guard can answer (a syntax error,
an exception at import) still gets the fail-open/fail-closed policy. Claude Code
reads exit 1 as a non-blocking error and runs the tool, so a blocking hook in
that state must exit 2; an advisory one must not block.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

BROKEN = {
    "a syntax error": "def broken(:\n",
    "an exception at import": "raise RuntimeError('broken at import')\n",
}


class HookThatCannotStartTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        self.hooks = os.path.join(root, ".claude", "hooks")
        os.makedirs(self.hooks)
        for name in ("_client.py", "_constants.py"):
            shutil.copy(os.path.join(_support.HOOKS_DIR, name), self.hooks)
        # A fresh auto-start attempt keeps the client from spawning a daemon here.
        open(os.path.join(self.hooks, ".daemon.start_attempt"), "w").close()

    def run_hook(self, name, source):
        with open(os.path.join(self.hooks, f"{name}.py"), "w") as f:
            f.write(source)
        return subprocess.run(
            [sys.executable, os.path.join(self.hooks, "_client.py"), name],
            input=json.dumps({"tool_name": "Write", "tool_input": {}}),
            capture_output=True, text=True, timeout=30)

    def test_a_blocking_hook_that_cannot_start_blocks(self):
        for how, source in BROKEN.items():
            with self.subTest(how):
                result = self.run_hook("secret_scanner", source)
                self.assertEqual(result.returncode, 2)
                self.assertIn("secret_scanner: hook exited 1 before answering", result.stderr)

    def test_an_advisory_hook_that_cannot_start_does_not_block(self):
        for how, source in BROKEN.items():
            with self.subTest(how):
                result = self.run_hook("context_attach", source)
                self.assertNotEqual(result.returncode, 2)
                self.assertTrue(result.stderr)


if __name__ == "__main__":
    unittest.main()
