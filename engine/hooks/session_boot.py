#!/usr/bin/env python3
"""
SessionStart — emit the always-loaded ecosystem context.

This is the ALWAYS-LOADED guarantee: regardless of the task, every session
starts by surfacing the project's living state so the model never works blind.
Emits hookSpecificOutput.additionalContext containing:
  - project + profile (stack) name
  - first 40 lines of .memory/STATE.md + a stale warning if "Last validated"
    is more than 7 days old
  - open "- [ ]" counts in VERIFY.md and ISSUES.md
  - last 20 lines of the newest .memory/diary/*.md
  - git branch, dirty-file count, unpushed-commit count
  - the kit.json always_load list, with the instruction to Read each before
    substantive work

Fail-open: any error prints a short note and exits 0. Never blocks a session.
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import MEMORY_DIR, PROJECT_ROOT, load_kit


def read_lines(path, n=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines if n is None else lines[:n]
    except OSError:
        return []


def tail_lines(path, n):
    lines = read_lines(path)
    return lines[-n:] if lines else []


def count_open_checkboxes(path):
    return sum(1 for ln in read_lines(path) if re.match(r"\s*-\s*\[ \]", ln))


def stale_warning(state_lines):
    """If STATE.md carries a 'Last validated: YYYY-MM-DD' line older than 7
    days, return a warning string; else ''."""
    for ln in state_lines:
        m = re.search(r"Last validated:\s*(\d{4}-\d{2}-\d{2})", ln)
        if m:
            try:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - dt).days
                if age > 7:
                    return f"⚠️  STATE.md was last validated {age} days ago — run /state to revalidate."
            except ValueError:
                pass
            break
    return ""


def git(args):
    try:
        out = subprocess.run(
            ["git", "-C", PROJECT_ROOT] + args,
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def git_summary():
    # symbolic-ref fallback covers an unborn HEAD (fresh repo, no commits yet).
    branch = (
        git(["rev-parse", "--abbrev-ref", "HEAD"])
        or git(["symbolic-ref", "--short", "HEAD"])
        or "(unknown)"
    )
    dirty = len([ln for ln in git(["status", "--porcelain"]).splitlines() if ln.strip()])
    unpushed = ""
    upstream = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream:
        ahead = git(["rev-list", "--count", "@{u}..HEAD"])
        unpushed = ahead or "0"
    else:
        unpushed = "no upstream"
    return branch, dirty, unpushed


def newest_diary():
    files = sorted(glob.glob(os.path.join(MEMORY_DIR, "diary", "*.md")))
    return files[-1] if files else None


def build_context():
    kit = load_kit()
    parts = []
    parts.append(f"# Ecosystem context — {kit['project']} ({kit['stack']})")
    parts.append("")

    # STATE.md
    state_path = os.path.join(MEMORY_DIR, "STATE.md")
    state_lines = read_lines(state_path, 40)
    if state_lines:
        parts.append("## Current state (.memory/STATE.md, first 40 lines)")
        warn = stale_warning(read_lines(state_path))
        if warn:
            parts.append(warn)
        parts.append("".join(state_lines).rstrip())
        parts.append("")

    # Open work
    verify_open = count_open_checkboxes(os.path.join(MEMORY_DIR, "VERIFY.md"))
    issues_open = count_open_checkboxes(os.path.join(MEMORY_DIR, "ISSUES.md"))
    parts.append(f"## Open work: VERIFY {verify_open} unchecked · ISSUES {issues_open} unchecked")
    parts.append("")

    # Newest diary tail
    diary = newest_diary()
    if diary:
        parts.append(f"## Latest diary ({os.path.basename(diary)}, last 20 lines)")
        parts.append("".join(tail_lines(diary, 20)).rstrip())
        parts.append("")

    # Git
    branch, dirty, unpushed = git_summary()
    parts.append(f"## Git: branch `{branch}` · {dirty} dirty file(s) · {unpushed} unpushed commit(s)")
    parts.append("")

    # Always-load
    always = kit.get("always_load", [])
    if always:
        parts.append("## Always load before substantive work")
        parts.append("Read each of these now (they are the durable knowledge for this repo):")
        for p in always:
            parts.append(f"  - {p}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def main():
    # Drain the SessionStart payload (session_id/source) — every hook reads
    # stdin so `echo '<payload>' | python3 session_boot.py` works standalone.
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    context = build_context()
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ecosystem-kit] session_boot: {e}", file=sys.stderr)
        sys.exit(0)
