# 2026-08-29 — feature/union-merge-for-ledgers

## The question

*"why do we have the merge conflict in mr for changelog?"*

Because the format guarantees it. `.memory/CHANGELOG.md` is newest-first, and
the docs contract makes every substantive change add a line — so **every**
branch inserts at the same position, right under the header. Eight of the last
eight commits touching that file changed those same lines. Two branches
inserting different text at the identical line give git no basis to order them.

## Correcting myself

Earlier in this session I told the owner this was rebase-specific — that a
3-way merge handled it and only rebase broke. A controlled test says otherwise:

```
(1) MERGE trunk into A : CONFLICT
(2) REBASE A onto trunk: CONFLICT
(3) MERGE with merge=union: CLEAN
```

That earlier claim came from one observation on PR #30 — a merge that happened
to succeed — generalised into a rule without testing. The real variable is how
much unchanged context separates the two insertions, not which strategy runs.

## The scope decision is the whole design

`merge=union` keeps both sides instead of stopping. Safe **only** where the
contract says append-only:

- **In**: CHANGELOG, DOCS-CHANGELOG, DECISIONS, diary — "new entries go on top,
  old entries are never edited or deleted".
- **Out**: ISSUES, IDEAS, VERIFY — `- [ ]`/`- [x]` queues whose items are
  *checked off*, i.e. edited in place. Union there would silently duplicate a
  line both sides changed instead of conflicting, which is worse than the
  conflict it avoids. STATE is rewritten wholesale; GOTCHAS/CONVENTIONS are
  edited.

Proved both halves in one run: two branches each adding a changelog entry and an
ISSUES item merged with the changelog clean and **ISSUES still conflicting**.

## The finding that justifies the promotion

`ecosystem-kit`'s own `.gitattributes` already had these four lines — including
`diary/*.md`, which I had not thought of. The kit solved this for itself and
never shipped it. mylantite and meritick carry Laravel's stock file with no
union lines; DevContainer, grade5 and homelab have no `.gitattributes` at all.

One repo holding the answer while five keep hitting the problem is the promotion
bar stated exactly. I took the kit's proven set rather than my narrower guess.

## Reaching repos that already exist

`install.sh` runs once, so every current repo would have missed this. Added as a
`kit-propagate` policy patch too, alongside attribution and hook wiring — the
same reasoning that put those there.

Matching is on the PATH, not the whole line, so a repo that deliberately set its
own driver for one of these keeps it instead of gaining a second contradictory
entry. mylantite's `* text=auto eol=lf` and its root-level `CHANGELOG.md
export-ignore` are untouched — the latter is Laravel's changelog, not
`.memory/`'s, which is why path matching had to be exact rather than by basename.
