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
   reasoning. **A reply belongs where the comment was made** (owner rule
   2026-08-03) — the two kinds of PR comment work differently:

   **Inline review comments** (left on a diff line) live in threads. List the
   unresolved ones with

   ```bash
   pr-thread threads <owner> <repo> <pr>     # ~/.claude/bin/pr-thread
   ```

   which returns each thread's `thread_id` plus the `reply_to_comment_id` to
   answer. Reply **in that thread** (`add_reply_to_pull_request_comment`, or
   `POST /repos/{o}/{r}/pulls/{n}/comments/{id}/replies`). Never post a new
   review comment on the same line — that opens a *second* thread beside the
   owner's — and never answer an inline comment with a general PR comment.

   Then **resolve the thread once it is genuinely addressed** (fix pushed, or
   the reply settles it):

   ```bash
   pr-thread resolve <thread_id>
   ```

   Resolving is GraphQL-only; REST cannot do it, which is why it is a machine
   tool rather than an API call you write. It **refuses unless a reply was
   posted first** — reply, then resolve, never resolve silently. Leave
   unresolved anything you could not address, and say why in the reply.

   **General comments on the conversation tab** have no thread; GitHub has no
   reply mechanism for them. Answer those with one general PR comment that
   **quotes** the lines you are responding to, so it still reads as a reply.
4. If conflicted, update the FEATURE branch by merging/rebasing the base
   branch into it (that direction is fine — it's the protected branch that is
   never written).
5. Commit and push to the feature branch; wait for checks to re-run.
6. Repeat. Stop when either: all checks green and all reviews addressed —
   report **"ready for the owner to merge"** — or something needs the owner
   (secrets, env values, a judgment call) — report exactly what's blocking.
