#!/usr/bin/env python3
"""session_boot's vault section: names the project's vault folder and its
waiting Inbox notes, and stays silent on a machine without a vault."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

MOD = _support.load_hook("session_boot")


class VaultSectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.vault = os.path.join(self.tmp, "vault")
        self.folder = os.path.join(self.vault, "Projects", "proj")
        self.vault_file = os.path.join(self.tmp, "vault-dir")
        with open(self.vault_file, "w") as f:
            f.write(self.vault + "\n")
        self.patch("VAULT_FILE", self.vault_file)
        self.patch("PROJECT_ROOT", os.path.join(self.tmp, "repos", "proj"))

    def patch(self, name, value):
        old = getattr(MOD, name)
        setattr(MOD, name, value)
        self.addCleanup(setattr, MOD, name, old)

    def text(self):
        return "\n".join(MOD.vault_section())

    def test_no_vault_file(self):
        os.unlink(self.vault_file)
        self.assertEqual(MOD.vault_section(), [])

    def test_no_project_folder(self):
        os.makedirs(self.vault)
        self.assertEqual(MOD.vault_section(), [])

    def test_empty_inbox(self):
        os.makedirs(os.path.join(self.folder, "Inbox", "Done"))
        out = self.text()
        self.assertIn(f"## Obsidian vault: {self.folder}", out)
        self.assertIn("Inbox: empty.", out)

    def test_lists_waiting_notes_but_not_done_ones(self):
        inbox = os.path.join(self.folder, "Inbox")
        os.makedirs(os.path.join(inbox, "Done"))
        for name in ("b request.md", "a request.md", "Done/old.md", "image.png"):
            open(os.path.join(inbox, name), "w").close()
        out = self.text()
        self.assertIn("Inbox: 2 note(s)", out)
        self.assertLess(out.index("a request.md"), out.index("b request.md"))
        self.assertNotIn("old.md", out)
        self.assertNotIn("image.png", out)
        self.assertIn("act on one only when asked", out)


if __name__ == "__main__":
    unittest.main()
