# Field notes — self-hosted runners & CI troubleshooting

Raw material for the IDEAS entry "Ship runner + CI-pipeline guidance to every
repo" (2026-08-01). Gathered from **mylantite** [ML] and **meritick** [MK],
which both moved from GitHub-hosted to self-hosted between 2026-07-28 and
2026-08-01 on one WSL2 box.

**This is research, not doctrine.** It lives in the kit's own `.memory/` (which
never ships to targets), not in `templates/`. When the guidance is built, the
generalizable parts move to `templates/` and this stays as provenance. Specific
names (`mylantite-ci`, `mylantite_app-network`, `/opt/ci-deps`) are examples,
never things the kit should assert about a repo.

Claims marked ✓ were verified directly on this machine on 2026-08-01; the rest
are quoted from the repos' own `.memory/` and commit messages.

## The single biggest gap

**No runner-provisioning runbook exists in either repo.** Grepping
`--labels|--unattended|registration token|config.sh` across both repos and the
harness returns nothing. Every piece of registration knowledge is post-hoc
(`config.out`, `.runner`) or buried in a stale shell script. Whatever gets
built, *this* is the hole it fills.

## Registration and identity

- **A "rename" is a remove + re-register — there is no rename API.** [MK]
  2026-07-30: the first attempt "reported success while doing nothing"
  because `config.sh remove` aborted on a stale `.service` marker, and the
  check — *does `.runner` exist?* — was satisfied by the file the **failed
  remove itself left behind**. Only re-querying the GitHub API showed the old
  name still registered. Generalized lesson, worth carrying verbatim: *verify
  against the system of record, not against a local artifact the failure path
  can also produce.*
- **Never pipe `config.sh` through `head`** [MK] — SIGPIPE leaves registration
  half-done *while still printing a success banner*.
- **`rsync --exclude .runner` does not clone a runner install** [MK] — it
  misses `.runner_migrated` (and `.service`), so the copy "claims it is already
  configured".
- **Runner NAME ≠ `runs-on` LABEL.** ✓ Verified: mylantite's workflows use
  `runs-on: [self-hosted, linux, x64, mylantite]` (label `mylantite`) while the
  runner is *named* `mylantite-ci` — and [ML]'s own `ops-ci.md` says jobs run on
  "self-hosted `mylantite-ci`". Conflating the two is a direct cause of *job
  queued forever*.

## Lifecycle — the reboot question

- **nohup'd runners do not survive reboot.** ✓ meritick's listener runs
  nohup'd from `~/actions-runner-staging/meritick-1` with no systemd unit;
  mylantite's runs as a service. meritick CI dies on restart, still owed.
- The acceptance criterion [MK] wrote is the right one: *units active **and**
  all runners online **after a reboot***. Anything short of a reboot test
  doesn't prove it.
- Install is `sudo`-gated, so an agent cannot do it — it sits as owner-owed work
  for days. Guidance should say so plainly rather than implying automation.
- **The re-home script went stale.** `/home/ubuntu/restructure-runners.sh` still
  assumes the four-runner topology abandoned on 07-30. A runbook that isn't
  re-validated when the topology changes is worse than none.

## PATH and toolchain — the sharpest trap

**The runner bakes the interactive shell's PATH at `config.sh` time.** ✓
Verified: `meritick-1/.path` begins
`/home/ubuntu/.nvm/versions/node/v24.15.0/bin:…` and includes **16 Claude Code
plugin cache bin dirs**; `.env` carries `NVM_BIN=…/v24.15.0/bin`.

Consequences: the runner's Node is whatever nvm happened to be on at
registration, a later `nvm use` never reaches it, and unrelated tooling leaks
into CI's PATH. This is the *same class* of bug as homeassistant's
`guard_lint_md` failing under `/usr/bin/node` v18 while the shell had v24 —
**the environment a background process inherits is not the one you typed in**.

The architectural answer both repos adopted: *self-hosted jobs must not assume
tools on the runner host* — everything runs inside the app image; if a job needs
a tool, it goes in the image, not on the box. One documented exception [MK]:
node runs bare on the host because the meritick-php image carries none.

Bonus: baking the toolchain into the image *closed* a maintenance issue — [MK]
no longer maintains a separate CI PHP-extension list, because CI runs inside the
same image.

## Concurrency and draining

- **Drain the queue, not just the running job.** [MK] 07-30: an in-flight job was
  orphaned by a busy-poll → removal race and resolved as a cancelled superseded
  run. Queued runs keep the worker busy back-to-back, so `pgrep Runner.Worker`
  going quiet for one instant proves nothing.
- **CI and local runs share databases.** [ML]'s reproduction waits for the runner
  to be idle **90 consecutive seconds** first. [ML] GOTCHAS: overlapping two
  backend suite invocations once produced **~134 phantom failures**.

## Secrets

- **Tests that read secrets fail on CI because the secrets aren't there** — and
  the obvious fix is in the wrong place. [ML]: empty `STRIPE_SECRET` →
  `GatewayInvalidRequestException` at provider registration → every billing
  endpoint 500s → 20/3,696 tests fail. Patched with placeholders in the CI
  script, which fixes CI only; the proper home (a tracked `phpunit.xml` `<env>`
  default) must be checked against the runner's override semantics or a
  developer holding **real** keys is silently switched to a placeholder.
- **A test that skips itself is a green pipeline hiding a hole.** [ML] gates a
  Stripe spec on `secrets.STRIPE_KEY != ''`; absent the secret it self-skips and
  the pipeline is green.
- Deploy credentials are deliberately kept **off** the self-hosted box.

## Reproducing CI locally

- **Do NOT use `git archive` for a cold checkout.** ✓ `.gitattributes` line 9 is
  `/.github export-ignore`, so the archive silently omits the very
  `.github/ci/*.sh` scripts under test and the run dies `exit 127, No such
  file`. CI is unaffected because `actions/checkout` is a real clone. Use
  `git clone --depth 1 --branch <branch>`.
- **Cold checkouts surface what warm caches hide** — a stale `phpstan.neon`
  ignore was invisible until container CI ran fresh with
  `reportUnmatchedIgnoredErrors` on.
- Cold-checkout provisioning, every item learned from a red run: `.env` absent →
  PHPStan boots the app and dies; `.phpstan-cache/` gitignored → create it
  ([MK] notes "learned the hard way, **twice**"); Passport keys gitignored →
  every token-issuing test throws `Invalid key supplied`; `public/build/
  manifest.json` gitignored → Blade `@vite()` tests throw `Vite manifest not
  found`.

## Diagnostic heuristics worth encoding

1. **"Has it ever been green?"** [ML] established a gate had *never* passed by
   reading **runner logs**, not the PR status — it had been red since the day it
   landed. Reframes the question from "what did I break" to "what was never
   working".
2. **Check whether an earlier step aborts before the failing step runs.** [ML]'s
   billing failures were masked in CI because `npm ci` died on ERESOLVE first.
3. **`$?` after a pipe swallows failures** — an `npm ci` had silently
   ERESOLVE-failed behind it. All CI scripts now open `set -euo pipefail`.
4. **Two independent masks can hide one bug**: locally green because a
   developer's gitignored `.env.testing` held a real key; in CI green-adjacent
   because an earlier step aborted.
5. **Log-noise calibration** — steady-state `_diag/Runner_*.log` contains
   hundreds of *benign* `ERR BrokerServer …TaskCanceledException` /
   `ERR stream read finished` lines. Genuinely notable: `TimeoutException`,
   `/renewjob failed (ServiceUnavailable)`, `Back off … before next retry`.
   Nobody has written this mapping down; a triage guide should ship it.
6. **Progressive validation before migrating** — [ML] built a
   `workflow_dispatch`-only smoke workflow probing exactly the assumptions the
   new pattern depended on (docker without sudo, extensions in the image,
   checkout mounts, DB by service name, Redis auth). Note it was itself rewritten
   once the pattern changed, and is now undeleted debt.
7. **A/B measure an optimisation** — same script, same cold clone: 241s → 117s
   (**2.06×**, ~12 min per full run), rebuild 136s paid once per dependency
   change.

## Patterns worth generalizing

- **Tag the CI image with a hash of the dependency manifests.** Any manifest
  change misses the cache and rebuilds automatically, so *a stale image can
  never be used silently*; a hash mismatch degrades to **slow**, never to
  **wrong dependencies**. The hash formula is duplicated in two places — if they
  drift the hash simply never matches, which is correct, just slow.
- **Baked deps must not live at the bind-mount path** — the checkout is mounted
  over `/var/www/app` and would hide anything baked there; hence `/opt/ci-deps`.
- **`.dockerignore` deny-all + allow the manifests** — without it the build
  context was ~2 GB.
- **CI logic in committed `.github/ci/*.sh`, not inline YAML** — the scripts are
  what got validated in a cold checkout, so local reproduction stays one command.
- **`--legacy-peer-deps` per call site, not a global `.npmrc`**, so peer checking
  stays active for ordinary local installs. It was needed at **8** call sites;
  working locally only because it had been typed by hand and never propagated.
- **Container UID must match the checkout owner** (`--user 1000:1000`), and an
  image whose entrypoint starts a daemon needs `--entrypoint` overridden for
  one-off commands.
- **Service-container port collisions**: dev MariaDB/Redis already bind
  3306/6379 on the box, so fixed port maps fail. Join the app network and
  address services by name instead.
- **Mutation testing as a scheduled ratchet, never a PR gate** — hours on a
  serial runner; thresholds live with the tools and only ever go up.
- **Definition of done for a CI change** [ML], directly reusable as a checklist:
  the affected script has been run in a cold checkout inside the app image, the
  ops-ci doc still matches the workflow↔runner table, and any new job states
  **which runner it targets and why**.

## Housekeeping nobody owns

`_work` (61M), `_diag` (58M), `~/.ci-cache*`, and 226 MB runner tarballs left
after extraction — no pruning policy anywhere. Only the CI *images* are pruned.

## Cross-cutting, not CI-specific

- A blocked guard hook kills the **entire** compound command, so a ledger edit
  chained after a blocked step silently never runs [MK] 07-30.
- A squash-merged branch is never an ancestor, so `git branch -d` refuses it —
  and a tool cannot delete the branch the repo is standing on [MK] 08-01.
