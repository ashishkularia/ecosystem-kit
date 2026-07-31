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


# A closed entry in the drifted (non-checkbox) format, e.g. "Status: RESOLVED
# 2026-07-08" or "Status: DONE". Case-SENSITIVE on purpose: these are shouted
# status markers, whereas lowercase prose ("clearance not done") means the
# entry is still open. "PARTIALLY RESOLVED" is likewise still open work.
DRIFT_CLOSED_RE = re.compile(
    r"(?<!PARTIALLY )\b(RESOLVED|DONE|CLOSED|FIXED|WONTFIX|OBSOLETE|DROPPED)\b")
DRIFT_ENTRY_RE = re.compile(r"-\s*(?:\*\*)?\d{4}-\d{2}-\d{2}")


def count_open_entries(path):
    """Count open entries; returns (count, drifted).

    The kit convention is `- [ ]` checkboxes, but repos drift to plain dated
    bullets (`- YYYY-MM-DD — ...`) and a checkbox-only counter then reports a
    misleading 0 at every session start (meritick, 2026-08-01 hygiene). When
    no checkboxes exist, count unresolved dated bullets and flag the drift.

    Drifted entries are counted per ENTRY, not per line: an entry runs from its
    dated bullet to the next one, and a closure marker anywhere inside it
    (often on a continuation line) closes it. The bullet pattern anchors at
    column 0 so the quoted mid-line examples in the kit's .memory templates are
    never counted."""
    lines = read_lines(path)
    boxes = sum(1 for ln in lines if re.match(r"\s*-\s*\[ \]", ln))
    if boxes:
        return boxes, False

    open_count = 0
    total = 0
    entry = None  # text of the entry being accumulated, or None outside one
    for ln in lines:
        if DRIFT_ENTRY_RE.match(ln):
            if entry is not None:
                total += 1
                open_count += 0 if DRIFT_CLOSED_RE.search(entry) else 1
            entry = ln
        elif entry is not None:
            if ln.strip() and not ln.startswith((" ", "\t")):
                # Back to column-0 prose: the entry block has ended.
                total += 1
                open_count += 0 if DRIFT_CLOSED_RE.search(entry) else 1
                entry = None
            else:
                entry += ln
    if entry is not None:
        total += 1
        open_count += 0 if DRIFT_CLOSED_RE.search(entry) else 1
    return open_count, total > 0


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
    def open_work_label(path):
        n, drifted = count_open_entries(path)
        if drifted:
            return f"{n} open ⚠ non-checkbox entries — kit format is \"- [ ]\""
        return f"{n} unchecked"
    verify_label = open_work_label(os.path.join(MEMORY_DIR, "VERIFY.md"))
    issues_label = open_work_label(os.path.join(MEMORY_DIR, "ISSUES.md"))
    parts.append(f"## Open work: VERIFY {verify_label} · ISSUES {issues_label}")
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
