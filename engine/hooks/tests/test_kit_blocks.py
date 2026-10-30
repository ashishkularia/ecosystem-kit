#!/usr/bin/env python3
"""Tests for installer/kit_blocks.py — kit-managed blocks inside a project's CLAUDE.md.

This is the first place the kit edits a PROJECT-OWNED file, so the contract is
tested mostly by what must NOT change: every byte outside the markers, anything
malformed, anything it cannot be sure about. A failure here edits a file that
five repos treat as hand-written policy.
"""
import importlib.util
import os
import shutil
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

KIT_ROOT = os.path.dirname(os.path.dirname(_support.HOOKS_DIR))  # engine/hooks -> engine -> kit
MODULE_PATH = os.path.join(KIT_ROOT, "installer", "kit_blocks.py")
TEMPLATE_PATH = os.path.join(KIT_ROOT, "templates", "CLAUDE.md.template")


def load_module():
    spec = importlib.util.spec_from_file_location("kit_blocks", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KB = load_module()


def block(name, body, note=" (managed)"):
    return f"<!-- kit:begin {name}{note} -->\n{body}\n<!-- kit:end {name} -->"


TEMPLATE_A = "# T\n\n" + block("a", "## A rule\n- kit says A") + "\n\ntrailer\n"


def statuses(results):
    return {name: status for name, status, _ in results}


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


class InsertTest(unittest.TestCase):
    def test_missing_block_is_appended_after_a_blank_line(self):
        target = "# Project\n\nOur own policy.\n"
        new, results = KB.sync(TEMPLATE_A, target)
        self.assertEqual(statuses(results), {"a": "INSERTED"})
        self.assertEqual(new, target + "\n" + block("a", "## A rule\n- kit says A") + "\n")

    def test_everything_before_the_insert_is_untouched(self):
        target = "# P\r\nno\r\n" .replace("\r\n", "\n") + "weird   trailing   \n\n\n"
        new, _ = KB.sync(TEMPLATE_A, target)
        self.assertTrue(new.startswith(target.rstrip("\n")))

    def test_file_without_trailing_newline_and_empty_file(self):
        new, _ = KB.sync(TEMPLATE_A, "no newline at end")
        self.assertTrue(new.startswith("no newline at end\n\n<!-- kit:begin a"))
        self.assertTrue(new.endswith("<!-- kit:end a -->\n"))
        new, _ = KB.sync(TEMPLATE_A, "")
        self.assertEqual(new, block("a", "## A rule\n- kit says A") + "\n")


class UpdateTest(unittest.TestCase):
    def test_stale_block_is_rewritten_and_the_rest_is_byte_identical(self):
        before = "# Mine\nkeep  this \n\n"
        after = "\n\n## Project rules\n- ours\n"
        stale = block("a", "## A rule\n- OLD", note=" (old note)")
        new, results = KB.sync(TEMPLATE_A, before + stale + after)
        self.assertEqual(statuses(results), {"a": "UPDATED"})
        self.assertEqual(new, before + block("a", "## A rule\n- kit says A") + after)

    def test_project_edits_inside_the_block_are_overwritten(self):
        edited = block("a", "## A rule\n- kit says A\n- someone added this")
        new, results = KB.sync(TEMPLATE_A, edited + "\n")
        self.assertEqual(statuses(results), {"a": "UPDATED"})
        self.assertNotIn("someone added this", new)

    def test_identical_block_is_unchanged_and_text_is_exact(self):
        target = "x\n" + block("a", "## A rule\n- kit says A") + "\ny"  # no final newline
        new, results = KB.sync(TEMPLATE_A, target)
        self.assertEqual(statuses(results), {"a": "UNCHANGED"})
        self.assertEqual(new, target)

    def test_sync_is_idempotent(self):
        once, _ = KB.sync(TEMPLATE_A, "# P\n")
        twice, results = KB.sync(TEMPLATE_A, once)
        self.assertEqual(once, twice)
        self.assertEqual(statuses(results), {"a": "UNCHANGED"})

    def test_replacement_text_is_inserted_verbatim(self):
        # re.sub would read these as group references / escapes.
        nasty = "regex \\1 \\g<0> $& \\n (?P<x>) [a-z]+ \\\\ end"
        new, _ = KB.sync(block("a", nasty), "# P\n")
        self.assertIn(nasty, new)
        stale = block("a", "old")
        new, _ = KB.sync(block("a", nasty), stale + "\n")
        self.assertIn(nasty, new)


class SeveralBlocksTest(unittest.TestCase):
    TEMPLATE = "# T\n\n" + block("a", "A body") + "\n\n" + block("b", "B body") + "\n"

    def test_blocks_are_independent(self):
        target = "# P\n" + block("a", "A stale") + "\nours\n"
        new, results = KB.sync(self.TEMPLATE, target)
        self.assertEqual(statuses(results), {"a": "UPDATED", "b": "INSERTED"})
        self.assertIn("ours", new)
        self.assertIn("B body", new)

    def test_a_malformed_block_does_not_stop_the_others(self):
        target = "# P\n<!-- kit:begin a -->\nstale, no end marker\n"
        new, results = KB.sync(self.TEMPLATE, target)
        self.assertEqual(statuses(results), {"a": "KEPT", "b": "INSERTED"})
        self.assertIn("stale, no end marker", new)


class MalformedTargetsAreLeftAloneTest(unittest.TestCase):
    def assertKept(self, target, fragment):
        new, results = KB.sync(TEMPLATE_A, target)
        self.assertEqual(statuses(results), {"a": "KEPT"}, target)
        self.assertEqual(new, target, "a KEPT block must leave the file byte-identical")
        self.assertIn(fragment, results[0][2])

    def test_begin_without_end(self):
        self.assertKept("x\n<!-- kit:begin a -->\nbody\n", "1 begin and 0 end")

    def test_end_without_begin(self):
        self.assertKept("x\nbody\n<!-- kit:end a -->\n", "0 begin and 1 end")

    def test_duplicate_blocks(self):
        two = block("a", "one") + "\n" + block("a", "two") + "\n"
        self.assertKept(two, "2 begin and 2 end")

    def test_end_before_begin(self):
        self.assertKept("<!-- kit:end a -->\nmid\n<!-- kit:begin a -->\n", "before begin")

    def test_another_blocks_marker_inside(self):
        self.assertKept(
            "<!-- kit:begin a -->\n<!-- kit:begin zzz -->\n<!-- kit:end zzz -->\n<!-- kit:end a -->\n",
            "cannot nest")

    def test_crlf_files_are_not_touched(self):
        target = "# P\r\nours\r\n"
        new, results = KB.sync(TEMPLATE_A, target)
        self.assertEqual(new, target)
        self.assertEqual(statuses(results), {"a": "KEPT"})
        self.assertIn("CRLF", results[0][2])


class OnlyRealMarkersCountTest(unittest.TestCase):
    def test_lookalikes_are_ignored(self):
        prose = ("Docs: write `<!-- kit:begin a -->` to start a block.\n"
                 "    <!-- kit:begin a -->\n"           # indented: a code sample
                 "<!-- kit:begin a --> trailing prose\n"  # not the whole line
                 "<!-- kit:begin A -->\n"
                 "<!-- kit:begin a-->\n"
                 "<!--kit:begin a -->\n")
        new, results = KB.sync(TEMPLATE_A, prose)
        self.assertEqual(statuses(results), {"a": "INSERTED"})
        self.assertTrue(new.startswith(prose))


class TemplateValidationTest(unittest.TestCase):
    def test_a_broken_template_raises_instead_of_guessing(self):
        for bad in ("<!-- kit:begin a -->\nno end\n",
                    "<!-- kit:end a -->\n",
                    block("a", "x") + "\n" + block("a", "y") + "\n"):
            with self.assertRaises(KB.BlockError):
                KB.sync(bad, "# P\n")

    def test_an_unrendered_placeholder_inside_a_block_raises(self):
        with self.assertRaises(KB.BlockError):
            KB.sync(block("a", "project is {{PROJECT}}"), "# P\n")

    def test_placeholders_outside_blocks_are_fine(self):
        new, _ = KB.sync("# {{PROJECT}}\n" + block("a", "ok") + "\n", "# P\n")
        self.assertNotIn("{{PROJECT}}", new)

    def test_template_without_blocks_is_a_no_op(self):
        new, results = KB.sync("# T\njust text\n", "# P\n")
        self.assertEqual((new, results), ("# P\n", []))


class ShippedTemplateTest(unittest.TestCase):
    def test_the_real_template_parses_and_carries_the_scratch_block(self):
        template = read(TEMPLATE_PATH)
        lines = template.split("\n")
        good, bad = KB.spans(lines)
        self.assertEqual(bad, {})
        self.assertIn("scratch", good)
        b, e = good["scratch"]
        body = "\n".join(lines[b:e + 1])
        self.assertNotIn("{{", body)
        self.assertIn("never in /tmp", body)
        self.assertIn("managed by ecosystem-kit", lines[b])

    def test_each_block_keeps_a_blank_line_inside_its_markers(self):
        # Prettier puts one there, so without it every update fails the format
        # check of a project that runs Prettier on CLAUDE.md.
        lines = read(TEMPLATE_PATH).split("\n")
        good, _ = KB.spans(lines)
        for name, (b, e) in good.items():
            with self.subTest(block=name):
                self.assertEqual(lines[b + 1], "")
                self.assertEqual(lines[e - 1], "")

    def test_install_then_update_is_a_no_op(self):
        # install.sh renders the template; update.sh must then find nothing to do.
        template = read(TEMPLATE_PATH)
        rendered = (template.replace("{{PROJECT}}", "demo").replace("{{STACK}}", "x")
                    .replace("{{DATE}}", "2026-01-01").replace("{{REPO_ABS}}", "/r"))
        new, results = KB.sync(template, rendered)
        self.assertEqual(new, rendered)
        self.assertEqual(set(statuses(results).values()), {"UNCHANGED"})


class FileLevelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="kit-blocks-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.template = os.path.join(self.tmp, "t.template")
        self.target = os.path.join(self.tmp, "CLAUDE.md")
        with open(self.template, "w", encoding="utf-8") as f:
            f.write(TEMPLATE_A)

    def run_main(self):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = KB.main(["kit_blocks.py", self.template, self.target])
        return code, out.getvalue(), err.getvalue()

    def test_writes_the_file_reports_and_counts(self):
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("# P\n")
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("INSERTED CLAUDE.md block 'a'", out)
        self.assertTrue(out.strip().splitlines()[-1].startswith("@counts new=1 changed=0 unchanged=0 kept=0"))
        self.assertIn("kit:begin a", read(self.target))

    def test_second_run_changes_nothing_and_does_not_rewrite(self):
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("# P\n")
        self.run_main()
        before = os.stat(self.target)
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertNotIn("INSERTED", out)
        self.assertNotIn("UPDATED", out)
        self.assertIn("unchanged=1", out)
        self.assertEqual(os.stat(self.target).st_mtime_ns, before.st_mtime_ns)

    def test_file_mode_is_preserved_and_no_temp_file_is_left(self):
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("# P\n")
        os.chmod(self.target, 0o640)
        self.run_main()
        self.assertEqual(stat.S_IMODE(os.stat(self.target).st_mode), 0o640)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["CLAUDE.md", "t.template"])

    def test_a_symlinked_claude_md_stays_a_symlink(self):
        real = os.path.join(self.tmp, "AGENTS.md")
        with open(real, "w", encoding="utf-8") as f:
            f.write("# Agents\n")
        os.symlink(real, self.target)
        self.run_main()
        self.assertTrue(os.path.islink(self.target))
        self.assertIn("kit:begin a", read(real))

    def test_missing_target_is_a_note_not_a_file(self):
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("CLAUDE.md missing", out)
        self.assertFalse(os.path.exists(self.target))

    def test_broken_template_is_an_error_and_the_target_is_untouched(self):
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("# P\n")
        with open(self.template, "w", encoding="utf-8") as f:
            f.write("<!-- kit:begin a -->\nno end\n")
        code, _out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("template", err)
        self.assertEqual(read(self.target), "# P\n")

    def test_unicode_survives(self):
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("# Projekt — Größe ✓\n")
        self.run_main()
        self.assertTrue(read(self.target).startswith("# Projekt — Größe ✓\n"))


if __name__ == "__main__":
    unittest.main()
