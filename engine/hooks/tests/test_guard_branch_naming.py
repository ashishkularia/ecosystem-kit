#!/usr/bin/env python3
"""Tests for guard_branch_naming — kit.json-driven types + protected creation."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import bash_payload, make_kit, patched, run_hook

MOD = _support.load_hook("guard_branch_naming")


def run_with_kit(command, kit):
    with patched(MOD, load_kit=lambda force_reload=False: kit):
        return run_hook(MOD, bash_payload(command))


class ProtectedBranchCreationTest(unittest.TestCase):
    def setUp(self):
        self.kit = make_kit()

    def test_checkout_b_main_blocked(self):
        code, _out, err = run_with_kit("git checkout -b main", self.kit)
        self.assertEqual(code, 2)
        self.assertIn("protected", err.lower())

    def test_switch_c_master_blocked(self):
        code, _out, _err = run_with_kit("git switch -c master", self.kit)
        self.assertEqual(code, 2)

    def test_git_branch_main_blocked(self):
        code, _out, _err = run_with_kit("git branch main", self.kit)
        self.assertEqual(code, 2)

    def test_creation_blocked_in_command_chain(self):
        code, _out, _err = run_with_kit(
            "git fetch origin && git checkout -b main", self.kit
        )
        self.assertEqual(code, 2)

    def test_custom_protected_branch_blocked(self):
        kit = make_kit(protected_branches=["main", "master", "production"])
        code, _out, _err = run_with_kit("git checkout -b production", kit)
        self.assertEqual(code, 2)


class ConfiguredTypesTest(unittest.TestCase):
    def test_default_types_pass_silently(self):
        code, out, err = run_with_kit("git checkout -b feature/add-widget", make_kit())
        self.assertEqual(code, 0, err)
        self.assertNotIn("ADVISORY", out)

    def test_meritick_style_feat_type_accepted_when_configured(self):
        kit = make_kit(branch_types=["feat", "fix", "chore"])
        code, out, _err = run_with_kit("git checkout -b feat/add-widget", kit)
        self.assertEqual(code, 0)
        self.assertNotIn("ADVISORY", out)

    def test_type_not_in_config_gets_advisory(self):
        kit = make_kit(branch_types=["feat", "fix", "chore"])
        code, out, _err = run_with_kit("git checkout -b feature/add-widget", kit)
        self.assertEqual(code, 0)  # advisory, never blocks
        self.assertIn("ADVISORY", out)

    def test_non_kebab_description_gets_advisory(self):
        code, out, _err = run_with_kit("git checkout -b feature/Add_Widget", make_kit())
        self.assertEqual(code, 0)
        self.assertIn("ADVISORY", out)

    def test_push_of_conforming_branch_silent(self):
        code, out, err = run_with_kit("git push -u origin fix/login-bug", make_kit())
        self.assertEqual(code, 0, err)
        self.assertNotIn("ADVISORY", out)

    def test_push_of_nonconforming_branch_gets_advisory(self):
        code, out, _err = run_with_kit("git push -u origin myrandombranch", make_kit())
        self.assertEqual(code, 0)
        self.assertIn("ADVISORY", out)

    def test_push_of_protected_branch_not_flagged_here(self):
        # Naming-wise main is fine; blocking pushes to it is guard_protected_merge's job.
        code, out, _err = run_with_kit("git push origin main", make_kit())
        self.assertEqual(code, 0)
        self.assertNotIn("ADVISORY", out)


class NonBranchCommandsTest(unittest.TestCase):
    def test_unrelated_command_ignored(self):
        code, out, err = run_with_kit("ls -la", make_kit())
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")

    def test_branch_listing_ignored(self):
        code, out, _err = run_with_kit("git branch --list", make_kit())
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_branch_delete_ignored(self):
        code, out, _err = run_with_kit("git branch -d feature/old", make_kit())
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
