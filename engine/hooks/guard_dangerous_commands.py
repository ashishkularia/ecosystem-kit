#!/usr/bin/env python3
"""PreToolUse:Bash — block destructive commands before they run.

BLOCKING hook (listed in BLOCKING_HOOKS — fails CLOSED on engine errors).
Exit 2 = block (reason on stderr). Exit 0 = allow.

Checks (project-agnostic; patterns live in _constants.py):
  - Destructive git operations (force push, hard reset, clean, checkout/restore .)
  - Staging secrets or env files (git add .env / -A / --all / .)
  - Destructive filesystem operations (rm -rf, chmod 777) — except `rm -rf`
    of literal paths strictly inside .claude/scratch/, and only when the whole
    command line is nothing but such removals (see scratch_cleanup_only)
  - Destructive database operations, incl. WHERE-less DELETE/UPDATE
  - Chained commands (&&, ||, ;) are split and each sub-command is checked
  - $(...) and backtick substitutions are extracted and checked
  - docker exec inner commands are extracted and checked (no container names
    are assumed — whatever container the command targets, the inner command
    is held to the same rules)
  - Filesystem/git patterns match with quoted spans blanked out, so a commit
    message that merely MENTIONS `rm -rf` does not block; SQL and env-staging
    patterns keep the raw string (quoted SQL / quoted paths are the normal
    invocation shapes there)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import (
    DB_DESTRUCTIVE_PATTERNS,
    DESTRUCTIVE_FILESYSTEM_PATTERNS,
    DESTRUCTIVE_GIT_CASE_SENSITIVE,
    DESTRUCTIVE_GIT_PATTERNS,
    ENV_STAGING_PATTERNS,
    PROJECT_ROOT,
    SCRATCH_DIR,
    split_shell_commands,
)

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_dangerous_commands] {msg}", file=sys.stderr)




def extract_docker_exec_command(command):
    """Extract the inner command from `docker exec [flags] <container> <cmd...>`.

    Returns the inner command string, or None if not a docker exec command.
    """
    pattern = r"^docker\s+exec\s+((?:-{1,2}[\w-]+(?:[= ]\S+)?\s+)*)(\S+)\s+(.+)$"
    match = re.match(pattern, command.strip())
    if match:
        inner = match.group(3).strip()
        debug(f"Extracted docker exec inner command: {inner}")
        return inner
    return None


def blank_quoted_spans(command):
    """Replace the CONTENT of single/double-quoted spans with spaces.

    Used for the filesystem/git checks only, so a commit message or echo text
    that merely MENTIONS a dangerous command (`git commit -m "rm -rf docs"`)
    is not blocked. The SQL checks deliberately keep the raw string — quoted
    SQL (`mysql -e "DELETE FROM users"`) is the normal invocation shape — and
    so does env-staging (`git add ".env"` must still match).
    """
    out = []
    quote = None
    for c in command:
        if quote:
            if c == quote:
                quote = None
                out.append(c)
            else:
                out.append(" ")
        elif c in ("'", '"'):
            quote = c
            out.append(c)
        else:
            out.append(c)
    return "".join(out)


# The ONLY shape of command the scratch exemption recognises: `rm`, a few
# harmless flags, then operands made of a tiny alphabet. Every shell
# metacharacter (quotes, $ ` * ? [ { ~ ! # \ < > | & ( ) and whitespace other
# than space/tab) is outside it, so what this regex parses is exactly what the
# shell will run — there is no second reading of the line to be fooled by.
# Operands may not start with "-" (they would be flags).
_SCRATCH_RM_RE = re.compile(
    r"^rm(?:[ \t]+(?:-[rRfv]+|--recursive|--force|--verbose))*"
    r"(?:[ \t]+--)?"
    r"((?:[ \t]+[A-Za-z0-9_./][A-Za-z0-9_./-]*)+)$"
)


def scratch_cleanup_only(command, cwd=None):
    """True only when the WHOLE command line is `rm` of literal paths strictly
    inside this project's scratch directory (SCRATCH_DIR).

    Why the whole line and not each sub-command: the guard checks sub-commands
    independently and before any of them runs, so `ln -s ~ .claude/scratch/l &&
    rm -rf .claude/scratch/l/Documents` would pass a per-command path check —
    the link does not exist yet. If every part must itself be a scratch `rm`,
    nothing in the line can create, move or redirect anything.

    Refuses (returns False) on: the scratch root itself, `..` segments, any path
    whose real location (symlinks resolved) falls outside <root>/.claude/scratch,
    and any exception — an error here must only ever lose the exemption, never
    grant it. That target is deliberately NOT resolved: if `.claude` or `scratch`
    is itself a symlink, every operand resolves elsewhere and fails containment,
    so a scratch directory pointed at ~ can never launder a deletion.
    """
    try:
        if "\n" in command or "\r" in command:
            return False
        scratch = os.path.join(os.path.realpath(PROJECT_ROOT), SCRATCH_DIR)
        base = os.path.realpath(cwd or os.getcwd())
        for part in re.split(r"[ \t]*(?:&&|;)[ \t]*", command.strip()):
            match = _SCRATCH_RM_RE.match(part)
            if not match:
                return False
            for operand in match.group(1).split():
                if ".." in operand.split("/"):
                    return False
                path = operand if operand.startswith("/") else os.path.join(base, operand)
                if not os.path.realpath(path).startswith(scratch + os.sep):
                    return False
        return True
    except Exception as e:
        debug(f"scratch_cleanup_only failed closed to 'not exempt': {e}")
        return False


def check_command(command, fs_exempt=False):
    """Check one command string against all destructive patterns.

    fs_exempt skips ONLY the destructive-filesystem patterns; it is set by
    main() when scratch_cleanup_only() vouched for the whole command line.

    Returns (blocked, reason).
    """
    cmd = command.strip()
    # Filesystem/git patterns match against the quote-blanked form (see
    # blank_quoted_spans); SQL and env-staging patterns match the raw form.
    cmd_unquoted = blank_quoted_spans(cmd)

    for pattern in DESTRUCTIVE_GIT_PATTERNS:
        if re.search(pattern, cmd_unquoted, re.IGNORECASE):
            return True, (
                f"BLOCKED: Destructive git operation.\n"
                f"Command: {command}\n"
                f"Pattern: {pattern}"
            )

    for pattern in DESTRUCTIVE_GIT_CASE_SENSITIVE:
        if re.search(pattern, cmd_unquoted):
            return True, (
                f"BLOCKED: Destructive git operation.\n"
                f"Command: {command}\n"
                f"Pattern: {pattern}"
            )

    for pattern in ENV_STAGING_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            # Adding .gitignore itself is fine.
            if ".gitignore" in cmd:
                continue
            return True, (
                f"BLOCKED: Staging secrets/env files or blanket-staging.\n"
                f"Command: {command}\n"
                f"Use `git add <specific-files>` instead."
            )

    for pattern in ([] if fs_exempt else DESTRUCTIVE_FILESYSTEM_PATTERNS):
        if re.search(pattern, cmd_unquoted):
            return True, (
                f"BLOCKED: Destructive filesystem operation.\n"
                f"Command: {command}\n"
                f"Pattern: {pattern}"
            )

    for pattern in DB_DESTRUCTIVE_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            # Migration tooling legitimately drops/truncates.
            if re.search(r"\bmigrate\b", cmd, re.IGNORECASE):
                continue
            return True, (
                f"BLOCKED: Destructive database operation.\n"
                f"Command: {command}"
            )

    # UPDATE without WHERE clause.
    if re.search(r"\bUPDATE\s+\w+\s+SET\b", cmd, re.IGNORECASE):
        if not re.search(r"\bWHERE\b", cmd, re.IGNORECASE):
            return True, (
                f"BLOCKED: UPDATE without WHERE clause.\n"
                f"Command: {command}\n"
                f"Add a WHERE clause to avoid updating all rows."
            )

    # DELETE without WHERE clause (same shape as the UPDATE rule — no
    # end-anchor, so `mysql -e "DELETE FROM users"` is caught even though the
    # closing quote follows the table name).
    if re.search(r"\bDELETE\s+FROM\s+\w+", cmd, re.IGNORECASE):
        if not re.search(r"\bWHERE\b", cmd, re.IGNORECASE):
            if not re.search(r"\bmigrate\b", cmd, re.IGNORECASE):
                return True, (
                    f"BLOCKED: DELETE without WHERE clause.\n"
                    f"Command: {command}\n"
                    f"Add a WHERE clause to avoid deleting all rows."
                )

    return False, ""


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

    sub_commands = split_shell_commands(command)
    to_check = list(sub_commands)
    for sub in sub_commands:
        inner = extract_docker_exec_command(sub)
        if inner:
            to_check.append(inner)
            inner_subs = split_shell_commands(inner)
            if len(inner_subs) > 1:
                to_check.extend(inner_subs)

    fs_exempt = scratch_cleanup_only(command, payload.get("cwd"))
    for cmd in to_check:
        blocked, reason = check_command(cmd, fs_exempt=fs_exempt)
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
