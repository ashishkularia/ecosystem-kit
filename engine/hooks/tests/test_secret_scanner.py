#!/usr/bin/env python3
"""Tests for secret_scanner — blocking hook, fails closed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import _support
from _support import edit_payload, run_hook, write_payload

MOD = _support.load_hook("secret_scanner")

# Assembled at runtime so this test file itself never contains a
# secret-shaped literal.
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
FAKE_SK_KEY = "sk-" + "abcdefghijklmnop1234"
FAKE_DB_URL = "mysql://appuser:s3cretpass@db.internal:3306/app"


class BlockingTest(unittest.TestCase):
    def test_aws_key_blocked(self):
        payload = write_payload("/repo/src/config.php", f"$key = '{FAKE_AWS_KEY}';")
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 2)
        self.assertIn("AWS", err)

    def test_sk_api_key_blocked(self):
        payload = write_payload("/repo/src/client.py", f'API_KEY = "{FAKE_SK_KEY}"')
        code, _out, _err = run_hook(MOD, payload)
        self.assertEqual(code, 2)

    def test_database_url_with_credentials_blocked(self):
        payload = write_payload("/repo/src/db.py", f'URL = "{FAKE_DB_URL}"')
        code, _out, _err = run_hook(MOD, payload)
        self.assertEqual(code, 2)

    def test_real_password_blocked(self):
        payload = write_payload("/repo/src/settings.py", 'password = "hunter2secret!"')
        code, _out, _err = run_hook(MOD, payload)
        self.assertEqual(code, 2)

    def test_edit_new_string_scanned(self):
        payload = edit_payload("/repo/src/client.ts", f'const k = "{FAKE_SK_KEY}";')
        code, _out, _err = run_hook(MOD, payload)
        self.assertEqual(code, 2)


class AllowedTest(unittest.TestCase):
    def test_clean_content_allowed(self):
        payload = write_payload("/repo/src/math.py", "def add(a, b):\n    return a + b\n")
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 0, err)

    def test_placeholder_password_allowed(self):
        payload = write_payload("/repo/src/settings.py", 'password = "password"')
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 0, err)

    def test_env_interpolated_password_allowed(self):
        payload = write_payload("/repo/config/database.php", "password = \"${DB_PASSWORD}\"")
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 0, err)

    def test_env_example_skipped(self):
        payload = write_payload("/repo/.env.example", f"AWS_KEY={FAKE_AWS_KEY}")
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 0, err)

    def test_test_directory_skipped(self):
        payload = write_payload("/repo/tests/Feature/AuthTest.php", f"$key = '{FAKE_AWS_KEY}';")
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 0, err)

    def test_markdown_skipped(self):
        payload = write_payload("/repo/docs/security.md", f"Example key: {FAKE_AWS_KEY}")
        code, _out, err = run_hook(MOD, payload)
        self.assertEqual(code, 0, err)

    def test_non_edit_write_tool_ignored(self):
        code, _out, err = run_hook(MOD, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
