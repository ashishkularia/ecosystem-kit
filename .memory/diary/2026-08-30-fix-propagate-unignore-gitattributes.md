# 2026-08-30 — fix/propagate-unignore-gitattributes

## The propagation finally ran, and that is how these were found

Three fixes had merged (per-repo isolation, the union driver, staging what the
patches touch) and none had ever executed. `~/.claude/bin/kit-propagate` is a
COPY, deployed by `bootstrap-machine.sh`, and nothing had re-run it since. Cron
fires that copy at 06:37 daily, so for days it ran the pre-fix version and
reported success.

Worth stating plainly: the union driver reaching zero repos had **two**
independent causes, and fixing the first did not fix it. The staging bug was
real. The stale deployed copy was also real, and would have kept the fix off
every machine indefinitely.

## Failure 1 — a repo that ignores everything

DevContainer's `.gitignore` is `*` on line 2 with an explicit `!` allowlist. The
patch wrote `.gitattributes` at the root, then:

```
git add .claude .gitattributes
  The following paths are ignored by one of your .gitignore files:
  .gitattributes
```

`add` refused, `check=True` raised, and the repo was lost from the run. The good
news is what happened next: the other four repos continued, because the per-repo
isolation from #36 was finally running. The fix it was written for showed up on
its first real execution.

`install.sh` had the identical hole and was quieter about it — no error, just a
`.gitattributes` written into a repo that could never see it.

Both now append `!.gitattributes` when the file comes back ignored. The
alternative, `git add -f`, works and leaves a tracked file that its own repo
claims is ignored — a trap for whoever edits it next.

## Failure 2 — found only by installing twice

The scratch-install rule says installer changes are proven by installing. Running
it twice proved something else:

```
after 1 install: 4 union lines
after 2 installs: 5
```

The dedupe was `grep -qE "^${path_only}[[:space:]]"`, and these paths are globs.
As a regex, `.memory/diary/*.md` reads "`/` zero or more times" — so it does not
match its own line, and every install appended another copy. Silent, unbounded,
and invisible to a single-run test.

The Python half of the same logic compares `line.split()[0]` exactly and was
never affected. One behaviour, two implementations, one of them wrong — which is
its own argument about keeping the shell and Python paths honest with each other.

Now an exact first-field `awk` compare, verified stable across three installs.

## A reporting bug that hid every push failure

mylantite failed with:

```
[FAIL] mylantite: push refused — error: failed to push some refs to '...'
```

That is git's generic trailer. The reason — a pre-push hook's message, a
non-fast-forward — always sits *above* it, and the code reported `detail[-1]`.
So the one line printed was guaranteed to be the least informative one available.
Now filtered: drop the `To …` / `failed to push some refs` / `hint:` noise and
report the last few real lines.

**mylantite's actual cause is still unknown** and is not guessed at here. Its
container is up, artisan boots, and 610 tests passed before a probe was cut
short — so the fast failure is not a broken harness. The next run will say.

## Not fixed here

Nothing yet compares the deployed `~/.claude/bin` tools against the kit checkout.
That gap is what let three merged fixes sit unused, and it is a health-check
concern, not a propagate one — every bootstrapped machine has it.
