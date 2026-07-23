#!/usr/bin/env python3
"""PreToolUse:Bash + GitHub MCP write tools — protected branches belong to the OWNER.

Owner rule: Claude never merges into, rebases onto itself, or pushes to a
protected branch (kit.json `protected_branches`, default main/master), and
never merges pull requests. Defense-in-depth behind ~/.claude/bin/safe-push.

BLOCKING hook (listed in BLOCKING_HOOKS — fails CLOSED on engine errors).
Exit 2 = block (reason on stderr). Exit 0 = allow.

Bash checks:
  - `gh pr merge` — always blocked (PR merging is owner-only)
  - `git merge` / `git rebase` while the current branch is protected
    (--abort is allowed; chained `git checkout main && git merge x` is caught
    by tracking the effective branch through the command chain)
  - `git push` whose refspec targets a protected branch, including
    `origin main`, `HEAD:main`, `refs/heads/main`, `:main` (delete),
    `--delete origin main`, and a bare `git push` while on a protected branch

GitHub MCP checks (mirrors the machine-level guard_protected_branch.py):
  - *merge_pull_request — always blocked
  - *push_files / *create_or_update_file / *delete_file with a protected
    `branch` param — blocked
"""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import PROJECT_ROOT, load_kit

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")

MCP_WRITE_TOOLS = ("push_files", "create_or_update_file", "delete_file")

# git global flags that consume a following value.
GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--exec-path", "--namespace"}
# push flags that consume a following value.
PUSH_VALUE_FLAGS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_protected_merge] {msg}", file=sys.stderr)


def get_current_branch(cwd=None):
    """Current git branch, or '' when undeterminable (fail open on detection:
    explicit refspec targets are still guarded)."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd or PROJECT_ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def split_shell_commands(command):
    """Split on &&, ||, ; while respecting quotes (order preserved)."""
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


def tokenize(command):
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def parse_git(tokens):
    """Return (subcommand, args_after_subcommand) or (None, [])."""
    if not tokens or os.path.basename(tokens[0]) != "git":
        return None, []
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t in GIT_GLOBAL_VALUE_FLAGS:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        return t, tokens[i + 1:]
    return None, []


def _normalize_ref(ref):
    ref = ref.strip().lstrip("+")
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/"):]
    return ref


def push_targets(args):
    """Parse `git push` args. Returns (destination_branches, is_bare_push)."""
    positionals = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in PUSH_VALUE_FLAGS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        positionals.append(a)
        i += 1

    refspecs = positionals[1:] if positionals else []
    destinations = []
    for refspec in refspecs:
        dst = refspec.split(":", 1)[1] if ":" in refspec else refspec
        dst = _normalize_ref(dst)
        if dst and dst != "HEAD":
            destinations.append(dst)
    return destinations, len(refspecs) == 0


def branch_after_checkout(subcommand, args):
    """Effective branch after `git checkout`/`git switch`, or None if unchanged,
    or '' if unknown (detached / previous-branch shorthand)."""
    if subcommand == "checkout":
        if "--" in args:
            return None  # path checkout, branch unchanged
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-b", "-B", "--orphan"):
                return args[i + 1] if i + 1 < len(args) else ""
            if a.startswith("-"):
                i += 1
                continue
            if a in (".", "-"):
                return None if a == "." else ""
            return a
        return None
    if subcommand == "switch":
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-c", "-C", "--orphan"):
                return args[i + 1] if i + 1 < len(args) else ""
            if a == "--detach":
                return ""
            if a.startswith("-"):
                i += 1
                continue
            return "" if a == "-" else a
        return None
    return None


def check_bash_command(command, protected, current_branch):
    """Returns (blocked, reason)."""
    effective = (current_branch or "").strip().lower()

    for sub in split_shell_commands(command):
        if re.search(r"\bgh\s+pr\s+merge\b", sub):
            return True, (
                "BLOCKED by guard_protected_merge: merging pull requests is owner-only.\n"
                "Get the PR green and wait for the owner to merge."
            )

        tokens = tokenize(sub)
        subcommand, args = parse_git(tokens)
        if subcommand is None:
            continue

        if subcommand in ("checkout", "switch"):
            new_branch = branch_after_checkout(subcommand, args)
            if new_branch is not None:
                effective = _normalize_ref(new_branch).lower()
            continue

        if subcommand in ("merge", "rebase"):
            if "--abort" in args:
                continue
            if effective in protected:
                return True, (
                    f"BLOCKED by guard_protected_merge: `git {subcommand}` while on "
                    f"protected branch '{effective}'.\n"
                    f"Protected branches ({', '.join(sorted(protected))}) are owner-only: "
                    f"open a PR and let the owner merge."
                )
            continue

        if subcommand == "push":
            destinations, bare = push_targets(args)
            for dst in destinations:
                if dst.lower() in protected:
                    return True, (
                        f"BLOCKED by guard_protected_merge: push targets protected "
                        f"branch '{dst}'.\n"
                        f"Push to a work branch and open a PR — the owner merges/pushes "
                        f"{', '.join(sorted(protected))}."
                    )
            if bare and effective in protected:
                return True, (
                    f"BLOCKED by guard_protected_merge: bare `git push` while on "
                    f"protected branch '{effective}'.\n"
                    f"Switch to a work branch first."
                )
            continue

    return False, ""


def check_mcp_tool(tool_name, tool_input, protected):
    """GitHub MCP write tools targeting protected branches. Returns (blocked, reason)."""
    if tool_name.endswith("merge_pull_request"):
        return True, (
            "BLOCKED by guard_protected_merge: merging pull requests is owner-only.\n"
            "Get the PR green and wait for the owner to merge."
        )

    if tool_name.endswith(MCP_WRITE_TOOLS):
        branch = str((tool_input or {}).get("branch", "")).strip().lower()
        if branch in protected:
            return True, (
                f"BLOCKED by guard_protected_merge: direct writes to '{branch}' via the "
                f"GitHub API are owner-only.\n"
                f"Push to a work branch and open a PR instead."
            )

    return False, ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    kit = load_kit()
    protected = {str(b).strip().lower() for b in (kit.get("protected_branches") or ["main", "master"])}

    if "github__" in tool_name:
        blocked, reason = check_mcp_tool(tool_name, payload.get("tool_input") or {}, protected)
        if blocked:
            print(reason, file=sys.stderr)
            sys.exit(2)
        sys.exit(0)

    if tool_name != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Fast path: nothing git/gh related.
    if not re.search(r"\b(git|gh)\b", command):
        sys.exit(0)
    if not re.search(r"\b(merge|rebase|push|checkout|switch)\b", command):
        sys.exit(0)

    current_branch = get_current_branch(payload.get("cwd"))
    blocked, reason = check_bash_command(command, protected, current_branch)
    if blocked:
        print(reason, file=sys.stderr)
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
