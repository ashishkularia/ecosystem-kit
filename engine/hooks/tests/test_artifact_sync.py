#!/usr/bin/env python3
"""Tests for artifact_sync and its _markdown helper.

Contract:
  - Only real publishes sync. Non-publish Artifact actions (comments, list,
    asset ops) and payloads without a url/path are no-ops — a comment read
    must never create an artifact directory.
  - Idempotency is keyed on tool_response.artifact_id, NOT the filename. The
    observed real-world shape is 37 publishes across 2 artifacts republished
    from the SAME temp path, so keying on filename would still be wrong the
    moment an artifact is retitled: find_existing() must reuse the directory
    carrying the id.
  - The published source is stored VERBATIM; the counterpart is generated and
    carries a "do not edit" banner.
  - commit() is scoped: it refuses on a protected branch and never pushes.
  - Every failure path exits 0 — a publish must never be blocked by this hook.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

MOD = _support.load_hook("artifact_sync")
MD = _support.load_hook("_markdown")


def payload(path, url="https://claude.ai/code/artifact/abc-123", artifact_id="abc-123",
            title="Sample Title", updated=False, action=None, description="d"):
    tool_input = {"file_path": path, "description": description}
    if action:
        tool_input["action"] = action
    return {
        "tool_name": "Artifact",
        "hook_event_name": "PostToolUse",
        "tool_input": tool_input,
        "tool_response": {
            "url": url, "path": path, "artifact_id": artifact_id,
            "title": title, "updated": updated, "version": "1-2",
        },
    }


class SyncTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)

        self._orig_root = MOD.PROJECT_ROOT
        MOD.PROJECT_ROOT = self.repo
        self.addCleanup(setattr, MOD, "PROJECT_ROOT", self._orig_root)

        # Never touch git from the unit tests; commit() is exercised separately.
        self._orig_commit = MOD.commit
        MOD.commit = lambda paths, message, conf: "not committed (test)"
        self.addCleanup(setattr, MOD, "commit", self._orig_commit)

        self._orig_cfg = MOD.cfg
        MOD.cfg = lambda: {"enabled": True, "dir": "docs/artifacts",
                           "commit": False, "commit_type": "docs"}
        self.addCleanup(setattr, MOD, "cfg", self._orig_cfg)

    def source(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def run_hook(self, event):
        """Run main() against a payload; returns its exit code."""
        import io
        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(json.dumps(event))
        sys.stdout = io.StringIO()
        try:
            MOD.main()
        except SystemExit as e:
            return e.code
        finally:
            sys.stdin, sys.stdout = stdin, stdout
        return 0

    @property
    def artifacts_root(self):
        return os.path.join(self.repo, "docs", "artifacts")

    def dirs(self):
        root = self.artifacts_root
        if not os.path.isdir(root):
            return []
        return sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))


class PublishGatingTest(SyncTestBase):
    def test_markdown_publish_writes_source_verbatim_and_html(self):
        body = "# Hello\n\nSome **bold** text.\n"
        src = self.source("note.md", body)
        self.assertEqual(self.run_hook(payload(src)), 0)

        self.assertEqual(self.dirs(), ["sample-title"])
        d = os.path.join(self.artifacts_root, "sample-title")
        with open(os.path.join(d, "sample-title.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), body, "source must be stored byte-for-byte")
        # A markdown source IS the readable form, so its counterpart is the
        # viewable page (index.html) — see ViewablePageTest. There is no
        # separate <slug>.html, which would just duplicate it.
        with open(os.path.join(d, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("GENERATED", html)
        self.assertTrue(os.path.isfile(os.path.join(d, "artifact.json")))

    def test_html_publish_writes_source_verbatim_and_md_digest(self):
        body = "<html><head><title>T</title></head><body><h1>Head</h1><p>Body text.</p></body></html>"
        src = self.source("page.html", body)
        self.assertEqual(self.run_hook(payload(src)), 0)

        d = os.path.join(self.artifacts_root, "sample-title")
        with open(os.path.join(d, "sample-title.html"), encoding="utf-8") as f:
            self.assertEqual(f.read(), body)
        with open(os.path.join(d, "sample-title.md"), encoding="utf-8") as f:
            md = f.read()
        self.assertIn("# Sample Title", md)
        self.assertIn("Body text.", md)
        self.assertIn("lossy", md.lower())

    def test_non_publish_actions_are_noops(self):
        src = self.source("note.md", "# x\n")
        for action in ("comments", "list", "reply", "upload_asset", "resolve"):
            self.assertEqual(self.run_hook(payload(src, action=action)), 0)
        self.assertEqual(self.dirs(), [], "a non-publish action must not create a directory")

    def test_missing_url_or_file_is_noop(self):
        src = self.source("note.md", "# x\n")
        ev = payload(src)
        ev["tool_response"]["url"] = None
        self.assertEqual(self.run_hook(ev), 0)

        ev = payload(os.path.join(self.tmp, "does-not-exist.md"))
        self.assertEqual(self.run_hook(ev), 0)
        self.assertEqual(self.dirs(), [])

    def test_non_artifact_tool_is_noop(self):
        src = self.source("note.md", "# x\n")
        ev = payload(src)
        ev["tool_name"] = "Write"
        self.assertEqual(self.run_hook(ev), 0)
        self.assertEqual(self.dirs(), [])

    def test_disabled_by_config(self):
        MOD.cfg = lambda: {"enabled": False, "dir": "docs/artifacts",
                           "commit": False, "commit_type": "docs"}
        src = self.source("note.md", "# x\n")
        self.assertEqual(self.run_hook(payload(src)), 0)
        self.assertEqual(self.dirs(), [])

    def test_garbage_stdin_exits_zero(self):
        import io
        stdin, stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO("not json at all")
        sys.stdout = io.StringIO()
        try:
            MOD.main()
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            sys.stdin, sys.stdout = stdin, stdout


class IdempotencyTest(SyncTestBase):
    def test_republish_reuses_one_directory(self):
        src = self.source("note.md", "# v1\n")
        for i in range(5):
            with open(src, "w", encoding="utf-8") as f:
                f.write("# v%d\n" % i)
            self.run_hook(payload(src, updated=i > 0))
        self.assertEqual(self.dirs(), ["sample-title"], "5 republishes must yield 1 directory")
        with open(os.path.join(self.artifacts_root, "sample-title", "sample-title.md")) as f:
            self.assertEqual(f.read(), "# v4\n", "latest publish wins")

    def test_retitled_artifact_keeps_its_directory(self):
        """The id is the key — a new title must not orphan the old directory."""
        src = self.source("note.md", "# x\n")
        self.run_hook(payload(src, title="First Name"))
        self.run_hook(payload(src, title="Totally Different"))
        self.assertEqual(self.dirs(), ["first-name"])
        with open(os.path.join(self.artifacts_root, "first-name", "artifact.json")) as f:
            meta = json.load(f)
        self.assertEqual(meta["title"], "Totally Different", "metadata still updates")

    def test_distinct_artifacts_get_distinct_directories(self):
        a = self.source("a.md", "# a\n")
        b = self.source("b.md", "# b\n")
        self.run_hook(payload(a, artifact_id="id-a", title="Alpha", url="https://x/a"))
        self.run_hook(payload(b, artifact_id="id-b", title="Beta", url="https://x/b"))
        self.assertEqual(self.dirs(), ["alpha", "beta"])

    def test_same_title_different_id_does_not_collide(self):
        a = self.source("a.md", "# a\n")
        b = self.source("b.md", "# b\n")
        self.run_hook(payload(a, artifact_id="id-aaaaaaaa", title="Same", url="https://x/a"))
        self.run_hook(payload(b, artifact_id="id-bbbbbbbb", title="Same", url="https://x/b"))
        self.assertEqual(len(self.dirs()), 2, "distinct artifacts must not overwrite each other")

    def test_republish_without_description_keeps_the_old_one(self):
        """A republish carries only file_path + label; metadata must survive.

        Observed live 2026-08-27: republishing with just a label blanked the
        artifact's description in artifact.json and therefore in INDEX.md.
        """
        src = self.source("note.md", "# x\n")
        self.run_hook(payload(src, description="The original description"))

        bare = payload(src, updated=True)
        bare["tool_input"].pop("description", None)
        self.run_hook(bare)

        with open(os.path.join(self.artifacts_root, "sample-title", "artifact.json")) as f:
            meta = json.load(f)
        self.assertEqual(meta["description"], "The original description")

    def test_republish_with_new_description_overwrites(self):
        src = self.source("note.md", "# x\n")
        self.run_hook(payload(src, description="old"))
        self.run_hook(payload(src, description="new", updated=True))
        with open(os.path.join(self.artifacts_root, "sample-title", "artifact.json")) as f:
            self.assertEqual(json.load(f)["description"], "new")

    def test_index_lists_every_artifact(self):
        a = self.source("a.md", "# a\n")
        b = self.source("b.md", "# b\n")
        self.run_hook(payload(a, artifact_id="id-a", title="Alpha", url="https://x/a"))
        self.run_hook(payload(b, artifact_id="id-b", title="Beta", url="https://x/b"))
        with open(os.path.join(self.artifacts_root, "INDEX.md"), encoding="utf-8") as f:
            index = f.read()
        self.assertIn("Alpha", index)
        self.assertIn("Beta", index)


class SlugifyTest(unittest.TestCase):
    def test_slugs(self):
        self.assertEqual(MOD.slugify("Claude Code Checkup"), "claude-code-checkup")
        self.assertEqual(MOD.slugify("  Wild --- Chars!! "), "wild-chars")
        self.assertEqual(MOD.slugify(""), "artifact")
        self.assertEqual(MOD.slugify("///", fallback="fb"), "fb")
        self.assertLessEqual(len(MOD.slugify("x" * 200)), MOD.MAX_SLUG)

    def test_path_traversal_cannot_escape(self):
        """A title is untrusted text; it must never produce a path separator."""
        for evil in ("../../etc/passwd", "a/b/c", "..", "....//"):
            slug = MOD.slugify(evil)
            self.assertNotIn("/", slug)
            self.assertNotIn("\\", slug)
            self.assertNotEqual(slug, "..")


class MarkdownRenderTest(unittest.TestCase):
    def test_headings_lists_code_links(self):
        html = MD.md_to_html(
            "# H1\n\n- one\n- two\n\n`code`\n\n[label](https://example.com)\n"
        )
        self.assertIn("<h1>H1</h1>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn('<a href="https://example.com">label</a>', html)

    def test_fenced_code_is_escaped_not_executed(self):
        html = MD.md_to_html("```python\nprint('<script>')\n```\n")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_table(self):
        html = MD.md_to_html("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        self.assertIn("<th>a</th>", html)
        self.assertIn("<td>1</td>", html)

    def test_javascript_url_is_neutralised(self):
        html = MD.md_to_html("[x](javascript:alert(1))\n")
        self.assertNotIn("javascript:", html)

    def test_raw_html_in_markdown_is_escaped(self):
        html = MD.md_to_html("<img src=x onerror=alert(1)>\n")
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_html_digest_drops_script_and_style(self):
        title, md = MD.html_to_md(
            "<html><head><title>T</title><style>p{color:red}</style></head>"
            "<body><script>alert(1)</script><h2>Head</h2><p>Text.</p></body></html>"
        )
        self.assertEqual(title, "T")
        self.assertIn("## Head", md)
        self.assertIn("Text.", md)
        self.assertNotIn("alert(1)", md)
        self.assertNotIn("color:red", md)

    def test_html_digest_keeps_links(self):
        _, md = MD.html_to_md('<body><p><a href="https://e.com">site</a></p></body>')
        self.assertIn("[site](https://e.com)", md)

    def test_digest_survives_malformed_html(self):
        _, md = MD.html_to_md("<body><p>unclosed <b>bold</body>")
        self.assertIn("unclosed", md)


class CommitScopeTest(SyncTestBase):
    """commit() must refuse on protected branches and never push."""

    def setUp(self):
        super().setUp()
        # SyncTestBase stubs commit() out so the publish tests never touch git.
        # These tests are ABOUT commit(), so put the real one back.
        MOD.commit = self._orig_commit

    def _fake_git(self, branch):
        calls = []

        class R:
            def __init__(self, out="", code=0):
                self.stdout, self.stderr, self.returncode = out, "", code

        def fake(args, cwd):
            calls.append(args)
            if args[:1] == ["rev-parse"] and "--is-inside-work-tree" in args:
                return R("true")
            if args[:1] == ["rev-parse"]:
                return R(branch)
            if args[:1] == ["status"]:
                return R(" M docs/artifacts/x/x.md")
            return R("")

        return fake, calls

    def test_refuses_on_protected_branch(self):
        fake, calls = self._fake_git("main")
        self._orig_git, MOD.git = MOD.git, fake
        self.addCleanup(setattr, MOD, "git", self._orig_git)
        conf = {"commit": True, "commit_type": "docs"}
        status = MOD.commit(["docs/artifacts/x"], "docs(artifact): add x", conf)
        self.assertIn("protected branch", status)
        self.assertFalse([c for c in calls if c[:1] == ["commit"]], "must not commit")

    def test_commits_on_feature_branch_with_pathspec_and_no_push(self):
        fake, calls = self._fake_git("feature/x")
        self._orig_git, MOD.git = MOD.git, fake
        self.addCleanup(setattr, MOD, "git", self._orig_git)
        conf = {"commit": True, "commit_type": "docs"}
        status = MOD.commit(["docs/artifacts/x", "docs/artifacts/INDEX.md"],
                            "docs(artifact): add x", conf)
        self.assertIn("committed", status)
        commits = [c for c in calls if c[:1] == ["commit"]]
        self.assertEqual(len(commits), 1)
        self.assertIn("--", commits[0], "must be a pathspec commit, not a bare commit")
        self.assertIn("docs/artifacts/x", commits[0])
        self.assertFalse([c for c in calls if c[:1] == ["push"]], "must never push")

        # An artifact's first publish leaves every file untracked, and
        # `git commit -- <paths>` cannot commit what git does not know
        # (observed live 2026-08-27: "pathspec ... did not match any file(s)").
        # The paths must be staged first — and only those paths.
        adds = [c for c in calls if c[:1] == ["add"]]
        self.assertEqual(len(adds), 1, "artifact paths must be staged before commit")
        self.assertIn("--", adds[0], "git add must be pathspec-scoped")
        self.assertIn("docs/artifacts/x", adds[0])
        for blanket in ("-A", "--all", "."):
            self.assertNotIn(blanket, adds[0], "must never stage the whole tree")
        self.assertLess(calls.index(adds[0]), calls.index(commits[0]), "add must precede commit")

    def test_stage_failure_reports_and_does_not_commit(self):
        class R:
            def __init__(self, out="", code=0, err=""):
                self.stdout, self.stderr, self.returncode = out, err, code

        calls = []

        def fake(args, cwd):
            calls.append(args)
            if args[:1] == ["rev-parse"] and "--is-inside-work-tree" in args:
                return R("true")
            if args[:1] == ["rev-parse"]:
                return R("feature/x")
            if args[:1] == ["status"]:
                return R(" M docs/artifacts/x/x.md")
            if args[:1] == ["add"]:
                return R(code=1, err="fatal: pathspec did not match")
            return R("")

        self._orig_git, MOD.git = MOD.git, fake
        self.addCleanup(setattr, MOD, "git", self._orig_git)
        status = MOD.commit(["docs/artifacts/x"], "m", {"commit": True, "commit_type": "docs"})
        self.assertIn("failed at stage", status)
        self.assertFalse([c for c in calls if c[:1] == ["commit"]])

    def test_disabled_commit_is_a_noop(self):
        fake, calls = self._fake_git("feature/x")
        self._orig_git, MOD.git = MOD.git, fake
        self.addCleanup(setattr, MOD, "git", self._orig_git)
        status = MOD.commit(["docs/artifacts/x"], "m", {"commit": False, "commit_type": "docs"})
        self.assertIn("artifacts.commit is false", status)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()


class ViewablePageTest(SyncTestBase):
    """Every artifact must be openable in a browser and servable statically.

    The stored source is a FRAGMENT by contract (the artifact host supplies
    <!doctype>/<html>/<body> and rejects pages that bring their own), so the
    source alone renders in quirks mode with no viewport meta.
    """

    def test_html_artifact_gets_a_standalone_index_page(self):
        fragment = '<title>T</title><style>body{color:red}</style><h1>Head</h1><p>Body.</p>'
        src = self.source("page.html", fragment)
        self.run_hook(payload(src))
        d = os.path.join(self.artifacts_root, "sample-title")

        with open(os.path.join(d, "sample-title.html"), encoding="utf-8") as f:
            self.assertEqual(f.read(), fragment, "source stays a verbatim fragment")

        with open(os.path.join(d, "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html>"))
        for required in ("<html", "<head", "<body", 'name="viewport"'):
            self.assertIn(required, page)
        self.assertIn("<h1>Head</h1>", page, "fragment content is preserved")
        self.assertIn("body{color:red}", page, "the artifact's own styles survive")
        self.assertEqual(page.count("<title>"), 1, "exactly one title, not two")

    def test_markdown_artifact_gets_a_rendered_index_page(self):
        src = self.source("note.md", "# Hello\n\nSome **bold** text.\n")
        self.run_hook(payload(src))
        d = os.path.join(self.artifacts_root, "sample-title")
        with open(os.path.join(d, "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("<strong>bold</strong>", page)

    def test_already_complete_document_is_not_double_wrapped(self):
        full = "<!doctype html><html><head><title>X</title></head><body><p>hi</p></body></html>"
        src = self.source("page.html", full)
        self.run_hook(payload(src))
        with open(os.path.join(self.artifacts_root, "sample-title", "index.html")) as f:
            page = f.read()
        self.assertEqual(page.lower().count("<!doctype"), 1)
        self.assertEqual(page.lower().count("<html"), 1)

    def test_gallery_is_generated_and_links_each_artifact(self):
        a = self.source("a.md", "# a\n")
        b = self.source("b.html", "<title>B</title><p>b</p>")
        self.run_hook(payload(a, artifact_id="id-a", title="Alpha", url="https://x/a"))
        self.run_hook(payload(b, artifact_id="id-b", title="Beta", url="https://x/b"))

        with open(os.path.join(self.artifacts_root, "index.html"), encoding="utf-8") as f:
            gallery = f.read()
        self.assertTrue(gallery.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn('href="alpha/"', gallery, "links the directory, so <slug>/ resolves to index.html")
        self.assertIn('href="beta/"', gallery)
        self.assertIn("Alpha", gallery)
        self.assertIn("Beta", gallery)

    def test_gallery_escapes_untrusted_title_text(self):
        src = self.source("a.md", "# a\n")
        self.run_hook(payload(src, title="<script>alert(1)</script>", description='"><img onerror=x>'))
        with open(os.path.join(self.artifacts_root, "index.html"), encoding="utf-8") as f:
            gallery = f.read()
        self.assertNotIn("<script>alert(1)</script>", gallery)
        self.assertNotIn("<img onerror", gallery)
        self.assertIn("&lt;script&gt;", gallery)

    def test_markdown_source_has_no_redundant_slug_html(self):
        """A markdown source IS the readable form; its only counterpart is the
        viewable page, so a separate <slug>.html would just be a duplicate."""
        src = self.source("note.md", "# x\n")
        self.run_hook(payload(src))
        d = os.path.join(self.artifacts_root, "sample-title")
        self.assertTrue(os.path.isfile(os.path.join(d, "index.html")))
        self.assertFalse(os.path.isfile(os.path.join(d, "sample-title.html")))
