# 2026-08-27 — fix/gh-auth-from-secrets

## The question that found it

Owner asked: *"for gh have you mentioned where the key will be?"*

The literal answer was yes — `~/.secrets/github-pat`, in both
`bootstrap-machine.sh` and `docs/ARCHITECTURE.md`. Checking properly rather than
answering from memory turned up three problems behind that yes:

```
$ gh auth status                 # no GH_TOKEN in env
You are not logged into any GitHub hosts.        exit 1
$ ls ~/.config/gh/hosts.yml
no such file
```

1. The step read **"Then authenticate"** and showed `gh auth status` — a
   *check*, which persists nothing. Wording I wrote.
2. `verify_gh` tested only that a binary existed, so bootstrap would report the
   step **green on a `gh` that cannot reach GitHub at all**.
3. Every invocation needed `GH_TOKEN="$(cat ~/.secrets/github-pat)"` prefixed. I
   did exactly that in every command of the session that installed it, and never
   wrote the requirement down.

Net effect: a future session running plain `gh pr create` gets "not logged in" —
the precise failure `gh` was added to prevent.

## Documenting a credential is not wiring it

The Python machine tools were never affected: `kit-propagate`, `pr-thread`,
`pr-comment-poller`, `pr-rebase` and `prune-stale-branches` all read
`TOKEN_FILE = ~/.secrets/github-pat` themselves. That consistency is what made
the gap invisible — the *scripts* were fine, so "where does the key live" had a
good answer, and `gh` being an external binary that knows nothing about that
file never came up.

## A decision recorded on a wrong premise

The original entry justified avoiding `gh auth login` by claiming it would
*"mint a separate OAuth token, giving the machine two GitHub credentials with
different scopes and lifetimes."*

True of the **interactive** flow. False of `--with-token`, which stores the
token you hand it — nothing is minted. The real tradeoff is one file versus the
same token copied into a second file (`~/.config/gh/hosts.yml`, written 0600).
Smaller, and outweighed: the copy is what makes bare `gh` usable at all, and
`verify_gh` now checks that copy still works, so rotation drift surfaces at
bootstrap instead of mid-task. The entry is corrected in place rather than
silently left standing.

## Presence is not usefulness

The `verify_gh` fix is the durable part. It now runs `gh auth status` with
`GH_TOKEN` and `GITHUB_TOKEN` **unset**, deliberately: testing with the caller's
environment would confirm that *this shell* can authenticate, not that the
machine can. Verified both ways — passes authenticated, fails against an empty
HOME.

Generalises past `gh`: a verify step that asserts installation rather than
capability will happily certify something that cannot do its job.
