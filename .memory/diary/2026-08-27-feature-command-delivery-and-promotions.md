# 2026-08-27 — feature/command-delivery-and-promotions

## The finding that reordered the work

A promotion sweep across all five registered repos turned up an obvious
candidate — `dev` exists in **both** DevContainer and mylantite, forked, and is
the most-used command in the ecosystem (130 invocations). Textbook "existing
duplication means the kit is late".

Then reading the installer to plan the promotion turned up something worse.
`update.sh`'s own header: *"Untouched by design: … commands/, agents/ …"*, and
`install.sh` copies commands skip-if-exists. So the kit had **no delivery path
for an improved command at all**. `templates/commands/pr-babysit.md` gained
in-thread replies on 2026-08-13 (commit `48c18a2`) and reached none of the five
repos — including the ones using `/pr-babysit` most (25 invocations, latest
2026-08-23, every one running the stale copy).

Which reorders everything: promoting `dev` first would have put it in the kit
where **nobody would ever receive it**. The gap had to close first.

## Telling "stale" from "customized"

Both look identical — a file that differs from the current template. The
standard answer is a recorded baseline (dpkg conffiles, brew). My first instinct
was a hash manifest written at install time, and it was wrong for the specific
situation: a manifest needs seeding, so the five repos that *have* the problem
would have had no baseline until their next install.

The kit already records one and wasn't using it. `.claude/kit-version` line 2
names the kit commit the target was installed from, and `update.sh` runs inside
the kit repo, which has that commit's history. So:

```
git show <recorded-commit>:templates/commands/<name>.md
```

*is* the as-installed file, reconstructed for free. Target still matches it →
nobody touched it → safe to refresh. Anything else → customized → `KEPT`.

No migration, no new file, works on all five repos today. Every ambiguous
case — no baseline, sha not in this checkout (shallow clone), kit didn't ship
the file at that commit — is treated as customized and left alone. Conservative
by construction; `install.sh --force` stays the deliberate way to adopt.

Verified on a scratch install deliberately made stale (installed from `13dcdcf`,
then updated): `retro.md` customized by hand stayed byte-identical, `pr-babysit`
and `idea` refreshed, the three promotions arrived as NEW. That is the whole
contract in one run.

## Promotions, and what stayed put

- **`dev`** — DevContainer's version is already generic (reads `conductor.md`,
  classifies via `adaptive-ceremony`, pulls gates from `kit.json`); only its
  hosting-harness paragraph needed generalising. mylantite's fork is a
  team-orchestration variant and keeps itself automatically, since commands are
  skip-if-exists.
- **`migration-review`**, **`security-audit`** — one project reference each.
  `security-audit` was prose. `migration-review` hardcoded
  `docker exec mylantite_app`, which `kit.json` already models as
  `containers.app` — the mechanism existed, the command just wasn't using it.
- **Left put:** `dependency-update` (258 lines, 26 mylantite references — a
  rewrite wearing a promotion's clothes), and `sdlc-gate` / `hotfix` /
  `tdd-cycle`, which are promotable but need real genericising and aren't
  near-free like the three above.

## mcp-audit, and why it is not a template

Every one of the five repos carries the identical eight-server
`enabledMcpjsonServers` list, all with zero calls in seventeen days. Five-for-five
duplication looks like a textbook promotion — but the names come from
`~/.mcp.json`, a **machine** artifact. `~/.mcp.json` is an ancestor
project-scope file, so with `enableAllProjectMcpServers` every server in it
activates in every repo beneath it. That is why all five match: not five
independent decisions, one file seen five times.

Baking those names into a kit template would encode this machine's setup into
every project's install. So it went to `tools/`, beside safe-push and
weekly-hygiene, which already own machine-scope policy. It reports and never
edits: disabling is per-repo, and no single off switch exists that would not
also kill `mylantite-dev` and `laravel-boost`.

Running it found nine unused, not eight — `laravel-boost` too (32 lifetime uses,
none since 2026-06-12).

## Corrected

`.memory/STATE.md` claimed the repos were stamped from `7e0d2d8`/`59916b5`. All
five are on `13dcdcf` (2026-08-01). Both older commits are real; the line just
wasn't updated after the last propagation.

## Not done here

- Nothing has been propagated yet. This branch makes delivery *possible*;
  actually running `update.sh` against the five repos is a separate, owner-timed
  step (`kit-propagate` exists for it).
- The mylantite `PostToolUse:Edit` slowness (2,124 ms median over 625 runs, vs
  164 ms in homeassistant) is still unprofiled. It is repo-scale-correlated, not
  a kit engine bug — so deliberately not addressed here.
