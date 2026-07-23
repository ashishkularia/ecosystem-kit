#!/usr/bin/env python3
"""PreToolUse:Bash — branch naming conventions + protected-branch creation guard.

Two behaviours:
  1. BLOCK (exit 2): creating a branch named exactly like a protected branch
     (kit.json `protected_branches`, default main/master). Protected branches
     are never creatable by the agent.
  2. ADVISORY (exit 0 + message): new/pushed branch names should follow
     `{type}/{kebab-case-description}` where type comes from kit.json
     `branch_types`.

Covers: git checkout -b/-B, git switch -c/-C, git branch <name>, git push
refspecs. Chained commands are split and each part checked.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import load_kit

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")

# Branches exempt from the type/description convention (long-lived branches).
CONVENTION_EXEMPT = {"develop", "staging", "release"}


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_branch_naming] {msg}", file=sys.stderr)


def split_shell_commands(command):
    """Split on &&, ||, ; while respecting quotes."""
    commands = []
    current = []
    in_single = False
    in_double = False
    i = 0
    while i < len(command):
        c = command[i]
        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
            continue
        if not in_single and not in_double:
            if i + 1 < len(command) and command[i:i + 2] in ("&&", "||"):
                cmd = "".join(current).strip()
                if cmd:
                    commands.append(cmd)
                current = []
                i += 2
                continue
            if c == ";":
                cmd = "".join(current).strip()
                if cmd:
                    commands.append(cmd)
                current = []
                i += 1
                continue
        current.append(c)
        i += 1
    cmd = "".join(current).strip()
    if cmd:
        commands.append(cmd)
    return commands


def extract_created_branch(command):
    """Branch name being CREATED by this command, or None."""
    cmd = command.strip()

    m = re.search(r"git\s+(?:checkout\s+-[bB]|switch\s+-[cC])\s+(\S+)", cmd)
    if m:
        return m.group(1)

    # git branch <name> — creation form only (not -d/-D/-m/--list/…).
    m = re.search(r"git\s+branch\s+(?!-)(\S+)\s*$", cmd)
    if m:
        return m.group(1)

    return None


def extract_pushed_branches(command):
    """Branch names being pushed (refspec src side), for advisory checks."""
    cmd = command.strip()
    if not re.search(r"\bgit\s+push\b", cmd):
        return []

    tokens = cmd.split()
    try:
        push_idx = tokens.index("push")
    except ValueError:
        return []

    positionals = []
    i = push_idx + 1
    while i < len(tokens):
        t = tokens[i]
        if t in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        positionals.append(t)
        i += 1

    branches = []
    for refspec in positionals[1:]:  # positionals[0] is the remote
        src = refspec.split(":", 1)[0].lstrip("+")
        if not src or src == "HEAD":
            continue
        if src.startswith("refs/heads/"):
            src = src[len("refs/heads/"):]
        branches.append(src)
    return branches


def strip_remote_prefix(branch):
    if "/" in branch:
        head, rest = branch.split("/", 1)
        if head in ("origin", "upstream"):
            return rest
    return branch


def validate_branch_name(branch, branch_types, protected):
    """Returns (valid, message). Protected/exempt names skip the convention."""
    branch = strip_remote_prefix(branch)
    if branch in protected or branch in CONVENTION_EXEMPT:
        return True, ""

    pattern = re.compile(
        r"^(?P<type>" + "|".join(re.escape(t) for t in branch_types) + r")"
        r"/(?P<description>[a-z0-9]+(?:-[a-z0-9]+)*)$"
    )
    if pattern.match(branch):
        return True, ""

    valid_types = ", ".join(f"{t}/" for t in branch_types)
    return False, (
        f"ADVISORY: branch name '{branch}' does not follow the naming convention.\n"
        f"  Expected: {{type}}/{{kebab-case-description}}\n"
        f"  Valid types: {valid_types}\n"
        f"  Examples: {branch_types[0]}/add-widget, fix/login-redirect-bug"
        if branch_types else
        f"ADVISORY: branch name '{branch}' — no branch_types configured in kit.json."
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    if not re.search(r"\bgit\s+(push|checkout|switch|branch)\b", command):
        sys.exit(0)

    kit = load_kit()
    branch_types = list(kit.get("branch_types") or [])
    protected = {str(b).strip().lower() for b in (kit.get("protected_branches") or ["main", "master"])}

    advisories = []
    for sub in split_shell_commands(command):
        created = extract_created_branch(sub)
        if created:
            plain = strip_remote_prefix(created).strip().lower()
            if plain in protected:
                print(
                    f"BLOCKED: '{plain}' is a protected branch and is never creatable.\n"
                    f"  Protected branches ({', '.join(sorted(protected))}) belong to the owner.\n"
                    f"  Create a work branch instead, e.g. "
                    f"{(branch_types[0] + '/short-description') if branch_types else 'feature/short-description'}.",
                    file=sys.stderr,
                )
                sys.exit(2)
            valid, message = validate_branch_name(created, branch_types, protected)
            if not valid:
                advisories.append(message)

        for pushed in extract_pushed_branches(sub):
            valid, message = validate_branch_name(pushed, branch_types, protected)
            if not valid:
                advisories.append(message)

    if advisories:
        print("=" * 60)
        for msg in advisories:
            print(msg)
        print("=" * 60)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Not a BLOCKING hook: fail OPEN on internal errors.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e} — allowing (fail-open).", file=sys.stderr)
        sys.exit(0)
