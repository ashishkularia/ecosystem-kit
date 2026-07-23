#!/usr/bin/env python3
"""PostToolUse:Edit|Write — advisory engineering-principles checks.

ALWAYS exits 0 (advisory). Each check runs only when its principle in
kit.json `principles` is not "off" (enforce and advise both surface the
same advisory text here — hard enforcement belongs to architecture tests).

Checks on the newly written content:
  - dead_code : large commented-out code blocks (>=5 consecutive comment
                lines that look like code). The unreferenced-new-files
                heuristic is OFF by default (too many false positives).
  - fail_fast : bare `except:` / swallowed exceptions (`except: pass`),
                empty catch blocks in JS/TS/PHP.
  - logging   : print()/console.log()/var_dump() in non-test source —
                prefer the project's structured logger.
  - dry_kiss  : advice text only, appended when another finding fired or
                a very large file is written in one shot.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import load_kit

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")

LARGE_WRITE_LINES = 400
DEAD_CODE_RUN = 5


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_principles] {msg}", file=sys.stderr)


def is_test_file(path):
    normalized = path.replace("\\", "/")
    basename = os.path.basename(normalized)
    if any(m in normalized for m in ("/tests/", "/test/", "/__tests__/")):
        return True
    if normalized.startswith(("tests/", "test/")):
        return True
    if basename.endswith("Test.php") or basename.startswith("test_"):
        return True
    if re.search(r"\.(test|spec)\.(ts|tsx|js|jsx|mjs)$", basename):
        return True
    return False


def language_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        return "python"
    if ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        return "js"
    if ext == ".php":
        return "php"
    if ext in (".go", ".rb", ".java", ".cs"):
        return "other_source"
    return None


def check_dead_code(content):
    """Runs of >=DEAD_CODE_RUN consecutive comment lines that look like code."""
    findings = []
    run = 0
    code_like = 0
    for line in content.split("\n"):
        stripped = line.strip()
        if re.match(r"^(#|//|/\*|\*)\s?", stripped):
            run += 1
            body = re.sub(r"^(#|//|/\*|\*)+\s?", "", stripped)
            if re.search(r"[;{}()=]|\breturn\b|\bif\b|\bfor\b", body):
                code_like += 1
        else:
            if run >= DEAD_CODE_RUN and code_like >= 3:
                findings.append(
                    f"dead_code: {run} consecutive commented-out lines that look like code. "
                    f"Delete dead code — git history keeps it."
                )
            run = 0
            code_like = 0
    if run >= DEAD_CODE_RUN and code_like >= 3:
        findings.append(
            f"dead_code: {run} consecutive commented-out lines that look like code. "
            f"Delete dead code — git history keeps it."
        )
    return findings


def check_fail_fast(content, lang):
    findings = []
    if lang == "python":
        if re.search(r"(?m)^\s*except\s*:\s*(#.*)?$", content):
            findings.append("fail_fast: bare `except:` — catch specific exceptions and let the rest crash loudly.")
        if re.search(r"except[^\n]*:\s*\n\s*pass\b", content):
            findings.append("fail_fast: `except ...: pass` swallows errors silently — log or re-raise.")
    elif lang in ("js", "php"):
        if re.search(r"catch\s*(\([^)]*\))?\s*\{\s*\}", content):
            findings.append("fail_fast: empty catch block swallows errors silently — handle, log, or rethrow.")
    return findings


def check_logging(content, lang):
    findings = []
    if lang == "python":
        count = len(re.findall(r"(?m)^\s*print\(", content))
        if count:
            findings.append(f"logging: {count} print() call(s) in source — prefer the structured logger (logging module).")
    elif lang == "js":
        count = len(re.findall(r"console\.(log|debug)\(", content))
        if count:
            findings.append(f"logging: {count} console.log/debug call(s) in source — prefer the project logger.")
    elif lang == "php":
        count = len(re.findall(r"\b(var_dump|print_r|dd)\s*\(", content))
        if count:
            findings.append(f"logging: {count} var_dump/print_r/dd call(s) in source — prefer the structured logger.")
    return findings


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    lang = language_of(file_path)
    if lang is None:
        sys.exit(0)

    if tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        content = tool_input.get("new_string", "")
    if not content:
        sys.exit(0)

    principles = load_kit().get("principles") or {}
    is_test = is_test_file(file_path)

    findings = []

    if principles.get("dead_code", "advise") != "off":
        findings.extend(check_dead_code(content))

    if principles.get("fail_fast", "advise") != "off":
        findings.extend(check_fail_fast(content, lang))

    if principles.get("logging", "advise") != "off" and not is_test:
        findings.extend(check_logging(content, lang))

    if principles.get("dry_kiss", "advise") != "off":
        if findings or (tool_name == "Write" and content.count("\n") > LARGE_WRITE_LINES):
            findings.append(
                "dry_kiss: keep it simple — extract shared logic instead of duplicating, "
                "and avoid speculative abstraction (see .memory/references/engineering-principles.md)."
            )

    if findings:
        print(f"Principles Advisory — {os.path.basename(file_path)}")
        for f in findings:
            print(f"  {f}")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Advisory: fail OPEN.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e} — allowing (advisory hook).", file=sys.stderr)
        sys.exit(0)
