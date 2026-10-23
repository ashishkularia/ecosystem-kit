#!/usr/bin/env python3
"""tools/vault-sync: the vault copy follows the default branch, skips what
Obsidian or the phone has no use for, and never loses an edit made in the vault.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[3] / "tools" / "vault-sync"


def load_tool():
    loader = importlib.machinery.SourceFileLoader("vault_sync", str(TOOL))
    spec = importlib.util.spec_from_loader("vault_sync", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


class VaultSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.vs = load_tool()
        home = self.tmp / "home"
        (home / ".claude").mkdir(parents=True)
        self.vault = self.tmp / "vault"
        self.vault.mkdir()
        self.vs.REGISTRY = home / ".claude" / "repo-registry"
        self.vs.VAULT_FILE = home / ".claude" / "vault-dir"
        self.vs.STATE_DIR = home / ".claude" / "vault-sync"
        self.vs.LOG = home / ".claude" / "vault-sync.log"
        self.vs.VAULT_FILE.write_text(f"{self.vault}\n")

        origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        self.repo = self.tmp / "proj"
        subprocess.run(["git", "clone", "-q", str(origin), str(self.repo)],
                       check=True, capture_output=True)
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        self.write({
            "README.md": "readme\n",
            "docs/guide.md": "guide\n",
            ".memory/STATE.md": "state\n",
            ".memory/diary/2026-10-23-x.md": "diary\n",
            ".memory/auto/note.md": "memory\n",
            ".memory/cache/c.md": "cache\n",
            ".github/pull_request_template.md": "tpl\n",
            "vendor/pkg/README.md": "vendored\n",
            "app.php": "<?php\n",
        })
        self.commit_push("init")
        git(self.repo, "remote", "set-head", "origin", "-a")
        self.vs.REGISTRY.write_text(f"{self.repo}\n")
        self.project = self.vault / "Projects" / "proj"

    def write(self, files):
        for rel, text in files.items():
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)

    def commit_push(self, msg):
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", msg)
        git(self.repo, "push", "-q", "origin", "HEAD:main")

    def run_tool(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = self.vs.main(list(argv))
        return code, out.getvalue()

    def copied(self):
        root = self.project / "Repo"
        return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())

    def test_copies_docs_and_maps_dot_memory(self):
        code, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(self.copied(), [
            "README.md", "docs/guide.md",
            "memory/STATE.md", "memory/diary/2026-10-23-x.md",
        ])
        self.assertTrue((self.project / "Inbox").is_dir())
        self.assertTrue((self.vault / "Projects" / self.vs.GUIDE_NAME).exists())

    def test_follows_default_branch_not_the_checkout(self):
        git(self.repo, "checkout", "-q", "-b", "feature/x")
        self.write({"docs/wip.md": "wip\n", "README.md": "changed on a branch\n"})
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "wip")
        self.run_tool()
        self.assertNotIn("docs/wip.md", self.copied())
        self.assertEqual((self.project / "Repo" / "README.md").read_text(), "readme\n")

    def test_vault_edit_moves_to_inbox_and_copy_is_restored(self):
        self.run_tool()
        state = self.project / "Repo" / "memory" / "STATE.md"
        state.write_text("edited on the phone\n")
        _, out = self.run_tool()
        self.assertIn("vault edit", out)
        self.assertEqual(state.read_text(), "state\n")
        rescued = list((self.project / "Inbox").glob("memory - STATE (edited *).md"))
        self.assertEqual(len(rescued), 1)
        body = rescued[0].read_text()
        self.assertIn("`.memory/STATE.md` (proj)", body)
        self.assertTrue(body.endswith("edited on the phone\n"))

    def test_second_edit_same_day_gets_its_own_inbox_note(self):
        self.run_tool()
        state = self.project / "Repo" / "memory" / "STATE.md"
        for text in ("first\n", "second\n"):
            state.write_text(text)
            self.run_tool()
        self.assertEqual(len(list((self.project / "Inbox").glob("memory - STATE*"))), 2)

    def test_upstream_change_overwrites_an_unedited_copy(self):
        self.run_tool()
        self.write({"docs/guide.md": "guide v2\n"})
        self.commit_push("v2")
        self.run_tool()
        self.assertEqual((self.project / "Repo" / "docs" / "guide.md").read_text(), "guide v2\n")
        self.assertEqual(list((self.project / "Inbox").iterdir()), [])

    def test_file_removed_from_repo(self):
        self.run_tool()
        (self.project / "Repo" / "README.md").write_text("my notes\n")
        git(self.repo, "rm", "-q", "README.md", "docs/guide.md")
        git(self.repo, "commit", "-q", "-m", "rm")
        git(self.repo, "push", "-q", "origin", "HEAD:main")
        self.run_tool()
        self.assertNotIn("README.md", self.copied())
        self.assertFalse((self.project / "Repo" / "docs").exists())
        self.assertEqual(len(list((self.project / "Inbox").glob("README (edited *).md"))), 1)

    def test_frontmatter_stays_first_in_inbox_note(self):
        self.write({"docs/fm.md": "---\ntitle: x\n---\nbody\n"})
        self.commit_push("fm")
        self.run_tool()
        (self.project / "Repo" / "docs" / "fm.md").write_text("---\ntitle: x\n---\nnew body\n")
        self.run_tool()
        note = next((self.project / "Inbox").glob("docs - fm*")).read_text()
        self.assertTrue(note.startswith("---\ntitle: x\n---\n"))
        self.assertIn("[!note]", note)

    def test_check_writes_nothing(self):
        code, out = self.run_tool("check")
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertFalse((self.vault / "Projects").exists())

    def test_no_vault_is_a_noop(self):
        self.vs.VAULT_FILE.unlink()
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIn("no vault", out)
        self.assertFalse((self.vault / "Projects").exists())

    def test_adopt_memory(self):
        settings = self.repo / ".claude" / "settings.local.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({
            "autoMemoryDirectory": str(self.repo / ".memory" / "auto"),
            "permissions": {"allow": ["Bash(ls)"]},
        }))
        (self.repo / ".memory" / "auto" / "local-only.md").write_text("untracked\n")
        target = self.project / self.vs.MEMORY_FOLDER

        _, out = self.run_tool("adopt-memory", "proj", "check")
        self.assertIn("dry run", out)
        self.assertFalse(target.exists())

        self.run_tool("adopt-memory", "proj")
        self.assertEqual((target / "note.md").read_text(), "memory\n")
        self.assertEqual((target / "local-only.md").read_text(), "untracked\n")
        self.assertTrue((self.repo / ".memory" / "auto" / "note.md").exists(),
                        "a tracked note is left for the repo's git rm PR")
        self.assertFalse((self.repo / ".memory" / "auto" / "local-only.md").exists())
        data = json.loads(settings.read_text())
        self.assertEqual(data["autoMemoryDirectory"], str(target))
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})

        _, out = self.run_tool("adopt-memory", "proj")
        self.assertIn("already adopted", out)

    def test_adopt_memory_needs_a_name_and_skips_other_repos(self):
        code, out = self.run_tool("adopt-memory")
        self.assertEqual(code, 2)
        self.assertIn("needs a repo directory name", out)
        code, out = self.run_tool("adopt-memory", "nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown repo(s): nope", out)
        self.assertFalse((self.project / self.vs.MEMORY_FOLDER).exists())
        code, _ = self.run_tool("adopt-memory", "all")
        self.assertEqual(code, 0)
        self.assertTrue((self.project / self.vs.MEMORY_FOLDER / "note.md").exists())

    def test_adopt_memory_keeps_both_on_conflict(self):
        target = self.project / self.vs.MEMORY_FOLDER
        target.mkdir(parents=True)
        (target / "note.md").write_text("vault version\n")
        self.run_tool("adopt-memory", "proj")
        self.assertEqual((target / "note.md").read_text(), "vault version\n")
        self.assertEqual((target / "note (repo copy).md").read_text(), "memory\n")


if __name__ == "__main__":
    unittest.main()
