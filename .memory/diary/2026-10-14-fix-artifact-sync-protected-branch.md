# 2026-10-14 — fix/artifact-sync-protected-branch

## How this surfaced

mylantite's coordinator asked why the artifact mirror kept dirtying the main
checkout and blocking the owner's pull, with `artifacts.commit` already false.

## Cause

`PROJECT_ROOT` comes from `realpath(__file__)`, so it is the checkout whose
`.claude/` the session loaded. Sessions in mylantite are rooted at the main
checkout, so every publish wrote `docs/artifacts/*` into main's working tree.
`commit()` already refused on a protected branch, but only after the files were
written, so `commit: true` would not have helped either. Evidence in the repo:
`artifact.json` `published_from` pointing into a main-rooted session's
scratchpad, and a hand commit restamping the mirror the same day.

## Fix

`protected_checkout()` plus an early return in `main()`; `commit()` shares
`current_branch()`. The message names the consequence and the scratchpad source
path. 7 new tests; each of three mutants (guard never fires, everything
protected, message loses the consequence) fails at least one.

## Not done

The installed copies in the project repos pick this up through `/kit-update`.
