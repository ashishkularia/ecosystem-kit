# 2026-09-02 — fix/hygiene-commits-on-a-branch

## How this surfaced

The owner asked, after being handed the same manual `git rebase origin/main` for
the third message running: *"can't you rebase your local branch?"*

No — `guard_protected_merge` names the case exactly ("Claude never merges into,
**rebases onto itself**, or pushes to a protected branch"), has no override, and
line 184 shows it tracks `git -C <dir>` deliberately, so the cwd-shift dodge was
already closed. But the better answer was that the owner should not be doing it
repeatedly, and the reason they were is a bug.

## The seam

```
tools/weekly-hygiene:60   "...commit with message 'chore(memory): weekly
                           hygiene ${TODAY}'. Do not push anything."
tools/kit-propagate:388   if cur != kit_default or head != remote: [abort]
```

Hygiene commits to `main` every Monday and never pushes → local `main` is one
ahead → the next PR merge on GitHub rebases that commit into origin's history →
`main` is now `ahead 1, behind 2` → propagate refuses to run.

Neither tool is wrong on its own. Hygiene not pushing is deliberate (owner
pushes/merges). Propagate refusing to ship from an unsynced kit is deliberate
(it would propagate unmerged content). Together they stall the whole propagation
chain every single week.

**19 of 27 propagate runs aborted on this** — `grep -c '^\[abort\]'` = 19, all
"not on a synced main", against 8 `[PR]` lines. Propagation has failed more
often than it has worked, for weeks, and the only evidence was a cron log.

And the clearing action is one the ruleset reserves for the owner: Claude cannot
touch `main`, by design and by hook. So the system was built to require a manual
weekly intervention that nothing ever asked for.

## The fix, and what it deliberately does NOT do

The script — not the model — cuts `chore/hygiene-<date>` before the run, and
pushes + PRs after it. The tempting version was to tell the headless model to
branch/commit/push/PR in one prompt, but that means adding network and
`safe-push` to its `--allowedTools`: push rights across five repos, granted to
an unattended cron agent, to fix a bookkeeping problem. The model's grant is
unchanged; the git plumbing is deterministic bash.

Guards added, each from a failure the fixture actually produced:

| case | behavior |
| --- | --- |
| not on default branch | skip — don't cut a hygiene branch off the owner's WIP |
| uncommitted `.memory/` changes | skip — don't sweep the owner's in-progress notes into the hygiene commit. Scoped to `.memory/`, NOT the whole tree: requiring a fully clean tree skipped meritick on the first real dry-run, and a habitually-dirty repo would then never get hygiene again — the same silent-stop this change exists to remove |
| hygiene branch already exists (local **or** remote) | skip — last week's PR is unmerged; two PRs rewriting the same ledgers conflict |
| model committed nothing | delete the branch, restore |
| push failed | warn, no PR, restore, `main` untouched |
| pushed but PR failed | name the ORPHAN with its branch — `kit-propagate` got trapped exactly here on 2026-08-27 and skipped grade5 forever as "pending" |
| cannot restore the branch | say so, with the branch it is stuck on |

## The bug the test found

First fixture run left the checkout wedged on the hygiene branch. Cause: the run
log is written to `.memory/cache/hygiene-<date>.log` — *inside the repo the
script then requires to be clean*. The post-run dirty check saw the script's own
log and refused to restore the default branch.

Kit-installed repos self-ignore `cache/` (tracked `cache/.gitignore` of `*` +
`!.gitignore`), so this would only fire where that convention is missing — which
is precisely where it would have been silent. `dirty()` now excludes
`.memory/cache`, because cache is machine-local scratch by definition and never
dirt. Worth noting the shape: a tool tripping over an artifact it created itself,
found only because the fixture didn't happen to follow the convention.

## Verified

Seven paths on scratch fixtures with stub `claude`/`safe-push`/`gh`: happy path
(commit on branch → push → PR → restore, **0 hygiene commits on `main`**), plus
the six guard cases above. Made `SAFE_PUSH`/`GH_BIN` env-overridable to allow it,
matching the existing `CLAUDE_BIN` pattern.

## Also logged

- ISSUES: the 19 aborts (resolved by this change).
- ISSUES: `start-remote-sessions.sh` treats any existing `claude-<repo>` tmux
  session as healthy, so one wedged on the folder-trust prompt hides itself from
  the launcher until the next reboot. Hit on percale today. Same family — the
  automation reports success while doing nothing.
