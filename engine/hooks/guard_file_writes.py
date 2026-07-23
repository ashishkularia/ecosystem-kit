#!/usr/bin/env python3
"""PreToolUse:Edit|Write — block writes to files that must never be hand-edited.

Exit 2 = block (reason on stderr). Exit 0 = allow (warnings on stdout).
Not in BLOCKING_HOOKS: an internal crash fails OPEN, but pattern matches
still block with exit 2.

Always blocked (project-agnostic defaults):
  - .env and .env.* variants (except .env.example / .env.sample)
  - credential material: credentials.json, ~/.aws/, ~/.ssh/, *.pem, *.key
  - lockfiles by hand: package-lock.json, yarn.lock, pnpm-lock.yaml,
    composer.lock, Cargo.lock, poetry.lock, uv.lock, Gemfile.lock, Pipfile.lock
  - dependency/VCS internals: node_modules/, vendor/, .git/
  - .claude/settings.local.json (per-machine, untracked)

Config-extensible via kit.json (optional key, safe when absent):
    "file_write_rules": {
        "blocked": [["<regex>", "<reason>"], "<regex>", ...],
        "allowed": ["<regex>", ...]        # exceptions that override blocks
    }

Advisory warnings (never block): CLAUDE.md, docker-compose.yml,
migrations/, .claude/settings.json.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import PROJECT_ROOT, PROTECTED_FILES, load_kit

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_file_writes] {msg}", file=sys.stderr)


BLOCKED_PATTERNS = [
    (r"(^|/)\.env$", "Writing to .env files is blocked. Use .env.example for templates."),
    (r"(^|/)\.env\.[A-Za-z0-9_.-]+$", "Writing to .env variant files is blocked. Use .env.example for templates."),
    (r"credentials\.json$", "Writing to credentials files is blocked."),
    (r"(^|/)\.aws/", "Writing to the AWS credentials directory is blocked."),
    (r"(^|/)\.ssh/", "Writing to the SSH directory is blocked."),
    (r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|composer\.lock|Cargo\.lock|poetry\.lock|uv\.lock|Gemfile\.lock|Pipfile\.lock)$",
     "Lockfiles are generated — never hand-edit. Run the package manager instead."),
    (r"(^|/)node_modules/", "Writing to node_modules/ is blocked. Use the package manager instead."),
    (r"(^|/)vendor/", "Writing to vendor/ is blocked. Use the package manager instead."),
    (r"(^|/)\.git/", "Writing inside .git/ is blocked."),
    (r"\.pem$", "Writing .pem key files is blocked."),
    (r"\.key$", "Writing .key files is blocked."),
]

ALLOWED_EXCEPTIONS = [
    r"\.env\.example$",
    r"\.env\.sample$",
    r"resources/views/vendor/",  # published package views, not a package dir
]

WARNING_PATTERNS = [
    (r"(^|/)CLAUDE\.md$",
     "You are modifying CLAUDE.md — the always-loaded durable-policy file.\n"
     "  Ensure changes are intentional; knowledge belongs in .memory/."),
    (r"(^|/)docker-compose\.ya?ml$",
     "You are modifying docker-compose directly.\n"
     "  Consider a docker-compose.override for local-only changes."),
    (r"(^|/)migrations/.+",
     "You are modifying a migration file.\n"
     "  Migrations that have already run must NOT be edited — create a new one."),
    (r"(^|/)\.claude/settings\.json$",
     "You are modifying hook wiring (.claude/settings.json).\n"
     "  Run the kit health-check afterwards to validate the wiring."),
]


def normalize_path(file_path):
    """Make the path repo-relative when inside PROJECT_ROOT."""
    path = file_path.replace("\\", "/")
    root = str(PROJECT_ROOT).replace("\\", "/").rstrip("/")
    if root and path.startswith(root + "/"):
        path = path[len(root) + 1:]
    if path.startswith("./"):
        path = path[2:]
    return path


def _kit_rules():
    """Extra blocked/allowed patterns from kit.json (optional key)."""
    rules = load_kit().get("file_write_rules") or {}
    blocked = []
    for entry in rules.get("blocked") or []:
        if isinstance(entry, str):
            blocked.append((entry, "Blocked by kit.json file_write_rules."))
        elif isinstance(entry, (list, tuple)) and entry:
            reason = entry[1] if len(entry) > 1 else "Blocked by kit.json file_write_rules."
            blocked.append((str(entry[0]), str(reason)))
    allowed = [str(p) for p in (rules.get("allowed") or [])]
    return blocked, allowed


def is_exception(path, extra_allowed):
    for pattern in ALLOWED_EXCEPTIONS + extra_allowed:
        try:
            if re.search(pattern, path):
                return True
        except re.error:
            continue
    return False


def check_blocked(path, extra_blocked):
    protected_exact = [(re.escape(p) + r"$", f"{p} is per-machine/protected — never written by the agent.")
                       for p in PROTECTED_FILES]
    for pattern, reason in BLOCKED_PATTERNS + protected_exact + extra_blocked:
        try:
            if re.search(pattern, path):
                return True, reason
        except re.error:
            continue
    return False, ""


def check_warnings(path):
    return [msg for pattern, msg in WARNING_PATTERNS if re.search(pattern, path)]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if not file_path:
        sys.exit(0)

    normalized = normalize_path(file_path)
    extra_blocked, extra_allowed = _kit_rules()

    if is_exception(normalized, extra_allowed):
        sys.exit(0)

    blocked, reason = check_blocked(normalized, extra_blocked)
    if blocked:
        print(
            f"BLOCKED: file write not allowed.\n"
            f"  File: {file_path}\n"
            f"  Reason: {reason}",
            file=sys.stderr,
        )
        sys.exit(2)

    warnings = check_warnings(normalized)
    if warnings:
        print(f"File Write Advisory — {os.path.basename(file_path)}")
        for w in warnings:
            print(f"  WARNING: {w}")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Not a BLOCKING hook: fail OPEN on internal errors.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e} — allowing (fail-open).", file=sys.stderr)
        sys.exit(0)
