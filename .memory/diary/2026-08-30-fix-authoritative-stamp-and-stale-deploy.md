# 2026-08-30 — fix/propagate-authoritative-stamp-and-stale-deploy

## Both of these were found by the tool working, not failing

The propagation ran clean. DevContainer got its PR, four repos correctly reported
stamp-only, and the union driver finished landing on all five. Nothing was
broken. These two came out of *reading* that successful output carefully enough
to notice it disagreed with the repos.

## "Behind" was a fact about my shell, not about the repo

`recorded_kit_commit` read `.claude/kit-version` from the working checkout. So
the answer depended on which branch someone had left that checkout on. mylantite
reported `2958de1` while its `origin/main` was at `6b3a963` — behind by a commit
it already had, because the checkout sat on a feature branch cut before the PR
merged.

The kit half of the same comparison had this right and said so in a comment:
*"the REMOTE default's tip — authoritative, never the local HEAD."* The repo half
had never caught up. An update PR is cut from `origin/<base>`, so `origin/<base>`
is the only reading of "behind" that matches what the tool would actually do
about it.

Overstating is harmless — the run produces `no material changes (stamp-only)` and
opens nothing. The direction that bites is the mirror image: a checkout *ahead*
of origin reads as current, and the repo silently never gets a PR it needs.

The fetch moved above the read as part of this. Reading `origin/<base>` from a
ref last updated yesterday would just be a fresher way of being wrong. `check`
still does not fetch — it is read-only and now says so in the comment rather than
in the docstring alone.

## A test that could not fail

First verification ran `check` against the real repos and printed the right
answers. It also proved nothing: mylantite's checkout had converged to `6b3a963`
in the meantime, so old and new code would have printed the same thing.

So: a fixture where the two genuinely disagree — a repo on `feature/old`
recording `bbbbbbb`, with `refs/remotes/origin/trunk` recording `aaaaaaa`.

```
recorded_kit_commit(repo)               -> bbbbbbb   (checkout, the old bug)
recorded_kit_commit(repo, base='trunk') -> aaaaaaa   (origin, authoritative)
recorded_kit_commit(repo, base='nope')  -> bbbbbbb   (fallback intact)
```

Building it hit the protected-branch guard on `git push origin main` — correct,
it cannot know a repo is disposable. `git update-ref refs/remotes/origin/trunk`
makes the remote-tracking ref directly and needs no remote at all.

## The gap that let three fixes do nothing

Cron runs `~/.claude/bin/kit-propagate`. The kit checkout is not what executes.
Nothing compared them, so three merged fixes to that file sat unused for days
while the daily run reported success.

`kit-propagate` now warns at startup, naming the drifted tools and the refresh
command. It parses the deploy list out of `bootstrap-machine.sh` rather than
keeping a second copy that would drift in its own right — the list is ten tools
and includes `unwedge-hooks.py`, which is not in `tools/`, so files absent from
the kit are skipped instead of reported as missing.

Warning, never aborting. A stale deployment is worth saying out loud and is never
a reason to refuse to propagate — and the tool doing the warning is itself the
most likely thing to be stale, which is an argument for advisory rather than
fatal.

## GOTCHAS: the answer was in the history

Earlier today a rebase conflicted in `.memory/GOTCHAS.md`, and both sides were
independent appended sections. That is precisely what union merge is for, and I
flagged it as a candidate.

The history disagrees. Across four repos, of 26 commits touching GOTCHAS, **4
deleted lines** — and every repo except the kit has at least one:

```
homeassistant  13 commits, 2 with deletions
mylantite      10 commits, 1
meritick        2 commits, 1
ecosystem-kit   1 commit,  0
```

Entries get corrected and retired in place. Union on that file merges two
versions of the same entry into something neither side wrote, silently. It stays
out, with ISSUES/IDEAS/VERIFY.

Worth keeping: one conflict made the file *look* append-only. Twenty-six commits
said it is not. Union should be earned by evidence of history, never by a file's
appearance during a single merge.

## Still not addressed

mylantite's push failure from this morning remains unexplained. It has not
recurred and cannot currently be reproduced — mylantite has the union lines, so
there is nothing to push. The error reporting will name the cause if it returns.
