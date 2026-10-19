#!/usr/bin/env python3
"""Tests for the scratch-cleanup exemption in guard_dangerous_commands.

`rm -rf` is blocked everywhere EXCEPT when the whole command line is nothing but
`rm` of literal paths strictly inside this project's `.claude/scratch/`. The
guard is a fail-closed blocker, so the exemption is tested mostly by what it
must still refuse: every shell metacharacter, `..`, symlink escapes, the scratch
root itself, other projects' scratch, and any chain that contains a command
other than a scratch `rm` (which could create a symlink between check and run).
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import bash_payload, run_hook

MOD = _support.load_hook("guard_dangerous_commands")


class _Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="kit-scratch-rm-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = os.path.join(self.tmp, "repo")
        self.scratch = os.path.join(self.root, ".claude", "scratch")
        self.outside = os.path.join(self.tmp, "outside")
        os.makedirs(os.path.join(self.scratch, "sub"))
        os.makedirs(os.path.join(self.root, "engine", "hooks"))
        os.makedirs(self.outside)
        patch = _support.patched(MOD, PROJECT_ROOT=self.root)
        patch.__enter__()
        self.addCleanup(patch.__exit__, None, None, None)

    def code(self, command, cwd=None):
        payload = bash_payload(command, cwd=cwd or self.root)
        return run_hook(MOD, payload)[0]

    def exempt(self, command, cwd=None):
        return MOD.scratch_cleanup_only(command, cwd or self.root)

    def assertAllowed(self, command, cwd=None):
        self.assertEqual(self.code(command, cwd), 0, command)

    def assertBlocked(self, command, cwd=None):
        self.assertEqual(self.code(command, cwd), 2, command)


class AllowedScratchCleanupTest(_Repo):
    def test_recursive_force_in_every_spelling(self):
        for flags in ("-rf", "-fr", "-Rf", "-r -f", "--recursive --force", "-rfv"):
            self.assertAllowed(f"rm {flags} .claude/scratch/g2-install")

    def test_end_of_options_marker(self):
        self.assertAllowed("rm -rf -- .claude/scratch/x")

    def test_several_operands_and_nested_paths(self):
        self.assertAllowed("rm -rf .claude/scratch/a .claude/scratch/b/c")

    def test_trailing_slash_and_missing_target(self):
        self.assertAllowed("rm -rf .claude/scratch/never-existed/")

    def test_chain_of_nothing_but_scratch_removals(self):
        self.assertAllowed("rm -rf .claude/scratch/a && rm -rf .claude/scratch/b")
        self.assertAllowed("rm -rf .claude/scratch/a; rm -rf .claude/scratch/b")

    def test_absolute_path_inside_this_projects_scratch(self):
        self.assertAllowed(f"rm -rf {self.scratch}/x")

    def test_relative_operand_resolves_against_the_command_cwd(self):
        self.assertAllowed("rm -rf x", cwd=os.path.join(self.scratch, "sub"))


class RefusedEvenInsideScratchTest(_Repo):
    def test_the_scratch_root_itself(self):
        for target in (".claude/scratch", ".claude/scratch/"):
            self.assertBlocked(f"rm -rf {target}")
        self.assertBlocked("rm -rf .", cwd=self.scratch)

    def test_dotdot_traversal(self):
        for target in (".claude/scratch/..", ".claude/scratch/../..",
                       ".claude/scratch/x/../../.."):
            self.assertBlocked(f"rm -rf {target}")
        self.assertBlocked("rm -rf ../x", cwd=os.path.join(self.scratch, "sub"))

    def test_outside_scratch(self):
        for target in ("/tmp/x", "src", ".claude/hooks", ".claude", "~", "/"):
            self.assertBlocked(f"rm -rf {target}")

    def test_lookalike_siblings(self):
        for target in (".claude/scratchy/x", ".claude/scratch.bak/x"):
            self.assertBlocked(f"rm -rf {target}")

    def test_one_bad_operand_poisons_the_command(self):
        self.assertBlocked("rm -rf .claude/scratch/x /etc")
        self.assertBlocked("rm -rf /etc .claude/scratch/x")

    def test_relative_path_from_the_wrong_cwd(self):
        # The shell would run this in engine/hooks, not at the repo root.
        self.assertBlocked("rm -rf .claude/scratch/x",
                           cwd=os.path.join(self.root, "engine", "hooks"))

    def test_another_projects_scratch(self):
        other = os.path.join(self.tmp, "other", ".claude", "scratch", "x")
        self.assertBlocked(f"rm -rf {other}")


class ShellMetacharactersAreNotLiteralPathsTest(_Repo):
    def test_each_metacharacter_defeats_the_exemption(self):
        cases = {
            "variable": "rm -rf .claude/scratch/$X",
            "substitution": "rm -rf .claude/scratch/$(pwd)",
            "backtick": "rm -rf .claude/scratch/`pwd`",
            "glob star": "rm -rf .claude/scratch/*",
            "glob query": "rm -rf .claude/scratch/?",
            "glob bracket": "rm -rf .claude/scratch/[a]",
            "brace": "rm -rf .claude/scratch/{a,b}",
            "tilde": "rm -rf .claude/scratch/~",
            "double quoted": 'rm -rf ".claude/scratch/x"',
            "single quoted": "rm -rf '.claude/scratch/x'",
            "backslash": "rm -rf .claude/scratch/a\\ b",
            "redirect out": "rm -rf .claude/scratch/x > /etc/f",
            "redirect tight": "rm -rf .claude/scratch/x >/etc/f",
            "redirect in": "rm -rf .claude/scratch/x < /etc/f",
            "pipe": "rm -rf .claude/scratch/x | cat",
            "background": "rm -rf .claude/scratch/x &",
            "or-chain": "rm -rf .claude/scratch/x || true",
            "subshell": "(rm -rf .claude/scratch/x)",
            "comment": "rm -rf .claude/scratch/x # y",
            "history": "rm -rf .claude/scratch/!x",
        }
        for label, command in cases.items():
            with self.subTest(label):
                self.assertBlocked(command)

    def test_newline_is_a_command_separator_not_whitespace(self):
        self.assertBlocked("rm -rf .claude/scratch/x\nrm -rf /")
        self.assertBlocked("rm -rf .claude/scratch/x\r\nrm -rf /")
        # Python's `$` matches before a trailing newline, so the regex alone
        # would accept the first half of this line.
        self.assertBlocked("rm -rf .claude/scratch/a\n&& rm -rf .claude/scratch/b")

    def test_dash_led_operand_is_never_an_operand(self):
        self.assertBlocked("rm -rf .claude/scratch/x -rf")
        # From inside scratch a dash-led word WOULD resolve inside it, so only
        # the alphabet rule keeps it from being treated as a path.
        for command in ("rm -rf x -rf", "rm -rf x --no-preserve-root", "rm -rf -x"):
            self.assertFalse(self.exempt(command, cwd=self.scratch), command)

    def test_only_the_known_harmless_flags_are_recognised(self):
        # Asserted on the predicate, not end to end: the base patterns do not
        # see every flag spelling (`rm --no-preserve-root -rf x` passes the
        # unmodified guard — see ISSUES), so "blocked" would prove nothing here.
        for flags in ("-rfx", "--no-preserve-root -rf", "-rf --interactive",
                      "-rI", "-d -rf", "-rf -i"):
            self.assertFalse(self.exempt(f"rm {flags} .claude/scratch/x"), flags)
        self.assertTrue(self.exempt("rm -rf .claude/scratch/x"))


class OnlyScratchRemovalsMayShareACommandLineTest(_Repo):
    def test_a_symlink_created_in_the_same_line_cannot_redirect_the_removal(self):
        # At check time the link does not exist, so a path-only check would pass.
        self.assertBlocked(
            f"ln -s {self.outside} .claude/scratch/l && rm -rf .claude/scratch/l/victim")

    def test_any_non_scratch_removal_in_the_chain_blocks_the_whole_line(self):
        self.assertBlocked("rm -rf .claude/scratch/x && rm -rf /tmp/y")
        self.assertBlocked("rm -rf .claude/scratch/x; echo done")
        self.assertBlocked("echo start && rm -rf .claude/scratch/x")

    def test_wrappers_are_not_recognised(self):
        for prefix in ("sudo ", "env ", "command ", "nohup "):
            self.assertBlocked(f"{prefix}rm -rf .claude/scratch/x")


class SymlinkEscapesTest(_Repo):
    def test_symlink_inside_scratch_pointing_out(self):
        victim = os.path.join(self.outside, "victim")
        os.mkdir(victim)
        os.symlink(self.outside, os.path.join(self.scratch, "link"))
        self.assertBlocked("rm -rf .claude/scratch/link/victim")
        self.assertBlocked("rm -rf .claude/scratch/link")  # conservative: not followed

    def test_scratch_directory_that_is_itself_a_symlink(self):
        shutil.rmtree(self.scratch)
        os.makedirs(os.path.join(self.outside, "precious"))
        os.symlink(self.outside, self.scratch)
        self.assertBlocked("rm -rf .claude/scratch/precious")

    def test_dot_claude_that_is_a_symlink(self):
        shutil.rmtree(os.path.join(self.root, ".claude"))
        os.makedirs(os.path.join(self.outside, "scratch", "precious"))
        os.symlink(self.outside, os.path.join(self.root, ".claude"))
        self.assertBlocked("rm -rf .claude/scratch/precious")


class RestOfTheGuardIsUnchangedTest(_Repo):
    def test_other_destructive_commands_inside_scratch_still_block(self):
        self.assertBlocked("chmod 777 .claude/scratch/x")
        self.assertBlocked("git reset --hard HEAD")
        self.assertBlocked("git clean -fd .claude/scratch/x")

    def test_non_forced_removals_were_never_blocked(self):
        self.assertAllowed("rm -r .claude/scratch/x")
        self.assertAllowed("rm .claude/scratch/x")

    def test_unrelated_rm_rf_still_blocks(self):
        self.assertBlocked("cd /tmp; rm -rf cache")
        self.assertBlocked("rm -rf node_modules")

    def test_an_internal_error_loses_the_exemption_never_grants_it(self):
        # realpath(None) raises inside scratch_cleanup_only. The guard must
        # fall back to its normal answer (block), not crash and not allow.
        with _support.patched(MOD, PROJECT_ROOT=None):
            self.assertBlocked("rm -rf .claude/scratch/x")

    def test_a_missing_cwd_cannot_crash_the_exemption(self):
        # No cwd in the payload: falls back to the process cwd, never raises.
        code = run_hook(MOD, bash_payload("rm -rf .claude/scratch/x"))[0]
        self.assertIn(code, (0, 2))


if __name__ == "__main__":
    unittest.main()
