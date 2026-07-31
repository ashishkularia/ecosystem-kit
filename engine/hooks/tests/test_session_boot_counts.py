#!/usr/bin/env python3
"""Tests for session_boot's open-work counter (count_open_entries).

Contract:
  - Files using the kit's `- [ ]` convention: count unchecked boxes,
    drifted=False. Checked boxes (`- [x]`) never count.
  - Files with NO checkboxes but plain dated bullets (`- YYYY-MM-DD — ...`,
    optionally bold-dated): count bullets not marked RESOLVED, drifted=True —
    a false "0 unchecked" at session start hides real open work (meritick,
    2026-08-01 hygiene finding).
  - Mid-line quoted examples from the kit's .memory templates are never
    counted (the dated-bullet pattern anchors at column 0).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

MOD = _support.load_hook("session_boot")


def write_tmp(content):
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


class CountOpenEntriesTest(unittest.TestCase):
    def count(self, content):
        path = write_tmp(content)
        try:
            return MOD.count_open_entries(path)
        finally:
            os.unlink(path)

    def test_checkbox_file_counts_unchecked_only(self):
        n, drifted = self.count(
            "# ISSUES\n"
            "- [ ] 2026-07-23 — open one\n"
            "- [x] 2026-07-23 — RESOLVED (2026-08-01)\n"
            "- [ ] 2026-07-23 — open two\n"
        )
        self.assertEqual(n, 2)
        self.assertFalse(drifted)

    def test_indented_checkboxes_still_count(self):
        n, drifted = self.count("- [ ] top\n  - [ ] nested sub-task\n")
        self.assertEqual(n, 2)
        self.assertFalse(drifted)

    def test_dated_bullets_without_checkboxes_flag_drift(self):
        n, drifted = self.count(
            "# ISSUES\n"
            "Noticed, not acted on.\n"
            "- 2026-08-01 — **STATE.md went unmaintained** blah\n"
            "- 2026-07-21 — round the durations\n"
        )
        self.assertEqual(n, 2)
        self.assertTrue(drifted)

    def test_bold_dated_bullets_flag_drift(self):
        n, drifted = self.count("- **2026-07-29** — runner re-home owed\n")
        self.assertEqual(n, 1)
        self.assertTrue(drifted)

    def test_resolved_dated_bullets_not_counted(self):
        n, drifted = self.count(
            "- 2026-08-01 — open thing\n"
            "- 2026-07-20 — RESOLVED (2026-07-30): fixed thing\n"
        )
        self.assertEqual(n, 1)
        self.assertTrue(drifted)

    def test_closure_marker_on_a_continuation_line_closes_the_entry(self):
        # meritick's real shape: the entry wraps and "Status: RESOLVED" lands
        # on a later line. A line-based counter calls this open.
        n, drifted = self.count(
            "- 2026-07-06 — Framework-level transcript-leak vector; the fix is\n"
            "  a log scrubber at ops integration. Status:\n"
            "  RESOLVED 2026-07-11 — DbExceptionScrubber shipped.\n"
            "- 2026-07-29 — genuinely open thing\n"
        )
        self.assertEqual(n, 1)
        self.assertTrue(drifted)

    def test_status_done_closes_but_lowercase_prose_does_not(self):
        # "not done" is prose about open work; "Status: DONE" is a marker.
        n, drifted = self.count(
            "- 2026-07-05 — trademark clearance not done; hard requirement\n"
            "- 2026-07-08 — adversarial review. Status: DONE 2026-07-08\n"
        )
        self.assertEqual(n, 1)
        self.assertTrue(drifted)

    def test_partially_resolved_still_counts_as_open(self):
        n, _ = self.count(
            "- 2026-07-10 — rubric editor built; descriptors pending. Status:\n"
            "  PARTIALLY RESOLVED 2026-07-11 — band_descriptors landed.\n"
        )
        self.assertEqual(n, 1)

    def test_column0_prose_ends_an_entry_block(self):
        # A closure marker in an unrelated paragraph must not reach back and
        # close the preceding entry.
        n, _ = self.count(
            "- 2026-08-01 — open thing\n"
            "\n"
            "Some section prose mentioning RESOLVED items generally.\n"
        )
        self.assertEqual(n, 1)

    def test_template_midline_examples_not_counted(self):
        # The kit templates quote entry patterns mid-line; neither counter may
        # treat them as real open entries.
        n, drifted = self.count(
            "# ISSUES — proj\n"
            '<!-- Open entry: "- [ ] YYYY-MM-DD — the observation."\n'
            'Closed: "- [x] RESOLVED (YYYY-MM-DD) — outcome" -->\n'
            'Entry: "- 2026-01-01 — quoted example" more prose\n'
        )
        self.assertEqual(n, 0)
        self.assertFalse(drifted)

    def test_empty_or_missing_file(self):
        self.assertEqual(self.count(""), (0, False))
        self.assertEqual(MOD.count_open_entries("/nonexistent/VERIFY.md"), (0, False))

    def test_checkboxes_win_over_dated_bullets(self):
        # A file mixing both follows the kit convention; no drift flagged.
        n, drifted = self.count(
            "- [ ] 2026-08-01 — checkbox entry\n"
            "- 2026-07-01 — legacy prose bullet\n"
        )
        self.assertEqual(n, 1)
        self.assertFalse(drifted)


if __name__ == "__main__":
    unittest.main()
