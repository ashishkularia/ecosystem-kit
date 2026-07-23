#!/usr/bin/env python3
"""PreToolUse:Edit|Write — block writing content that contains secrets.

BLOCKING hook (listed in BLOCKING_HOOKS — fails CLOSED on engine errors).
Exit 2 = block (reason on stderr). Exit 0 = allow.

Scans (patterns live in _constants.py):
  - AWS access keys, sk-prefixed API keys, generic api_key assignments
  - Private key headers, JWT tokens, GitHub/Stripe/Cloudflare tokens
  - Database URLs with inline credentials, Bearer tokens
  - Hardcoded passwords / secrets (placeholder values like "password",
    "changeme", "example" and templated values like "${VAR}" are allowed)

Skipped files: .env.example / .env.sample, test directories, markdown.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import (
    ALLOWED_PASSWORD_VALUES,
    GENERIC_SECRET_PATTERN as _GENERIC_SECRET_PATTERN_STR,
    PASSWORD_PATTERN as _PASSWORD_PATTERN_STR,
    SECRET_PATTERNS,
)

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG secret_scanner] {msg}", file=sys.stderr)


PASSWORD_PATTERN = re.compile(_PASSWORD_PATTERN_STR, re.IGNORECASE)
GENERIC_SECRET_PATTERN = re.compile(_GENERIC_SECRET_PATTERN_STR, re.IGNORECASE)


def _is_placeholder(value):
    """Values that are clearly placeholders/templates, not real secrets."""
    v = value.strip()
    if v.lower() in ALLOWED_PASSWORD_VALUES:
        return True
    # Env interpolation / template syntax: ${VAR}, $VAR, {{ var }}, <value>, %VAR%
    if v.startswith(("$", "{{", "<", "%")):
        return True
    return False


def scan_for_secrets(content):
    """Return a list of finding descriptions (empty when clean)."""
    matches = []

    for name, pattern, description in SECRET_PATTERNS:
        if re.search(pattern, content):
            matches.append(f"{name}: {description}")

    for m in PASSWORD_PATTERN.finditer(content):
        if not _is_placeholder(m.group(1)):
            matches.append("Password: hardcoded password detected")

    for m in GENERIC_SECRET_PATTERN.finditer(content):
        if not _is_placeholder(m.group(1)):
            matches.append("Generic secret: hardcoded secret value detected (length >= 8)")

    return matches


def should_skip_file(file_path):
    """Files exempt from scanning (templates, tests, docs)."""
    normalized = file_path.replace("\\", "/")
    basename = os.path.basename(normalized)

    if basename in (".env.example", ".env.sample"):
        return True

    for marker in ("/tests/", "/test/", "/__tests__/"):
        if marker in normalized:
            return True
    if normalized.startswith(("tests/", "test/")):
        return True

    if basename.endswith(".md"):
        return True

    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    if should_skip_file(file_path):
        debug(f"Skipping exempt file: {file_path}")
        sys.exit(0)

    if tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        content = tool_input.get("new_string", "")
    if not content:
        sys.exit(0)

    matches = scan_for_secrets(content)
    if matches:
        lines = [
            "=" * 60,
            f"BLOCKED: Secrets detected — {os.path.basename(file_path)}",
            "=" * 60,
        ]
        lines.extend(f"  {m}" for m in matches)
        lines.append(f"File: {file_path}")
        lines.append("Remove hardcoded secrets; load them from the environment instead.")
        lines.append("=" * 60)
        print("\n".join(lines), file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Blocking hook: fail CLOSED.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e}", file=sys.stderr)
        print("Blocking operation as a safety precaution.", file=sys.stderr)
        sys.exit(2)
