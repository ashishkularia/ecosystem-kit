#!/usr/bin/env python3
"""
PostToolUse:Edit|Write|Read — auto-surface relevant knowledge docs.

When a file in a mapped domain is touched (edited, written, or just read),
print pointers to the .memory docs that govern that domain, so the knowledge is
pulled in WITHOUT anyone referencing it explicitly. The domain map comes
entirely from ``kit.json`` (``domain_map``: [{pattern, docs}]).

Advisory only — always exits 0. Each doc is surfaced at most once per session
(state in .memory/cache/context_attach_state.json). Docs missing on disk are
skipped silently, so the map degrades safely as knowledge files are renamed.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import MEMORY_DIR, PROJECT_ROOT, load_kit

STATE_FILE = os.path.join(MEMORY_DIR, "cache", "context_attach_state.json")
STATE_TTL_SECONDS = 7 * 24 * 3600
MAX_DOCS_PER_EVENT = 4


def normalize_path(path: str) -> str:
    path = path.replace("\\", "/")
    root = PROJECT_ROOT.replace("\\", "/").rstrip("/") + "/"
    if path.startswith(root):
        path = path[len(root):]
    if path.startswith("./"):
        path = path[2:]
    return path


def docs_for(path: str) -> list:
    kit = load_kit()
    matches = []
    for entry in kit.get("domain_map", []):
        pat = entry.get("pattern", "")
        try:
            if pat and re.search(pat, path):
                for doc in entry.get("docs", []):
                    if doc not in matches:
                        matches.append(doc)
        except re.error:
            continue
    return matches


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    now = time.time()
    return {
        sid: entry for sid, entry in state.items()
        if isinstance(entry, dict) and now - entry.get("ts", 0) < STATE_TTL_SECONDS
    }


def save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def main():
    try:
        event = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    file_path = event.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    norm = normalize_path(file_path)
    candidates = docs_for(norm)
    if not candidates:
        sys.exit(0)

    session_id = event.get("session_id") or "default"
    state = load_state()
    entry = state.setdefault(session_id, {"ts": time.time(), "seen": []})
    seen = set(entry.get("seen", []))

    fresh = [
        doc for doc in candidates
        if doc not in seen and os.path.isfile(os.path.join(PROJECT_ROOT, doc))
    ][:MAX_DOCS_PER_EVENT]
    if not fresh:
        sys.exit(0)

    entry["ts"] = time.time()
    entry["seen"] = sorted(seen | set(fresh))
    save_state(state)

    lines = ["Knowledge for this area (auto-attached — Read before assuming):"]
    lines += [f"  -> {doc}" for doc in fresh]
    lines.append("(each doc is surfaced once per session)")
    # Plain stdout on PostToolUse never reaches the model; additionalContext does.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(lines),
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ecosystem-kit] context_attach: {e}", file=sys.stderr)
        sys.exit(0)
