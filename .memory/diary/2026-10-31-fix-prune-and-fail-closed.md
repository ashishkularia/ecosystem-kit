# 2026-10-31 — fix/prune-and-fail-closed

## What happened

Cleaning up after mylantite #247, I found that the owner's list from the day
before still asked them to force-delete two kit branches. The 06:52
`prune-stale-branches` run has a tier for squash-merged branches, so its log was
the place to look. It would delete `fix/secret-scanner-psql-interpolation`
itself, but it had kept `chore/bootstrap-drop-unwedge` on every run since #52
merged on 2026-10-23, as "has unpushed commits: [ahead 1, behind 5]".

Before committing the fix I ran `/verify`, which found the second bug in this
PR.

## The prune job

That branch was made from `origin/main`, so `origin/main` stayed its upstream
after the push. A squash merge leaves the branch's commit off main, and the job
read "ahead of `origin/main`" as unpushed work. Its tip, `3409361`, is PR #52's
head, so nothing on it was unpushed.

The same check failed the other way too. Once a merged branch's remote is
deleted, its upstream reads "[gone]", which says nothing about ahead, so a
commit made on the branch after the merge was deleted with it. The log names
deleted branches but not their commits, so whether a past run did this cannot
be told from it.

Tier 2 now asks GitHub for the head commits of the branch's merged PRs. It
deletes the branch only when its tip is one of those commits or an ancestor of
one, and it never reads the upstream.

`test_prune_stale_branches.py` builds each case in a scratch repo, with the API
answer stubbed:

- a squash-merged branch that tracks `origin/main` is deleted;
- one with a commit after its merged head is kept;
- so is one whose remote branch is gone.

The old job fails the first test. Given GitHub's "merged" answer, it also fails
the third, deleting the commit. A version that deletes whenever a merged PR
exists fails the second. Run in `check` mode against the registry, the fixed job
would delete both kit branches. It keeps mylantite's
`fix/stripe-notice-strict-mode`, whose PR closed unmerged.

## The verify pass

All three open VERIFY rows could be checked:

- **The session_boot banner** was in this session's own start context: the
  STATE head, the VERIFY and ISSUES counts, the diary tail and the always-load
  list.
- **The docs_contract Stop gate:** this session's transcript holds seven blocks
  after source edits, each naming the CHANGELOG and the branch diary. Each time
  the docs were then updated, and the next stop went through. That stop carries
  `stop_hook_active`, so the gate cannot wedge a session.
- **The fail-open/fail-closed split failed half its check.** In a scratch hook
  install, a broken advisory hook exits 1 with its error on stderr, so tools
  still run. But a broken `secret_scanner` exited 1 too:
  - A syntax error or an exception at import kills a hook before its own guard
    runs. The daemon cannot load such a hook, so the client runs the file
    directly and passes its exit code through.
  - Claude Code reads exit 1 as a non-blocking error, so the Write would have
    gone through.

  The client now exits 2 when a blocking hook exits with anything but 0 or 2.
  `test_client_fail_closed.py` covers both halves, and the old client fails its
  blocking test for both breakages. The intact scanner still blocks a secret
  Write and passes a clean one.

The scratch install started a daemon once its 60-second auto-start cooldown ran
out. I stopped it with `_daemon.py stop` before deleting the directory, and the
test keeps a fresh cooldown file so it never starts one.

## Checks

The engine suite (315 tests) passes. The cron and the hooks run the deployed
copies, so the fixes take effect in two ways:

- `kit-propagate` installs the client fix in each repo;
- `bootstrap-machine.sh` deploys the prune job to `~/.claude/bin/`.
