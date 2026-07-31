# Diary — fix/guard-command-splitting

Started 2026-08-01 · PR # (fill in once opened)

## Session — the guard that could be walked around

Dear diary,

A homeassistant session self-reported pushing to master — first once, then
twice more, three commits total (064294c, d5c95b2, d9f073b). It did the honest
thing: reported it, diagnosed it, and deliberately did NOT patch the security
guard it had just found a hole in, because the auto-mode classifier blocked an
agent editing its own guard and it agreed that was right. It also noted the fix
belongs upstream or `/kit-update` overwrites it. All correct.

**I verified the report rather than trusting it, and the hole was wider than
reported.** The splitter handled `&&`, `||`, `;` and nothing else. Probing the
real hook on a scratch repo checked out on master, nine forms sailed through:
piped (`git push | tail -2`, the reported one), `| cat`, `|&`, backgrounded
(`&`), newline-separated, subshell `(git push)`, substitution `$(git push)`,
backticks, and brace groups. Then a test I wrote caught a whole second family:
`for f in a b; do git push; done` splits fine but the fragment is `do git push`
— the KEYWORD becomes the command word, so the guard inspects `do` and sees
nothing. Same for `then`, and for `sudo`/`command`/`nohup`/`env` wrappers and
`FOO=bar` assignment prefixes. Eighteen bypass forms, all now blocked, verified
against the real hook.

**Two causes, and the second one isn't the kit's.** The session's other half of
the diagnosis was that something outside Claude checks out master and pulls
after a PR merge, so it believed it was on a feature branch. The reflog backs
that up exactly: `checkout: moving from <branch> to master` followed six to
seven seconds later by a bare `pull: Fast-forward`, twice. I checked every kit
tool — `prune-stale-branches` deliberately resolves the default branch from the
REMOTE precisely so a local checkout can't mislead it, and `kit-propagate` and
`pr-rebase` both work in worktrees. None of them checks out a branch in a
project repo. So that half is Ashish's own tooling or habit, exactly as the
session guessed. Worth him knowing, but nothing for me to fix.

The two combined perfectly: external tooling moved the checkout to master, the
session's belief about its branch went stale, and the one guard that would have
caught it had a hole in exactly the command form the session habitually uses.
Neither alone would have done it.

**Decided:**

- One splitter, in `_constants.py`, imported by all three guards. They each
  carried a copy and the copies had ALREADY drifted — 40 lines, 56 lines, 40
  lines; only `guard_dangerous_commands` ever learned to extract `$(...)`.
  That is exactly how this bug survives a fix: someone patches one fork. A
  security parser with three forks gets fixed in one of them.
- Over-split rather than under-split, stated as a rule in the docstring. An
  extra fragment costs at most a false positive; a missed fragment is a bypass.
  The asymmetry should be written down where the next person edits it.
- Keep BOTH the raw fragment and the prefix-stripped one. Some guards match
  whole command lines, others inspect the first token; dropping the raw form to
  "clean up" would break the former.
- `&` is a separator EXCEPT after `>`, so `2>&1` survives intact. Mis-splitting
  is not a safe kind of over-splitting: `git push 2>` with a stray `1` changes
  which token reads as a destination, and could flip a block into an allow.

**Done:** 18-form bypass matrix all blocking, 157 tests (up from 136), and a
false-positive sweep over everyday commands — including `git push origin
feature/x | tail -2`, the exact habitual form, which correctly still passes.

**Not done, deliberately:** `git commit` on a protected branch is still allowed
and that is BY DESIGN, not a gap. `weekly-hygiene` commits `.memory/` on the
default branch and never pushes; blocking local commits would break the kit's
own automation. The push is the gate, because the push is what makes it shared
— and the push gate is what was broken.

**Open:** the three commits are already on origin/master (local and remote both
at d9f073b, zero ahead), so this is not recoverable by a local reset. Reverting
means new commits pushed to a protected branch, which is the owner's call, not
mine. My read: the content is docs and tdarr source that would have passed
review anyway, so leaving it costs nothing but the process record — and a revert
would put *more* unreviewed commits on master to undo commits nobody objects
to. Recommend leaving it and letting the fixed guard prevent the next one.
