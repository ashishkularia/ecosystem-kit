#!/usr/bin/env python3
"""PreToolUse:Edit|Write — test-first discipline, driven by kit.json.

Behaviour depends on kit.json `principles.tdd`:
  - "off"     → silent, always allow
  - "advise"  → first edit of each source file this session prints a
                test-first reminder (advisory, exit 0)
  - "enforce" → editing a source file with ZERO test-file edits so far this
                session blocks (exit 2). Touch/extend a test first, then the
                source edit is allowed.

"Source" = repo-relative path matching any kit.json `source_patterns` regex;
when a profile omits source_patterns, files with a source extension
(_constants.SOURCE_EXTENSIONS) count. Test files are always allowed and
recorded as test edits.

Session state lives in .memory/cache/tdd_state.json (gitignored), keyed by
the harness session_id so a new session starts clean.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import MEMORY_DIR, PROJECT_ROOT, SOURCE_EXTENSIONS, load_kit

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG tdd_gate] {msg}", file=sys.stderr)


def state_path():
    return os.path.join(MEMORY_DIR, "cache", "tdd_state.json")


def load_state(session_id):
    try:
        with open(state_path(), "r", encoding="utf-8") as f:
            state = json.load(f)
        if state.get("session_id") == session_id:
            return state
    except (OSError, ValueError):
        pass
    return {"session_id": session_id, "test_edits": 0, "advised": []}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(state_path()), exist_ok=True)
        with open(state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError as e:
        debug(f"Could not persist state: {e}")


def relative_path(file_path):
    path = file_path.replace("\\", "/")
    root = str(PROJECT_ROOT).replace("\\", "/").rstrip("/")
    if root and path.startswith(root + "/"):
        path = path[len(root) + 1:]
    if path.startswith("./"):
        path = path[2:]
    return path


def is_test_file(path):
    normalized = path.replace("\\", "/")
    basename = os.path.basename(normalized)
    if any(m in normalized for m in ("/tests/", "/test/", "/__tests__/")):
        return True
    if normalized.startswith(("tests/", "test/")):
        return True
    if basename.endswith("Test.php"):
        return True
    if re.search(r"\.(test|spec)\.(ts|tsx|js|jsx|mjs)$", basename):
        return True
    if basename.startswith("test_") and basename.endswith(".py"):
        return True
    if re.search(r"_test\.(py|go|rb)$", basename):
        return True
    return False


def is_source_file(rel_path, source_patterns):
    if source_patterns:
        for pattern in source_patterns:
            try:
                if re.search(pattern, rel_path):
                    return True
            except re.error:
                continue
        return False
    # Fallback when the profile omits source_patterns.
    return os.path.splitext(rel_path)[1].lower() in SOURCE_EXTENSIONS


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    kit = load_kit()
    tdd_mode = (kit.get("principles") or {}).get("tdd", "advise")
    if tdd_mode == "off":
        sys.exit(0)

    session_id = str(payload.get("session_id") or "default")
    rel = relative_path(file_path)

    # A path still absolute after normalization lies OUTSIDE this repo —
    # out of scope for this project's TDD discipline.
    if rel.startswith("/") or re.match(r"^[A-Za-z]:/", rel):
        sys.exit(0)

    if is_test_file(rel):
        state = load_state(session_id)
        state["test_edits"] = int(state.get("test_edits", 0)) + 1
        save_state(state)
        sys.exit(0)

    if not is_source_file(rel, kit.get("source_patterns") or []):
        sys.exit(0)

    state = load_state(session_id)

    if tdd_mode == "enforce" and int(state.get("test_edits", 0)) == 0:
        print(
            f"BLOCKED by tdd_gate (principles.tdd = enforce): source file edited "
            f"with no test edits this session.\n"
            f"  File: {rel}\n"
            f"  Write or update a failing test FIRST (Red), then implement (Green).\n"
            f"  Editing any test file unlocks source edits for this session.",
            file=sys.stderr,
        )
        sys.exit(2)

    advised = state.get("advised") or []
    if rel not in advised:
        advised.append(rel)
        state["advised"] = advised[-200:]  # bound the state file
        save_state(state)
        print(f"TDD Advisory — {os.path.basename(rel)}")
        print("  You are editing a source file. Write/update the test first.")
        print("  Red -> Green -> Refactor.")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Advisory-grade: fail OPEN.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e} — allowing (fail-open).", file=sys.stderr)
        sys.exit(0)
