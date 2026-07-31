#!/usr/bin/env python3
"""Tests for the daemon's stale-hooks detection.

Contract (2026-07-31 finding: a daemon up since before a kit update kept
enforcing the OLD guard_protected_merge and wrongly blocked a feature-branch
rebase):

  - hooks_signature() fingerprints every *.py in HOOKS_DIR, including
    _-prefixed internals — a hook's behavior changes when _constants.py does.
  - handle_request() answers `{"exit_code": 2, "stdout": "Stale daemon: ..."}`
    and signals shutdown when the on-disk signature no longer matches what the
    process imported. _client.py treats that reply as a fall-back signal
    (never as a hook block), so the current on-disk code runs via direct exec.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

DAEMON_PATH = os.path.join(_support.HOOKS_DIR, "_daemon.py")
MOD = _support.load_hook("_daemon")


class HooksSignatureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._orig_dir = MOD.HOOKS_DIR
        MOD.HOOKS_DIR = self.tmp
        self.addCleanup(setattr, MOD, "HOOKS_DIR", self._orig_dir)

    def write(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_signature_stable_when_nothing_changes(self):
        self.write("guard_x.py", "def main():\n    pass\n")
        self.assertEqual(MOD.hooks_signature(), MOD.hooks_signature())

    def test_signature_changes_when_hook_content_changes(self):
        path = self.write("guard_x.py", "def main():\n    pass\n")
        before = MOD.hooks_signature()
        # Content of a different size => size component alone proves the change,
        # independent of mtime granularity.
        with open(path, "w") as f:
            f.write("def main():\n    raise SystemExit(2)\n")
        self.assertNotEqual(MOD.hooks_signature(), before)

    def test_signature_tracks_underscore_internals(self):
        # _constants.py is not a hook module, but every hook's behavior depends
        # on it — an update that only changes it must still invalidate.
        self.write("guard_x.py", "def main():\n    pass\n")
        const = self.write("_constants.py", "BLOCKING_HOOKS = ()\n")
        before = MOD.hooks_signature()
        with open(const, "w") as f:
            f.write("BLOCKING_HOOKS = ('guard_x',)\n")
        self.assertNotEqual(MOD.hooks_signature(), before)

    def test_signature_changes_when_hook_added_or_removed(self):
        self.write("guard_x.py", "def main():\n    pass\n")
        before = MOD.hooks_signature()
        added = self.write("guard_y.py", "def main():\n    pass\n")
        self.assertNotEqual(MOD.hooks_signature(), before)
        os.unlink(added)
        self.assertEqual(MOD.hooks_signature(), before)


class StaleRequestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        MOD.HOOKS_DIR = self.tmp
        self.addCleanup(setattr, MOD, "HOOKS_DIR", os.path.dirname(DAEMON_PATH))

        self.calls = []
        self._orig_hooks = MOD.loaded_hooks
        self._orig_sig = MOD.loaded_signature
        MOD.loaded_hooks = {"guard_x": lambda: self.calls.append("ran")}
        self.addCleanup(setattr, MOD, "loaded_hooks", self._orig_hooks)
        self.addCleanup(setattr, MOD, "loaded_signature", self._orig_sig)
        MOD.stale_shutdown.clear()
        self.addCleanup(MOD.stale_shutdown.clear)

        self.hook_path = os.path.join(self.tmp, "guard_x.py")
        with open(self.hook_path, "w") as f:
            f.write("def main():\n    pass\n")
        MOD.loaded_signature = MOD.hooks_signature()

    def request(self):
        return MOD.handle_request(json.dumps({"hook": "guard_x", "payload": {}}))

    def test_fresh_daemon_runs_the_hook(self):
        resp = json.loads(self.request())
        self.assertEqual(resp["exit_code"], 0)
        self.assertEqual(self.calls, ["ran"])
        self.assertFalse(MOD.stale_shutdown.is_set())

    def test_changed_hooks_yield_stale_reply_and_shutdown(self):
        with open(self.hook_path, "w") as f:
            f.write("def main():\n    raise SystemExit(2)  # new rules\n")
        resp = json.loads(self.request())
        self.assertEqual(resp["exit_code"], 2)
        self.assertTrue(resp["stdout"].startswith("Stale daemon:"))
        # The stale daemon must NOT run its outdated hook code.
        self.assertEqual(self.calls, [])
        self.assertTrue(MOD.stale_shutdown.is_set())

    def test_stale_prefix_is_distinct_from_unknown_hook(self):
        # _client.py branches on these two prefixes separately; neither may be
        # mistaken for a real hook block (exit 2 from hook logic).
        resp = json.loads(MOD.handle_request(json.dumps({"hook": "nope", "payload": {}})))
        self.assertTrue(resp["stdout"].startswith("Unknown hook:"))
        self.assertFalse(resp["stdout"].startswith("Stale daemon:"))

    def test_no_signature_recorded_skips_the_check(self):
        # A daemon that never captured a signature (defensive default) must
        # keep serving rather than declaring itself stale on every call.
        MOD.loaded_signature = None
        with open(self.hook_path, "w") as f:
            f.write("def main():\n    pass  # changed\n")
        resp = json.loads(self.request())
        self.assertEqual(resp["exit_code"], 0)
        self.assertEqual(self.calls, ["ran"])


class RetireEndpointTest(unittest.TestCase):
    """retire_endpoint() must free the socket/PID file so a successor can boot
    (cmd_start refuses while a live PID file exists) — but never delete an
    endpoint a successor already owns."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sock = os.path.join(self.tmp, ".daemon.sock")
        self.pid = os.path.join(self.tmp, ".daemon.pid")
        for attr, val in (("SOCKET_PATH", self.sock), ("PID_FILE", self.pid)):
            self.addCleanup(setattr, MOD, attr, getattr(MOD, attr))
            setattr(MOD, attr, val)

    def make_endpoint(self, owner_pid):
        open(self.sock, "w").close()
        with open(self.pid, "w") as f:
            f.write(str(owner_pid))

    def test_owner_retires_its_own_endpoint(self):
        self.make_endpoint(os.getpid())
        MOD.retire_endpoint()
        self.assertFalse(os.path.exists(self.sock))
        self.assertFalse(os.path.exists(self.pid))

    def test_does_not_delete_a_successors_endpoint(self):
        # A successor booted and claimed the endpoint; the retiring daemon's
        # later shutdown must leave it intact.
        self.make_endpoint(os.getpid() + 1)
        MOD.retire_endpoint()
        self.assertTrue(os.path.exists(self.sock))
        self.assertTrue(os.path.exists(self.pid))

    def test_idempotent_when_already_retired(self):
        self.make_endpoint(os.getpid())
        MOD.retire_endpoint()
        MOD.retire_endpoint()  # must not raise
        self.assertFalse(os.path.exists(self.pid))

    def test_tolerates_corrupt_pid_file(self):
        open(self.sock, "w").close()
        with open(self.pid, "w") as f:
            f.write("not-a-pid")
        MOD.retire_endpoint()  # must not raise
        self.assertTrue(os.path.exists(self.sock))


if __name__ == "__main__":
    unittest.main()
