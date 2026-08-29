# 2026-08-29 — fix/propagate-stages-what-patches-touch

## Caught by checking, not by the run

Propagation of the union-merge driver ended looking fine:

```
[attr] grade5: union merge for .memory/CHANGELOG.md, …
[ok]   grade5: no material changes (stamp-only) — no PR
```

Those two lines are contradictory and I nearly read past them. The check that
caught it was asking the only question that matters — *did the lines actually
arrive?*

```
DevContainer   0 union lines on default branch
mylantite      0
grade5         0
meritick       0
homeassistant  0
```

Zero, everywhere, from a run that reported success.

## The cause, and why it hid

```python
run(["git", "-C", str(wt), "add", ".claude"])
changed = git diff --cached --name-only
if not changed or changed == [".claude/kit-version"]:
    ... no PR
```

`.gitattributes` is at the repo ROOT. `git add .claude` never staged it, so it
never appeared in `changed`, so the run concluded there was nothing material,
opened no PR, and the `finally` block removed the worktree — taking the file
with it.

The assumption was invisible because it had always been true: `patch_attribution`
and `patch_hook_wiring` both write `.claude/settings.json`. I added the first
patch that writes outside `.claude/` and did not notice the staging was scoped.

## Third time in this family

- `commit -- <paths>` could not commit untracked files (first publish always failed)
- `artifact_sync` generated the gallery and left it out of the commit pathspec
- a policy patch wrote outside the staged prefix

Each time: something written, something else deciding what to commit, and the
two disagreeing while the tool reported success. The general fix is the same
one the gallery bug landed on — derive the commit set from what was actually
written, not from a fixed assumption about where it lives.

So patches now record the paths they touch outside `.claude/`, and those get
staged. A future patch that writes somewhere new has one obvious place to say
so, and the comment says what happens if it does not.

## Note

Nothing was lost — the worktrees were disposable and `master` was untouched in
every repo. The cost was one propagation run, and a fix that would have shipped
believing itself delivered.
