# 2026-08-27 — fix/kit-propagate-slow-network

## Found by finally running it for real

Four kit changes merged today, all five repos still on `13dcdcf`. The first
genuine multi-repo `kit-propagate run` failed two ways, neither visible from
`check` mode:

```
[wire] DevContainer: added hook wiring PostToolUse[Artifact]:artifact_sync
[PR]   DevContainer: .../DevContainer/pull/15 (8 file(s))
[wire] mylantite: added hook wiring PostToolUse[Artifact]:artifact_sync
Traceback (most recent call last):
subprocess.TimeoutExpired: ['safe-push', ...] timed out after 300 seconds
```

DevContainer got its PR. mylantite's push timed out. **grade5, meritick and
homeassistant were never attempted** — the traceback took the process down.

## Bug 1: one timeout for two very different jobs

`run()` applied a flat `timeout=300` to every subprocess. `git rev-parse` and
`safe-push` are not the same class of operation, and this machine makes that
obvious:

```
$ time git ls-remote origin HEAD
real    0m13.549s
```

**Thirteen and a half seconds for a single round-trip to github.com.**
`safe-push` fetches, checks the remote default branch, then pushes — several
round-trips plus the transfer — so 300s was never going to be enough here.

Two fixes, and the second matters more than the first: network operations get
their own 1200s budget, **and** a timeout now degrades to a per-repo failure
instead of an escaping traceback. Losing one repo to a slow push is tolerable;
losing the four queued behind it is not.

## Bug 2: the pending-PR skip assumed kit main stands still

```python
branch = f"chore/kit-update-{kit_head}"
if origin/<branch> exists: skip   # "pending PR"
```

That reads as "skip if this repo already has an update pending". It actually
means "skip if this repo has an update pending **for exactly this kit commit**".
The moment kit main moves, the branch name changes, the open PR becomes
invisible, and the repo gets a second overlapping update PR.

Which is precisely what happened: PR #29 merged *while I was propagating*, kit
head went `7b193a7 → 9c1cd1c`, and DevContainer — with PR #15 open and
unmerged — was queued for a duplicate.

Now keyed on the branch **prefix**, so the invariant is the real one: at most
one outstanding kit update per repo. The cost is that a newer kit change waits
for the pending PR to merge, which is right — it is the same change plus more,
and merging the older one first loses nothing.

## What I got wrong on the way here

I told the owner propagation should wait for PR #27 (the unwired-hook report),
claiming otherwise every repo would take a health-check ERR and `artifact_sync`
would do nothing. **False.** `kit-propagate` already had `patch_hook_wiring`,
whose docstring describes this exact failure from 2026-08-01. The propagation
path was never at risk; only the manual `installer/update.sh` route (used by
`/kit-update`) was, which is a much narrower claim than the one I made.

I tested the low-level component in isolation, found a real defect, then
assumed it was the only delivery path. The evidence was sitting in
`kit-propagate`'s docstring — which I read for the first time *after* shipping
the PR. Read the caller before sizing the bug.

The run itself confirmed the correction, in its own output: `[wire]
DevContainer: added hook wiring PostToolUse[Artifact]:artifact_sync`.

## State left behind

- DevContainer PR #15 is **open and functionally complete**: `9c1cd1c` (the gh
  change) touches only `.memory/`, `docs/` and `tools/bootstrap-machine.sh`,
  none of which `update.sh` installs into a target repo. Nothing is missing
  from it, and the new prefix skip will leave it alone.
- mylantite's branch never reached origin; no leftover worktrees.
- grade5, meritick, homeassistant untouched.
- Once this merges, one `kit-propagate run` finishes the remaining four.

## Noted, not fixed

`check` mode still reports DevContainer as `[behind]` rather than
`[skip] pending`, because the pending test happens after the check-mode early
return. Honest (its stamp *is* behind) but less useful than it could be. Left
alone to keep this change to the two failures that actually broke the run.
