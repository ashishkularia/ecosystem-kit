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
import json
import os
import re
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


def diary_satisfied(after_ts: float) -> bool:
    """Today's diary exists and was touched after `after_ts`."""
    today = date.today().isoformat()
    path = os.path.join(MEMORY_DIR, "diary", f"{today}.md")
    return os.path.isfile(path) and mtime(path) > after_ts


def flag_satisfied(name: str, info: dict) -> bool:
    ts = info.get("ts", 0)
    if name == "discussion":
        return diary_satisfied(ts)
    roster = FLAG_ROSTER.get(name)
    if roster is None:
        # Unknown flag name: satisfied when the diary catches up (best effort).
        return diary_satisfied(ts)
    return mtime(os.path.join(MEMORY_DIR, roster)) > ts


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

    reasons = []
    for name in unsatisfied:
        if name == "code_change":
            reasons.append("update .memory/CHANGELOG.md with what changed")
        elif name == "decision":
            reasons.append("record the decision in .memory/DECISIONS.md")
        elif name == "discussion":
            reasons.append(f"write today's diary entry (.memory/diary/{date.today().isoformat()}.md)")
        else:
            reasons.append(f"resolve pending flag '{name}'")
    if kit.get("diary") and not diary_gate_ok and "discussion" not in unsatisfied:
        reasons.append(f"write today's diary entry (.memory/diary/{date.today().isoformat()}.md)")

    reason = (
        "Docs contract: work this session is not yet reflected in the "
        "ecosystem docs. Before stopping, " + "; ".join(reasons) + ". "
        "Then stop again."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    event = payload.get("hook_event_name", "")
    if event == "Stop":
        handle_stop(payload)
    elif payload.get("tool_name") in ("Edit", "Write") or event == "PostToolUse":
        handle_post_tool(payload)
    else:
        sys.exit(0)


if __name__ == "__main__":
    # Generic flag drop for command flows (/decide, /idea, ...):
    #   python3 .claude/hooks/docs_contract.py flag decision "why"
    # argv is only consulted here — the daemon calls main() directly, so its
    # own argv ("start") can never leak into hook dispatch.
    if len(sys.argv) >= 3 and sys.argv[1] in ("flag", "set-flag"):
        try:
            set_flag(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
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
