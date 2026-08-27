# 2026-08-27 — fix/propagate-prune-stale-refs

## Both found by finishing the job, not by reading the code

The five-repo propagation completed: DevContainer merged, mylantite #108,
grade5 #13, meritick #11, homeassistant #24. Two defects surfaced along the
way, and **one of them I introduced that same morning in #30.**

## The regression I shipped

#30 changed the pending-PR skip from an exact branch name to a prefix match,
to stop a moving kit head producing duplicate PRs. The final run printed:

```
[skip] DevContainer: kit update already pending (origin/chore/kit-update-7b193a7)
```

DevContainer's PR had **merged hours earlier** and GitHub had deleted that
branch. Checking:

```
$ git ls-remote --heads origin 'chore/kit-update-*'      # nothing
$ git for-each-ref 'refs/remotes/origin/chore/kit-update-*'
  origin/chore/kit-update-7b193a7                        # stale
```

The skip reads **local remote-tracking refs**, and `git fetch` without
`--prune` never deletes the ref for a branch the remote dropped. So once a
repo's kit update merges, that repo is skipped **forever**: one kit update per
repo, then silence, with no error anywhere.

The pre-#30 code read the same stale refs — but keyed on the exact new branch
name, so it self-healed every time kit main moved. **My broader check removed
the narrowness that was quietly keeping its inputs fresh.** Worth generalising:
when a check gets wider, re-examine what was keeping its inputs valid; the old
narrowness may have been doing that work.

It also read as *correct* here, because DevContainer genuinely was up to date.
Right outcome, wrong reason — the hardest kind to notice.

## The orphan

Earlier in the same sequence the run died with `RemoteDisconnected` inside
`create_pr`. #30 hardened subprocess timeouts; `urllib` exceptions were still
uncaught.

The damage is not the abort. `create_pr` runs **after the branch is pushed**, so
the exception left grade5 with a branch and no PR — and the new prefix skip
then reads that branch as "pending", skipping grade5 indefinitely for a PR that
does not exist. The two bugs compound: one creates orphans, the other makes
them permanent.

Now: retry once, and on hard failure raise a message naming the orphan with the
exact `gh pr create` to recover. Verified both paths against a stubbed
`urlopen` — two attempts then a recovery message, and success on a second
attempt after one drop.

## Rule this leaves

**Anything after the point of no return must not raise.** Once a side effect is
on a remote, a failure has to degrade into a report, because an exception
abandons state that later runs will misread.

## Still open elsewhere

- **mylantite's pre-push gate may not run from a worktree.** Its PR appeared
  2m13s after wiring; the suite takes ~17 min (timed). Neither `kit-propagate`
  nor `safe-push` sets `SKIP_HOOKS`/`SKIP_TESTS` or `--no-verify`. Likely cause:
  `core.hooksPath = .githooks` is relative and may not resolve in a worktree.
  Compounded by `run()` doing `docker exec -w /var/www/app`, so the hook tests
  the MAIN checkout, not the worktree being pushed. Two independent worktree
  blind spots on what that repo's own hook calls "the last gate before main".
  Not mine to change; owner can test with a trivial worktree commit and a clock.
- **mylantite parallel suite: 546 errors of 4720** on a clean run, passing
  sequentially. Points at test isolation under `--parallel`.
