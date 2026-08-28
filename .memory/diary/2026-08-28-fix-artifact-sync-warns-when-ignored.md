# 2026-08-28 — fix/artifact-sync-warns-when-ignored

## Found by an audit, not by the hook

Recovering four artifacts that predated `artifact_sync`, one of them landed in
DevContainer. The hook said:

```
Artifact mirrored into the repo (ecosystem-kit artifact_sync):
  -> docs/artifacts/prod-decision-md/ (prod-decision-md.md, index.html, artifact.json)
  no change to commit
```

The first line is a claim of durability. The last line was the only hint, and it
reads like "nothing to do". The truth was that DevContainer's `.gitignore` line 1
is `*` — deny-by-default with explicit un-ignores — so git could not see any of
it. The files existed on disk and would have vanished on the next clone.

A hook whose entire purpose is *making artifacts durable* reported success for a
write that retained nothing.

## Two states, one output

`git status --porcelain -- <paths>` returns empty for both:

- nothing changed since the last run — benign, the common case
- the paths are ignored — the feature silently did nothing

Identical output, opposite meanings. The hook collapsed them into
`"no change to commit"`, which is true of the first and dangerously misleading
about the second. Now separated with `git check-ignore -q`, reporting:

```
NOT TRACKED — docs/artifacts/... is gitignored, so the mirror exists only on
this machine and disappears on a fresh clone. Un-ignore it (a deny-by-default
.gitignore needs an explicit `!` rule) or point artifacts.dir somewhere tracked.
```

Says what is lost, and what to do — not just that something is off.

## Checking the instrument before trusting it

Earlier in the audit I ran `git check-ignore -v` on a negated path, read the
printed pattern as proof the file was ignored, and reported "STILL IGNORED"
while `git status` was showing it as trackable. Wrong, and the sort of wrong
that would have been baked into this fix.

So before writing the detection, I tested it against a throwaway repo carrying
both cases:

```
docs/a/f.html  (negated → NOT ignored): exit=1
other/g.html   (ignored):               exit=0
```

`check-ignore -q` is exact, including for negations. My earlier reading was the
error, not git's behaviour. Verifying the tool the fix depends on cost one
command and is what makes the fix trustworthy.

## The test that nearly passed for the wrong reason

The first end-to-end run against a scratch repo reproducing DevContainer's
`.gitignore` printed:

```
NOT COMMITTED — on protected branch 'master'; commit it on a branch
```

The scratch repo was on `master`, so `commit()` returned at the protected-branch
guard long before reaching the ignore check. Had I only read "not committed" and
moved on, I would have concluded the warning worked without it ever running.
Re-run on a feature branch, the real message appeared — and disappeared again
once `!docs/` was added, which is the other half of the proof.

Ordering note, deliberate and left alone: the protected-branch check still comes
first, so on a protected branch an ignored path is not reported. Correct
priority — the commit could not happen either way — but worth knowing.

## Not addressed here

The kit still cannot tell a project *where* to keep artifacts if `docs/` is
deliberately ignored; `artifacts.dir` is configurable and that is the answer.
The warning names it.
