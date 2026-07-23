#!/usr/bin/env python3
"""PostToolUse:Bash — parse and summarize test output.

ALWAYS exits 0 (advisory). Prints a structured pass/fail summary after a
test command completes. Detects PHPUnit, Pest, Vitest and Playwright
output. A command counts as a test command when it matches a generic
marker OR contains one of kit.json `quality_commands.test` entries.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import load_kit

HOOK_DEBUG = os.environ.get("HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug(msg):
    if HOOK_DEBUG:
        print(f"[DEBUG guard_post_test] {msg}", file=sys.stderr)


GENERIC_TEST_MARKERS = [
    r"php\s+artisan\s+test",
    r"\bphpunit\b",
    r"\bpest\b",
    r"composer\s+(run\s+)?test",
    r"\bnpm\s+(run\s+)?test\b",
    r"\bpnpm\s+(run\s+)?test\b",
    r"\byarn\s+test\b",
    r"\bvitest\b",
    r"playwright\s+test",
]


def is_test_command(command):
    cmd_lower = command.lower()
    for marker in GENERIC_TEST_MARKERS:
        if re.search(marker, cmd_lower):
            return True
    for configured in (load_kit().get("quality_commands") or {}).get("test", []) or []:
        if isinstance(configured, str) and configured.lower() in cmd_lower:
            return True
    return False


def parse_phpunit(output):
    ok = re.search(r"OK \((\d+) tests?, (\d+) assertions?\)", output)
    if ok:
        total = int(ok.group(1))
        return {"framework": "PHPUnit", "total": total, "passed": total,
                "failed": 0, "assertions": int(ok.group(2)), "status": "PASS"}

    m = re.search(
        r"Tests:\s*(\d+),\s*Assertions:\s*(\d+)(?:,\s*Failures:\s*(\d+))?(?:,\s*Errors:\s*(\d+))?",
        output,
    )
    if m:
        total = int(m.group(1))
        failures = int(m.group(3) or 0) + int(m.group(4) or 0)
        return {"framework": "PHPUnit", "total": total, "passed": total - failures,
                "failed": failures, "assertions": int(m.group(2)),
                "status": "FAIL" if failures else "PASS"}
    return None


def parse_pest(output):
    # Pest:  "Tests:    2 failed, 1 skipped, 40 passed (128 assertions)"
    #        "Tests:    40 passed (128 assertions)"
    m = re.search(
        r"Tests:\s+(?:(\d+)\s+failed[,\s]*)?(?:(\d+)\s+skipped[,\s]*)?(\d+)\s+passed\s*\((\d+)\s+assertions?\)",
        output,
    )
    if m:
        failed = int(m.group(1) or 0)
        skipped = int(m.group(2) or 0)
        passed = int(m.group(3))
        return {"framework": "Pest", "total": failed + skipped + passed,
                "passed": passed, "failed": failed,
                "assertions": int(m.group(4)),
                "status": "FAIL" if failed else "PASS"}
    return None


def parse_vitest(output):
    m = re.search(r"Tests\s+(?:(\d+)\s+passed)?(?:\s*\|\s*(\d+)\s+failed)?\s*\((\d+)\)", output)
    if m:
        passed = int(m.group(1) or 0)
        failed = int(m.group(2) or 0)
        return {"framework": "Vitest", "total": int(m.group(3)), "passed": passed,
                "failed": failed, "status": "FAIL" if failed else "PASS"}
    return None


def parse_playwright(output):
    m = re.search(r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?", output)
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2) or 0)
        return {"framework": "Playwright", "total": passed + failed, "passed": passed,
                "failed": failed, "status": "FAIL" if failed else "PASS"}
    return None


def extract_output(payload):
    resp = payload.get("tool_response")
    parts = []
    if isinstance(resp, dict):
        for key in ("stdout", "stderr", "output"):
            value = resp.get(key)
            if value:
                parts.append(str(value))
    elif isinstance(resp, str):
        parts.append(resp)
    if not parts:
        for key in ("tool_output", "stdout"):
            value = payload.get(key)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def format_summary(result):
    lines = [
        "=" * 60,
        f"Test Summary ({result['framework']}) — {result['status']}",
        "=" * 60,
        f"  Total:  {result['total']}",
        f"  Passed: {result['passed']}",
        f"  Failed: {result['failed']}",
    ]
    if "assertions" in result:
        lines.append(f"  Assertions: {result['assertions']}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command or not is_test_command(command):
        sys.exit(0)

    output = extract_output(payload)
    if not output.strip():
        sys.exit(0)

    result = (
        parse_phpunit(output)
        or parse_pest(output)
        or parse_vitest(output)
        or parse_playwright(output)
    )
    if result:
        print(format_summary(result))

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # Advisory: fail OPEN.
        print(f"HOOK ERROR ({os.path.basename(__file__)}): {e} — allowing (advisory hook).", file=sys.stderr)
        sys.exit(0)
