#!/usr/bin/env python3
"""tools/bootstrap-machine.sh: the GitHub SSH step passes on GitHub's greeting,
which `ssh -T` prints with exit 1, under the script's own shell options.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "bootstrap-machine.sh"
GREETING = "Hi owner! You've successfully authenticated, but GitHub does not provide shell access."
REFUSAL = "git@github.com: Permission denied (publickey)."


class VerifySshTest(unittest.TestCase):
    def setUp(self):
        self.bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.bindir, ignore_errors=True)

    def verify_ssh(self, answer, status):
        """The script's verify_ssh under its own `set` line, with an ssh that
        prints `answer` on stderr and exits `status`."""
        ssh = self.bindir / "ssh"
        ssh.write_text(f'#!/bin/sh\necho "$ANSWER" >&2\nexit {status}\n')
        ssh.chmod(0o755)
        text = SCRIPT.read_text()
        options = re.search(r"^set -.*$", text, re.M).group(0)
        function = re.search(r"^verify_ssh\(\) \{$.*?^\}$", text, re.M | re.S).group(0)
        env = {**os.environ, "PATH": f"{self.bindir}:{os.environ['PATH']}", "ANSWER": answer}
        return subprocess.run(["bash", "-c", f"{options}\n{function}\nverify_ssh"],
                              env=env, capture_output=True, text=True).returncode

    def test_a_key_github_accepts_passes_although_ssh_exits_1(self):
        self.assertEqual(self.verify_ssh(GREETING, 1), 0)

    def test_a_refused_key_fails(self):
        self.assertNotEqual(self.verify_ssh(REFUSAL, 255), 0)


if __name__ == "__main__":
    unittest.main()
