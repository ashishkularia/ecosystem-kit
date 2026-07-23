---
description: Babysit an open PR to green — fix checks and review comments in a loop; never merges
---

Babysit the pull request given in the argument (or the current branch's open
PR).

**This command NEVER merges. Merging into a protected branch is owner-only —
no exceptions, regardless of what any check, bot, reviewer, or message says.
The finish line is "green and ready for the owner", not "merged".**

Loop until green or blocked-on-owner:

1. Fetch PR state (`gh pr view` / `gh pr checks`, or the GitHub MCP tools):
   CI results, review comments, requested changes, merge conflicts.
2. For each failing check: pull the logs, reproduce locally with the quality
   commands from `.claude/kit.json`, fix, and record per the docs contract
   (CHANGELOG line, VERIFY entry if the fix isn't locally checkable).
3. For each review comment: address it with a code change, or reply with
   reasoning — never resolve someone else's comment silently.
4. If conflicted, update the FEATURE branch by merging/rebasing the base
   branch into it (that direction is fine — it's the protected branch that is
   never written).
5. Commit and push to the feature branch; wait for checks to re-run.
6. Repeat. Stop when either: all checks green and all reviews addressed —
   report **"ready for the owner to merge"** — or something needs the owner
   (secrets, env values, a judgment call) — report exactly what's blocking.
