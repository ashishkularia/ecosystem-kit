#!/usr/bin/env python3
"""Tests for guard_dangerous_commands — blocking hook, fails closed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import bash_payload, run_hook

MOD = _support.load_hook("guard_dangerous_commands")


def run(command):
    return run_hook(MOD, bash_payload(command))


class DestructiveGitTest(unittest.TestCase):
    def test_force_push_blocked(self):
        code, _out, err = run("git push --force origin feature/x")
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", err)

    def test_force_push_short_flag_blocked(self):
        code, _out, _err = run("git push -f origin feature/x")
        self.assertEqual(code, 2)

    def test_hard_reset_blocked(self):
        code, _out, _err = run("git reset --hard HEAD~1")
        self.assertEqual(code, 2)

    def test_git_clean_blocked(self):
        code, _out, _err = run("git clean -fd")
        self.assertEqual(code, 2)

    def test_branch_capital_d_blocked(self):
        code, _out, _err = run("git branch -D feature/old")
        self.assertEqual(code, 2)

    def test_branch_lowercase_d_allowed(self):
        code, _out, err = run("git branch -d feature/old")
        self.assertEqual(code, 0, err)

    def test_normal_push_allowed(self):
        code, _out, err = run("git push origin feature/x")
        self.assertEqual(code, 0, err)


class EnvStagingTest(unittest.TestCase):
    def test_git_add_all_blocked(self):
        code, _out, _err = run("git add -A")
        self.assertEqual(code, 2)

    def test_git_add_dot_blocked(self):
        code, _out, _err = run("git add .")
        self.assertEqual(code, 2)

    def test_git_add_env_blocked(self):
        code, _out, _err = run("git add .env")
        self.assertEqual(code, 2)

    def test_git_add_specific_file_allowed(self):
        code, _out, err = run("git add src/app.py")
        self.assertEqual(code, 0, err)


class FilesystemTest(unittest.TestCase):
    def test_rm_rf_blocked(self):
        code, _out, _err = run("rm -rf build/")
        self.assertEqual(code, 2)

    def test_chmod_777_blocked(self):
        code, _out, _err = run("chmod 777 storage/")
        self.assertEqual(code, 2)

    def test_plain_rm_allowed(self):
        code, _out, err = run("rm stale.txt")
        self.assertEqual(code, 0, err)

    def test_rm_rf_with_quoted_target_still_blocked(self):
        # The dangerous part (command + flags) is outside the quotes.
        code, _out, _err = run('rm -rf "build/"')
        self.assertEqual(code, 2)


class QuotedMentionTest(unittest.TestCase):
    """Text that merely MENTIONS a dangerous command must not block."""

    def test_commit_message_mentioning_rm_rf_allowed(self):
        code, _out, err = run('git commit -m "chore: rm -rf cleanup docs"')
        self.assertEqual(code, 0, err)

    def test_echo_mentioning_hard_reset_allowed(self):
        code, _out, err = run("echo 'never run git reset --hard on main'")
        self.assertEqual(code, 0, err)


class DatabaseTest(unittest.TestCase):
    def test_drop_table_blocked(self):
        code, _out, _err = run("mysql -e 'DROP TABLE users'")
        self.assertEqual(code, 2)

    def test_delete_without_where_blocked(self):
        code, _out, _err = run("mysql -e 'DELETE FROM users;'")
        self.assertEqual(code, 2)

    def test_delete_without_where_quoted_no_semicolon_blocked(self):
        # Regression: the closing quote used to defeat the end-of-string
        # anchor, letting the realistic quoted form through.
        code, _out, _err = run('mysql -e "DELETE FROM sessions"')
        self.assertEqual(code, 2)

    def test_delete_with_where_allowed(self):
        code, _out, err = run("mysql -e 'DELETE FROM users WHERE id = 5'")
        self.assertEqual(code, 0, err)

    def test_update_without_where_blocked(self):
        code, _out, _err = run("mysql -e 'UPDATE users SET active = 1'")
        self.assertEqual(code, 2)

    def test_update_with_where_allowed(self):
        code, _out, err = run("mysql -e 'UPDATE users SET active = 1 WHERE id = 5'")
        self.assertEqual(code, 0, err)

    def test_migrate_commands_exempt(self):
        code, _out, err = run("php artisan migrate:fresh --seed")
        self.assertEqual(code, 0, err)


class ChainAndWrapperTest(unittest.TestCase):
    def test_dangerous_second_command_in_chain_blocked(self):
        code, _out, _err = run("echo checking && git reset --hard HEAD")
        self.assertEqual(code, 2)

    def test_dangerous_command_after_semicolon_blocked(self):
        code, _out, _err = run("cd /tmp; rm -rf cache")
        self.assertEqual(code, 2)

    def test_command_substitution_checked(self):
        code, _out, _err = run("echo $(git reset --hard HEAD)")
        self.assertEqual(code, 2)

    def test_docker_exec_inner_command_checked(self):
        code, _out, _err = run("docker exec -it some_container git reset --hard HEAD")
        self.assertEqual(code, 2)

    def test_docker_exec_safe_inner_allowed(self):
        code, _out, err = run("docker exec -it some_container php artisan about")
        self.assertEqual(code, 0, err)

    def test_safe_chain_allowed(self):
        code, _out, err = run("git status && git diff --stat")
        self.assertEqual(code, 0, err)

    def test_non_bash_tool_ignored(self):
        code, _out, err = run_hook(MOD, {"tool_name": "Edit", "tool_input": {"file_path": "x"}})
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
