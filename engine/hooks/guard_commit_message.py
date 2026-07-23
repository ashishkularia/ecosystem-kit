#!/usr/bin/env python3
"""PostToolUse:Bash — advisory conventional-commit message checks.

ALWAYS exits 0 (advisory). Prints warnings to stdout when a `git commit`
message deviates from conventions:
  - Conventional format: type(scope): description
  - Valid types come from _constants.VALID_COMMIT_TYPES
  - Subject line <= 72 characters
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import VALID_COMMIT_TYPES

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_commit_message] {msg}", file=sys.stderr)


CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<type>\w+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r":\s+"
    r"(?P<description>.+)$"
)


def extract_commit_message(command):
    """Extract the message from `git commit -m ...` / heredoc form."""
    heredoc = re.search(r"cat\s+<<['\"]?EOF['\"]?\s*\n(.*?)\nEOF", command, re.DOTALL)
    if heredoc:
        return heredoc.group(1).strip()

    m = re.search(r'-m\s+["\'](.+?)["\']', command, re.DOTALL)
    if m:
        return m.group(1).strip()

    m = re.search(r"-m\s+(\S+)", command)
    if m:
        return m.group(1).strip()

    return None


def check_commit_message(message):
    """Returns a list of warning strings (may be empty)."""
    warnings = []
    lines = message.split("\n")
    subject = lines[0].strip() if lines else ""

    if not subject:
        return ["  WARNING: empty commit message subject line."]

    match = CONVENTIONAL_COMMIT_RE.match(subject)
    if not match:
        warnings.append(
            "  WARNING: subject does not follow conventional commit format.\n"
            "    Expected: type(scope): description\n"
            f"    Got: {subject}\n"
            f"    Valid types: {', '.join(sorted(VALID_COMMIT_TYPES))}"
        )
    elif match.group("type") not in VALID_COMMIT_TYPES:
        warnings.append(
            f"  WARNING: invalid commit type '{match.group('type')}'.\n"
            f"    Valid types: {', '.join(sorted(VALID_COMMIT_TYPES))}"
        )

    if len(subject) > 72:
        warnings.append(
            f"  WARNING: subject line is {len(subject)} characters (max 72).\n"
            f"    Subject: {subject[:72]}..."
        )

    return warnings


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command or not re.search(r"\bgit\s+commit\b", command):
        sys.exit(0)

    message = extract_commit_message(command)
    if not message:
        sys.exit(0)

    warnings = check_commit_message(message)
    if warnings:
        print("=" * 60)
        print("Commit Message Advisory")
        print("=" * 60)
        for w in warnings:
            print(w)
        print("=" * 60)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Advisory: fail OPEN.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e} — allowing (advisory hook).", file=sys.stderr)
        sys.exit(0)
