#!/usr/bin/env python3
"""tools/prune-stale-branches: a squash-merged branch goes once a merged PR
carried its tip, whatever upstream it tracks; a commit after that keeps it.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOL = Path(__file__).resolve().parents[3] / "tools" / "prune-stale-branches"


def load_tool():
    loader = importlib.machinery.SourceFileLoader("prune_stale_branches", str(TOOL))
    spec = importlib.util.spec_from_loader("prune_stale_branches", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class SquashMergedBranchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "proj"
        self.psb = load_tool()
        self.psb.REGISTRY = self.tmp / "repo-registry"
        self.psb.REGISTRY.write_text(f"{self.repo}\n")
        self.psb.TOKEN_FILE = self.tmp / "github-pat"
        self.psb.TOKEN_FILE.write_text("token\n")
        self.psb.LOG = self.tmp / "prune-branches.log"
        self.psb.repo_coords = lambda repo: ("owner", "proj")
        self.psb.merged_pr_heads = lambda owner, repo, branch, tok: self.merged_heads

        origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        subprocess.run(["git", "clone", "-q", str(origin), str(self.repo)],
                       check=True, capture_output=True)
        git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        self.commit("README.md")
        git(self.repo, "push", "-q", "origin", "HEAD:main")

        # Made from origin/main, so the push leaves origin/main as its upstream.
        git(self.repo, "switch", "-q", "-c", "fix/thing", "--track", "origin/main")
        self.commit("thing.txt")
        git(self.repo, "push", "-q", "origin", "fix/thing")
        self.merged_heads = {git(self.repo, "rev-parse", "fix/thing")}

        # GitHub's squash merge: one new commit on main with the branch's tree.
        git(self.repo, "switch", "-q", "main")
        git(self.repo, "merge", "-q", "--squash", "fix/thing")
        git(self.repo, "commit", "-q", "-m", "fix: thing (#1)")
        git(self.repo, "push", "-q", "origin", "HEAD:main")

    def commit(self, name):
        (self.repo / name).write_text(f"{name}\n")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", f"add {name}")

    def prune(self):
        with mock.patch.object(sys, "argv", ["prune-stale-branches"]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.psb.main()
        return out.getvalue()

    def branches(self):
        return git(self.repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()

    def test_deletes_a_squash_merged_branch_that_tracks_the_default(self):
        track = git(self.repo, "for-each-ref", "--format=%(upstream:track)", "refs/heads/fix/thing")
        self.assertIn("ahead 1", track)

        self.prune()

        self.assertNotIn("fix/thing", self.branches())

    def test_keeps_a_branch_with_a_commit_after_its_merged_head(self):
        git(self.repo, "switch", "-q", "fix/thing")
        self.commit("more.txt")
        git(self.repo, "switch", "-q", "main")

        out = self.prune()

        self.assertIn("fix/thing", self.branches())
        self.assertIn("keep (commits after its merged PR): fix/thing", out)

    def test_keeps_a_commit_after_the_merge_once_its_remote_branch_is_gone(self):
        git(self.repo, "switch", "-q", "fix/thing")
        git(self.repo, "branch", "-q", "-u", "origin/fix/thing")
        self.commit("more.txt")
        git(self.repo, "switch", "-q", "main")
        git(self.repo, "push", "-q", "origin", "--delete", "fix/thing")
        git(self.repo, "fetch", "-q", "--prune")
        track = git(self.repo, "for-each-ref", "--format=%(upstream:track)", "refs/heads/fix/thing")
        self.assertEqual("[gone]", track)

        self.prune()

        self.assertIn("fix/thing", self.branches())


if __name__ == "__main__":
    unittest.main()
