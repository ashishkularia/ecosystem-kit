#!/usr/bin/env python3
"""
docs_contract — v2 of the documentation contract.

The ecosystem describes the codebase; nothing forces the description to follow
the code. This hook closes that loop with a two-phase mechanism:

PostToolUse (Edit|Write):
  If the edited file matches a profile ``source_patterns`` regex, record a
  pending "code_change" flag in .memory/cache/pending.json and print a
  one-line reminder. Flag names are accepted GENERICALLY, so /decide and
  /idea style flows can drop "decision"/"discussion" flags the same way.

Stop:
  If pending flags exist, BLOCK the stop until (a) each flag's roster file has
  an mtime newer than the flag timestamp, AND (b) when kit.diary is on, today's
  diary entry exists and was touched after the session's first flag. Satisfied
  flags are cleared as their roster files catch up, but first_flag_ts is kept
  until BOTH conditions hold, so the diary gate survives flag clearance.
  Loop-guarded via stop_hook_active so it can never wedge a session.

CLI (for command flows — /decide, /idea, ...):
  python3 .claude/hooks/docs_contract.py flag <name> [example]
  drops a generic pending flag (e.g. "decision", "discussion").

Roster mapping:
  code_change -> .memory/CHANGELOG.md
  decision    -> .memory/DECISIONS.md
  discussion  -> newest .memory/diary/*.md

This hook is in BLOCKING_HOOKS: engine-level crashes fail CLOSED.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import MEMORY_DIR, PROJECT_ROOT, load_kit

CACHE_DIR = os.path.join(MEMORY_DIR, "cache")
PENDING_FILE = os.path.join(CACHE_DIR, "pending.json")

FLAG_ROSTER = {
    "code_change": "CHANGELOG.md",
    "decision": "DECISIONS.md",
    # "discussion" resolves to the diary, handled specially.
}


def normalize_path(path: str) -> str:
    path = path.replace("\\", "/")
    root = PROJECT_ROOT.replace("\\", "/").rstrip("/") + "/"
    if path.startswith(root):
        path = path[len(root):]
    if path.startswith("./"):
        path = path[2:]
    return path


def matches_source(path: str) -> bool:
    kit = load_kit()
    for pat in kit.get("source_patterns", []):
        try:
            if re.search(pat, path):
                return True
        except re.error:
            continue
    return False


def load_pending() -> dict:
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("flags"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"flags": {}, "first_flag_ts": None}


def save_pending(data: dict) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def set_flag(name: str, example: str = "") -> None:
    data = load_pending()
    now = time.time()
    if name not in data["flags"]:
        data["flags"][name] = {"ts": now, "example": example}
    if data.get("first_flag_ts") is None:
        data["first_flag_ts"] = now
    save_pending(data)


def mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def touched_since(path: str, after_ts: float) -> bool:
    """Was `path` written at or after `after_ts`?

    Compared at WHOLE-SECOND resolution, and inclusively. Filesystem mtime
    granularity is not guaranteed finer than one second (it is exactly 1s on
    several filesystems), so a strict float comparison calls a file written
    milliseconds AFTER the flag "older" and blocks someone who did the work —
    which is precisely the fast path, since recording a decision and writing
    the diary in the same turn happens in well under a second. The cost is a
    sub-second window where a diary written just BEFORE the flag counts; that
    is a far better failure than a gate that fires on correct behavior."""
    m = mtime(path)
    return m > 0 and int(m) >= int(after_ts)


def current_branch() -> str:
    """Current git branch, or "" when detached/not a repo (callers fall back to
    the daily diary — a diary keyed on a branch that doesn't exist is worse than
    a dated one)."""
    try:
        out = subprocess.run(
            ["git", "-C", PROJECT_ROOT, "symbolic-ref", "--quiet", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def branch_slug(branch: str) -> str:
    """`fix/hygiene-findings-trio` -> `fix-hygiene-findings-trio`."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch.strip()).strip("-.")
    return slug[:80]


def diary_path() -> str:
    """The diary file this change should be written into.

    Under `diary_scope: "branch"` (default) one file covers the whole
    branch/MR — `YYYY-MM-DD-<branch-slug>.md`, dated when the branch's diary
    STARTED, so a change spanning days keeps its discussion in one place and
    the filename still sorts chronologically. An existing file for the branch
    is reused whatever its date prefix; only the first write picks a date.

    Falls back to the dated file (`YYYY-MM-DD.md`) under
    `diary_scope: "daily"`, on a detached HEAD, and outside a git repo."""
    diary_dir = os.path.join(MEMORY_DIR, "diary")
    today = date.today().isoformat()
    if load_kit().get("diary_scope") != "branch":
        return os.path.join(diary_dir, f"{today}.md")
    slug = branch_slug(current_branch())
    if not slug:
        return os.path.join(diary_dir, f"{today}.md")
    existing = sorted(glob.glob(os.path.join(diary_dir, f"*-{slug}.md")))
    if existing:
        return existing[-1]
    return os.path.join(diary_dir, f"{today}-{slug}.md")


def diary_satisfied(after_ts: float) -> bool:
    """This change's diary exists and was touched after `after_ts`."""
    path = diary_path()
    return os.path.isfile(path) and touched_since(path, after_ts)


def flag_satisfied(name: str, info: dict) -> bool:
    ts = info.get("ts", 0)
    if name == "discussion":
        return diary_satisfied(ts)
    roster = FLAG_ROSTER.get(name)
    if roster is None:
        # Unknown flag name: satisfied when the diary catches up (best effort).
        return diary_satisfied(ts)
    return touched_since(os.path.join(MEMORY_DIR, roster), ts)


def handle_post_tool(payload):
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if not file_path:
        sys.exit(0)
    norm = normalize_path(file_path)
    # A path still absolute after normalization lies OUTSIDE this repo —
    # never flag it (unanchored profile regexes would otherwise match scratch
    # files anywhere on the machine and wedge the Stop gate).
    if norm.startswith("/") or re.match(r"^[A-Za-z]:/", norm):
        sys.exit(0)
    # Never flag edits to the memory ledgers themselves.
    if norm.startswith(".memory/") or "/.memory/" in norm:
        sys.exit(0)
    if matches_source(norm):
        set_flag("code_change", norm)
        msg = (
            f"Docs contract: source change to `{norm}` recorded. Before you "
            f"stop, add a line to .memory/CHANGELOG.md"
            + ("" if not load_kit().get("diary") else " and write/touch today's .memory/diary entry")
            + "."
        )
        # Plain stdout on PostToolUse never reaches the model; additionalContext
        # does (proven pattern from the v1 homelab/meritick shell hooks).
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": msg,
            }
        }))
    sys.exit(0)


def handle_stop(payload):
    # Loop-guard: if a prior Stop hook already blocked, don't block again.
    if payload.get("stop_hook_active"):
        sys.exit(0)

    data = load_pending()
    flags = data.get("flags", {})
    first_ts = data.get("first_flag_ts")
    # first_flag_ts survives after roster flags are cleared so the diary gate
    # (condition b) cannot be dodged by satisfying the roster files alone.
    if not flags and not first_ts:
        sys.exit(0)

    kit = load_kit()
    unsatisfied = []

    # Clear satisfied flags (condition a, per flag); collect what remains.
    for name in list(flags.keys()):
        if flag_satisfied(name, flags[name]):
            del flags[name]
        else:
            unsatisfied.append(name)

    # Session-level diary gate (condition b): while ANY flag was raised this
    # session and kit.diary is on, today's diary entry must exist and postdate
    # the session's first flag.
    diary_gate_ok = True
    if kit.get("diary"):
        diary_gate_ok = diary_satisfied(first_ts or 0)

    if not unsatisfied and diary_gate_ok:
        # Fully satisfied — reset the session ledger.
        save_pending({"flags": {}, "first_flag_ts": None})
        sys.exit(0)

    # Persist cleared flags but KEEP first_flag_ts while anything is owed.
    save_pending(data)

    rel_diary = os.path.relpath(diary_path(), PROJECT_ROOT)
    reasons = []
    for name in unsatisfied:
        if name == "code_change":
            reasons.append("update .memory/CHANGELOG.md with what changed")
        elif name == "decision":
            reasons.append("record the decision in .memory/DECISIONS.md")
        elif name == "discussion":
            reasons.append(f"write this change's diary entry ({rel_diary})")
        else:
            reasons.append(f"resolve pending flag '{name}'")
    if kit.get("diary") and not diary_gate_ok and "discussion" not in unsatisfied:
        reasons.append(f"write this change's diary entry ({rel_diary})")

    reason = (
        "Docs contract: work this session is not yet reflected in the "
        "ecosystem docs. Before stopping, " + "; ".join(reasons) + ". "
        "Then stop again."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


# Anchored to a command boundary (start of string, or after ; && || | newline)
# so `echo git commit` and `grep "git commit" log` do not gate a commit that
# isn't happening. This hook BLOCKS, so a loose match is not a harmless warning
# the way it is in advisory guard_commit_message.
GIT_COMMIT_RE = re.compile(
    r"(?:\A|[;&|]|\n)\s*git\s+(?:-C\s+\S+\s+)?commit\b")


def handle_pre_commit(payload):
    """Commit-time checkpoint: a decision or discussion raised during this work
    must be in the diary BEFORE the commit that carries it, not at session end.

    Deliberately narrow. Only `decision`/`discussion` flags gate here — those
    are the things whose reasoning evaporates once the session ends. A plain
    `code_change` still rides to the Stop gate, so ordinary commits are never
    interrupted by a hook that has nothing to say."""
    kit = load_kit()
    if not kit.get("diary"):
        sys.exit(0)
    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not GIT_COMMIT_RE.search(command):
        sys.exit(0)

    data = load_pending()
    flags = data.get("flags", {})
    owed = [n for n in ("decision", "discussion") if n in flags]
    if not owed:
        sys.exit(0)
    # The oldest owed flag is what the diary has to have caught up with.
    since = min(flags[n].get("ts", 0) for n in owed)
    if diary_satisfied(since):
        sys.exit(0)

    rel = os.path.relpath(diary_path(), PROJECT_ROOT)
    what = " and ".join(owed)
    print(
        f"Docs contract: a {what} was recorded while building this commit, but "
        f"{rel} has not been updated since. Write it into the diary now — while "
        f"the reasoning is still in front of you — then commit again.\n"
        f"The diary covers this whole branch, so append to the existing entry "
        f"rather than starting a new one.",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    event = payload.get("hook_event_name", "")
    if event == "Stop":
        handle_stop(payload)
    elif event == "PreToolUse":
        handle_pre_commit(payload)
    elif payload.get("tool_name") in ("Edit", "Write") or event == "PostToolUse":
        handle_post_tool(payload)
    else:
        sys.exit(0)


if __name__ == "__main__":
    # Generic flag drop for command flows (/decide, /idea, ...):
    #   python3 .claude/hooks/docs_contract.py flag decision "why"
    # argv is only consulted here — the daemon calls main() directly, so its
    # own argv ("start") can never leak into hook dispatch.
    # Path resolution for command flows (/diary): the caller must not have to
    # reimplement branch-slug + existing-file rules to find the right file.
    if len(sys.argv) == 2 and sys.argv[1] == "diary-path":
        try:
            print(os.path.relpath(diary_path(), PROJECT_ROOT))
        except Exception as e:
            print(f"[ecosystem-kit] docs_contract diary-path failed: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    if len(sys.argv) >= 3 and sys.argv[1] in ("flag", "set-flag"):
        try:
            set_flag(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
            # Point the command flow at the diary the moment the decision is
            # made — writing it now is the whole difference between a diary
            # that reconstructs the day and one that recorded it.
            if sys.argv[2] in ("decision", "discussion") and load_kit().get("diary"):
                rel = os.path.relpath(diary_path(), PROJECT_ROOT)
                print(f"Record this in {rel} now (append to the branch's entry) — "
                      f"the commit gate will ask for it otherwise.")
        except Exception as e:
            # Flag-drop is plumbing for commands, not a gate: fail open.
            print(f"[ecosystem-kit] docs_contract flag failed: {e}", file=sys.stderr)
        sys.exit(0)
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # BLOCKING hook: fail closed on an engine-level crash.
        print(f"[ecosystem-kit] docs_contract crashed: {e}", file=sys.stderr)
        sys.exit(2)
