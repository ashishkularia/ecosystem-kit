#!/usr/bin/env python3
"""Tests for the shared shell-command splitter (_constants.split_shell_commands).

This is a SECURITY primitive: every guard finds the commands it must inspect
through it, so a form it fails to split is a form that hides from the guard.

The 2026-08-01 bypass: it split on `&&`, `||`, `;` but not on a lone `|`, so
`git push | tail -2` parsed as ONE command whose push arguments were
['|','tail','-2'] — `tail` read as an explicit, unprotected push destination —
and guard_protected_merge allowed a push to a protected branch. Reported from a
homeassistant session that had already pushed to master.

Design rule under test: OVER-split rather than under-split. An extra fragment
costs at most a false positive; a missed fragment is a bypass.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support

MOD = _support.load_hook("_constants")
split = MOD.split_shell_commands


class SeparatorTest(unittest.TestCase):
    def assertFinds(self, command, needle="git push"):
        self.assertIn(needle, split(command),
                      f"{command!r} hid {needle!r} from the guards: {split(command)}")

    def test_classic_separators(self):
        for cmd in ("git add -A && git push", "git add -A || git push",
                    "git add -A; git push"):
            self.assertFinds(cmd)

    def test_pipe_is_a_separator(self):
        # The reported bypass, and the habitual form ("trim the output").
        self.assertFinds("git push | tail -2")
        self.assertFinds("git push | cat")
        self.assertFinds("git push |& tail")

    def test_newline_is_a_separator(self):
        self.assertFinds("git add -A\ngit push")

    def test_background_operator_is_a_separator(self):
        self.assertFinds("git push &")

    def test_grouping_constructs_do_not_hide_commands(self):
        self.assertFinds("(git push)")
        self.assertFinds("{ git push; }")

    def test_command_substitution_does_not_hide_commands(self):
        self.assertFinds("$(git push)")
        self.assertFinds("`git push`")

    def test_nested_and_chained_forms(self):
        self.assertFinds("cd repo && (git push | tail -1)")

    def test_shell_keywords_do_not_become_the_command_word(self):
        # `do git push` / `then git push`: left alone, the KEYWORD reads as the
        # command and the guard never sees git.
        self.assertFinds("for f in a b; do git push; done")
        self.assertFinds("if true; then git push; fi")
        self.assertFinds("while :; do git push; done")

    def test_wrappers_and_assignments_do_not_hide_the_command(self):
        for cmd in ("sudo git push", "command git push", "nohup git push",
                    "env git push", "FOO=bar git push", "GIT_DIR=/x git push"):
            self.assertFinds(cmd)

    def test_raw_fragment_is_kept_alongside_the_stripped_one(self):
        # Guards that match whole command lines must still see the original.
        out = split("sudo git push")
        self.assertIn("sudo git push", out)
        self.assertIn("git push", out)


class LiteralPreservationTest(unittest.TestCase):
    """Over-splitting is acceptable; MIS-splitting is not — a mangled command
    could flip a block into an allow by changing which token reads as a
    destination."""

    def test_redirection_ampersand_is_not_a_separator(self):
        # 2>&1 must survive intact: `git push 2>` with a stray `1` would change
        # how the push arguments parse.
        self.assertEqual(split("git push 2>&1"), ["git push 2>&1"])
        self.assertEqual(split("git push >&2"), ["git push >&2"])

    def test_separators_inside_quotes_are_literal(self):
        self.assertEqual(split('git commit -m "a|b;c"'), ['git commit -m "a|b;c"'])
        self.assertEqual(split("git commit -m 'x && y'"), ["git commit -m 'x && y'"])

    def test_quoted_command_text_is_not_a_command(self):
        # `echo "git push"` does not push; the first token is echo.
        self.assertEqual(split('echo "git push" | cat'), ['echo "git push"', "cat"])

    def test_plain_command_is_untouched(self):
        self.assertEqual(split("git push origin master"), ["git push origin master"])

    def test_empty_and_whitespace(self):
        self.assertEqual(split(""), [])
        self.assertEqual(split("   "), [])
        self.assertEqual(split(" ; | && "), [])


class HeredocTest(unittest.TestCase):
    """A heredoc body is DATA, not commands.

    Adding newline to the separator set made every line of a commit message
    parse as its own command, so `git commit -F - <<'EOF' … EOF` with a message
    mentioning `git push origin main` blocked itself. Caught the moment the kit
    was installed on the kit — this commit could not be written until it was
    fixed. Same principle as blanking quoted spans so a commit message may
    discuss `rm -rf` (2026-07-23).
    """

    COMMIT = "git commit -F - <<'EOF'\n%s\nEOF\ngit log --oneline -1"

    def test_message_body_is_not_parsed_as_commands(self):
        out = split(self.COMMIT % "a message that says git push origin main")
        self.assertNotIn("git push origin main", out)
        self.assertIn("git log --oneline -1", out)

    def test_multiline_message_body_is_dropped_entirely(self):
        body = "first line\ngit push origin main\nrm -rf /\nlast line"
        out = split(self.COMMIT % body)
        for leaked in ("git push origin main", "rm -rf /", "first line"):
            self.assertNotIn(leaked, out)

    def test_a_real_command_after_the_heredoc_is_still_found(self):
        out = split("git commit -F - <<'EOF'\nmsg\nEOF\ngit push origin main")
        self.assertIn("git push origin main", out)

    def test_unquoted_and_dash_forms(self):
        for opener in ("<<EOF", "<<-EOF", '<<"EOF"'):
            out = split(f"git commit -F - {opener}\ngit push origin main\nEOF")
            self.assertNotIn("git push origin main", out, opener)

    def test_unterminated_heredoc_does_not_hang_or_leak(self):
        out = split("git commit -F - <<'EOF'\nstuff git push origin main")
        self.assertNotIn("git push origin main", out)

    def test_command_without_heredoc_is_unaffected(self):
        self.assertEqual(split("git push | tail -2"), ["git push", "tail -2"])


class SharedImplementationTest(unittest.TestCase):
    """All three guards must resolve to the ONE implementation. They used to
    each carry a copy, and the copies drifted — only guard_dangerous_commands
    ever learned to extract `$(...)`. A security parser with three forks gets
    fixed in one of them."""

    def test_guards_use_the_shared_splitter(self):
        for name in ("guard_protected_merge", "guard_dangerous_commands",
                     "guard_branch_naming"):
            mod = _support.load_hook(name)
            self.assertIs(mod.split_shell_commands, split,
                          f"{name} does not use the shared splitter")

    def test_no_guard_defines_its_own_copy(self):
        hooks_dir = _support.HOOKS_DIR
        for fname in os.listdir(hooks_dir):
            if not fname.startswith("guard_") or not fname.endswith(".py"):
                continue
            with open(os.path.join(hooks_dir, fname), encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotIn("def split_shell_commands(", src,
                             f"{fname} re-defines the splitter — import it from _constants")


if __name__ == "__main__":
    unittest.main()
