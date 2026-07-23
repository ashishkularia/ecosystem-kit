#!/usr/bin/env python3
"""Machine-wide guardrail: main/master belong to the owner.

Owner rule (2026-07-23): "No auto merge to main/master. Only I can merge to
them. Rest all branches are fine."

PreToolUse hook on GitHub MCP tools. Blocks:
- merge_pull_request (any target — PR merging is owner-only; also denied at
  the permission layer, this hook is the explaining backstop)
- push_files / create_or_update_file / delete_file when the branch param is a
  protected branch (permission rules cannot inspect params; this can)

Standalone by design — no dependency on any project's hook daemon.
"""
import json
import sys

PROTECTED = {"main", "master"}
WRITE_TOOLS = ("push_files", "create_or_update_file", "delete_file")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    if "github__" not in tool:
        return 0

    tool_input = payload.get("tool_input") or {}

    if tool.endswith("merge_pull_request"):
        print(
            "BLOCKED by guard_protected_branch: merging pull requests is "
            "owner-only. Get the PR green and wait for the owner to merge.",
            file=sys.stderr,
        )
        return 2

    if tool.endswith(WRITE_TOOLS):
        branch = str(tool_input.get("branch", "")).strip().lower()
        if branch in PROTECTED:
            print(
                f"BLOCKED by guard_protected_branch: direct writes to "
                f"'{branch}' via the GitHub API are owner-only. Push to a "
                f"feature branch and open a PR instead.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
