# CHANGELOG — ecosystem-kit

- 2026-08-30 — **A deny-by-default `.gitignore` swallowed the union driver, and
  the installer re-appended one line forever.** Two faults in the same block,
  found by running the propagation and then installing twice. (1) DevContainer
  ignores everything (`*` + an explicit `!` allowlist), so `git add .gitattributes`
  REFUSED the file the patch had just written and took the whole repo down with a
  RuntimeError — `install.sh` had the same hole, silently. Both now un-ignore it
  by appending `!.gitattributes`, rather than forcing it into the index. (2) the
  installer deduped with `grep -E "^$path"`, but these paths are globs:
  `.memory/diary/*.md` as a regex reads `/` zero-or-more times and never matched
  its own line, so every re-install appended another copy. Exact first-field
  compare now; verified idempotent across three installs.

- 2026-08-29 — **kit-propagate stages what the policy patches touch, not just
  `.claude/`.** The union-merge patch wrote `.gitattributes` at the repo ROOT,
  but staging was `git add .claude` — so the file was written, never staged,
  judged "no material changes (stamp-only)", and deleted with the worktree. All
  five repos reported `[attr] union merge for …` immediately followed by `[ok]
  no PR`, and **zero union lines reached any repo** while the run looked
  successful. Every earlier policy patch happened to write inside `.claude/`,
  which is why the scoped `add` held until it did not. Patches now record the
  paths they touch outside `.claude/` and those are staged too.

- 2026-08-29 — **Append-only ledgers get the union merge driver, kit-wide.** Owner
  asked why CHANGELOG conflicts in every MR. Cause is the format, not the merge
  strategy: the docs contract requires a CHANGELOG line on every substantive
  change and the file is newest-first, so concurrent branches always insert at
  the same line. Verified in a controlled test that BOTH merge and rebase
  conflict — correcting an earlier claim in this session that it was
  rebase-specific — and that `merge=union` resolves it, keeping both entries.
  New `templates/gitattributes.snippet`, appended by `install.sh` and by a new
  `kit-propagate` policy patch (install runs once; every existing repo predates
  this). Scoped to CHANGELOG, DOCS-CHANGELOG, DECISIONS and diary — NOT to
  ISSUES/IDEAS/VERIFY, which are checkbox queues edited in place where union
  would duplicate rather than conflict. Verified end to end: a two-branch test
  merged the changelog cleanly while ISSUES still conflicted.

- 2026-08-29 — **pr-rebase waits for GitHub to compute mergeability instead of
  guessing.** Owner reported the conflict resolver "runs sometimes and sometimes
  it doesn't". Cause: GitHub computes `mergeable_state` ASYNCHRONOUSLY — a GET
  requests the computation and returns `unknown` until it finishes — and the
  detector treated `unknown` as "no conflict" and moved on. The bias is the
  worst possible: the PRs most likely to be conflicted are the ones most
  recently pushed, which are exactly the ones answered `unknown`. Now polls
  until the state settles (4 attempts, 3s apart, no extra calls when it is
  already settled), and a still-unknown PR is LOGGED and skipped rather than
  silently read as clean. Ruled out the other candidate — the
  attempted-once state key — by checking every entry: all 12 are closed PRs,
  none stuck.

- 2026-08-29 — **One repo can no longer kill a propagation run — for real this
  time.** #31 claimed to fix this by converting `TimeoutExpired` into a
  `RuntimeError`, but that is still fatal under `check=True`, which the push call
  uses: the exception type changed and the run kept dying. Today mylantite's
  pre-push gate refused (non-zero exit, not even a timeout — a path #31 never
  touched) and grade5, meritick and homelab were never attempted. The push now
  runs with `check=False` and a refusal is logged as `[FAIL] <repo>: push
  refused`, and the whole per-repo body is wrapped so a step added later cannot
  reintroduce the same failure.

- 2026-08-29 — **artifact_sync commits the gallery it generates.** The root
  `docs/artifacts/index.html` was written and then left out of the commit
  pathspec, so it never entered git — the one file that makes the tree servable
  was the one file missing. Invisible until now because every repo that tracks
  it got it from a hand-run `git add` during a migration; meritick was the first
  repo where the hook ran unassisted, and there the gallery sat untracked. Fixed
  by committing every generated path, with a test that walks the output tree and
  asserts each written file falls under a committed path — a general guard
  rather than one that only knows about today's omission. 2 new tests, 210 green.

- 2026-08-28 — **artifact_sync reports when its output is gitignored instead of
  claiming success.** An empty `git status` over the artifact paths means either
  "nothing changed" or "git cannot see these files" — identical output, opposite
  meanings, and the hook reported the benign one for both. DevContainer ignores
  everything by default (`.gitignore` line 1 is `*`), so the hook wrote
  `docs/artifacts/`, said "mirrored into the repo", and git discarded it: the
  files existed locally and would have vanished on a fresh clone. Now
  disambiguated with `git check-ignore -q` (which exits 1 on a negation match,
  so negated paths are correctly read as trackable) and reported as
  `NOT TRACKED` with what is actually lost and how to fix it. 3 new tests,
  208 green; verified end to end against a scratch repo reproducing
  DevContainer's exact .gitignore.

- 2026-08-27 — **Published artifacts now reach their host automatically
  (`artifacts.deploy_command`).** `artifact_sync` made artifacts durable but not
  reachable: the kularia homelab serves them at `artifacts.kularia.net/<repo>/`
  via `ops/lxc/deploy-artifacts.sh`, and that was a manual second command after
  every publish. New optional shell string, run after the sync with `{dir}` and
  `{project}` substituted and bounded by `deploy_timeout` (300s). Ships EMPTY, so
  nothing runs unless a project opts in. Advisory by construction — a failed,
  slow or misconfigured deploy is reported and never fails the publish, since the
  artifact is written and committed before it runs. Verified end to end against
  the live host: publish -> mirror -> commit -> `artifacts.kularia.net` in one
  action. 7 new tests, 205 green.

- 2026-08-27 — **gh actually authenticates now; verify_gh tests the credential,
  not the binary.** The gh bootstrap step named `~/.secrets/github-pat` but its
  command was `gh auth status` — a check that persists nothing — under the
  heading "Then authenticate". So bare `gh` returned "not logged into any GitHub
  hosts" while `verify_gh` (which only tested that a binary existed) reported the
  step green. Now: `gh auth login --with-token < ~/.secrets/github-pat` persists
  it once, and `verify_gh` runs `gh auth status` with GH_TOKEN/GITHUB_TOKEN unset
  so it tests the stored credential rather than the caller's shell. Also corrects
  a DECISIONS claim that `gh auth login` mints a second credential — true of the
  interactive flow, false of `--with-token`. Every Python machine tool already
  read the PAT file directly and was never affected.

- 2026-08-27 — **kit-propagate: prune stale tracking refs, and never orphan a
  pushed branch.** Two defects found by completing a real five-repo run, one of
  them introduced by that morning's own fix. (1) The new prefix skip reads LOCAL
  `refs/remotes/origin/chore/kit-update-*`, and `git fetch` without `--prune`
  never drops the ref for a branch the remote deleted — which GitHub does on
  every PR merge. So a repo whose kit update merged would be skipped **forever**:
  one kit update per repo, then silence. The exact-branch check it replaced was
  equally stale but self-healed, because the branch name changed whenever kit
  main moved. Fixed with `--prune`. (2) `create_pr` let `urllib` exceptions
  escape, killing the run AFTER the branch was pushed — a transient
  `RemoteDisconnected` left grade5 with a branch and no PR, which the prefix skip
  then reads as "pending" forever. Now retries once and, failing that, reports
  the orphan with the exact `gh pr create` to recover.

- 2026-08-27 — **`gh` is now a machine-layer prerequisite, with a bootstrap
  step and `verify_gh`.** The GitHub MCP server disconnected repeatedly during a
  working session, leaving no way to open a PR — three had to be created through
  a hand-written REST script. `gh` is the fallback, installs without sudo into
  `~/.local/bin` (already on PATH), and authenticates from the same
  `~/.secrets/github-pat` the machine tools already own, so it adds no second
  credential. The step spells out checksum verification and the one-download-at-
  a-time rule, because a concurrent resume produced an oversized corrupt archive
  that failed its checksum and read like a network problem.
- 2026-08-27 — **kit-propagate survives a slow network and stops stacking
  duplicate update PRs.** First real multi-repo run failed two ways. (1) A flat
  `timeout=300` covered every subprocess including `safe-push`; on a link with a
  **~13s round-trip to github.com** (measured) the largest repo blew it, and the
  `TimeoutExpired` escaped as a traceback that killed the whole run — the four
  repos queued after it were never attempted. Network operations now get their
  own 1200s budget and a timeout is reported per repo instead of aborting
  everything. (2) The pending-PR skip was keyed on `chore/kit-update-<kit_head>`,
  so a single kit commit landing between runs changed the branch name, made the
  open PR invisible, and produced a SECOND overlapping PR on the same repo —
  observed on DevContainer after gh landed on kit main mid-propagation. It now
  skips while ANY `chore/kit-update-*` branch is pending.

- 2026-08-27 — **Synced artifacts are now viewable and statically servable.**
  An artifact source is a FRAGMENT by contract — the host supplies
  `<!doctype>/<html>/<body>` at publish time and rejects pages carrying their
  own — so `artifact_sync` was storing something no browser renders properly:
  quirks mode, no viewport meta. Each artifact directory now also gets a
  generated `index.html` wrapping the fragment in a deliberately minimal shell
  (the same reset the host applies, so the artifact's own styles and fonts are
  not fought), and the root gets a generated gallery. That makes the tree a
  static site with no build step: `npx serve docs/artifacts` serves `/` as the
  gallery and `/<slug>/` as the artifact. The convention is generalized from
  homeassistant's `artifacts/build.py` (2026-08-26), which solved the same
  problem by hand for one repo. Markdown sources no longer emit a redundant
  `<slug>.html` — their counterpart IS the viewable page. 6 new tests, 198 green.

- 2026-08-27 — **update.sh reports hooks it delivered but could not wire.**
  update.sh ships engine hooks and never edits `settings.json` (project-owned;
  install.sh only writes it when absent), so a hook the kit ADDS landed on disk
  unwired: it never fired, and health-check reported `[ERR] wiring drift`.
  Latent since the wiring convention settled — no new hook had shipped since —
  and first hit by `artifact_sync`, which would have taken all five repos to an
  85% health score on their next update. Reports rather than edits, matching
  install.sh's settings.json behavior, and prints the paste-ready block with the
  event and matcher read from `templates/settings.json.template`. Verified both
  directions on a scratch install: ERR before, OK after pasting.

- 2026-08-27 — **update.sh delivers commands and agents again; three commands
  promoted.** `update.sh` refreshed engine + skills only and `install.sh` is
  skip-if-exists, so an IMPROVED kit command could reach no installed repo:
  `templates/commands/pr-babysit.md` gained in-thread replies on 2026-08-13 and
  none of the five repos ever got it. Fixed without a new manifest, using a
  baseline the kit already records — `.claude/kit-version` names the kit commit
  the target was installed from, so `git show <commit>:templates/…` IS the
  as-installed file. Target still matching it => untouched => refresh; anything
  else => customized => `KEPT` and left alone. Promotions in the same change:
  `dev` (forked in DevContainer AND mylantite, 130 uses), `migration-review`
  and `security-audit` (mylantite-only, one project-specific reference each;
  meritick runs the same stack today). New machine tool `tools/mcp-audit`
  reports MCP servers with zero calls across registered repos — nine on this
  machine, eight of them in all five repos.
- 2026-08-27 — **Published artifacts now land in the repo (`artifact_sync`).**
  Artifacts are authored in the session scratchpad, which is wiped when the
  session ends: 37 publishes across two artifacts (measured across all
  transcripts) left zero files on disk. New PostToolUse:Artifact hook mirrors
  each publish into `docs/artifacts/<slug>/` — source file verbatim, a
  generated counterpart in the other format (banner-marked), `artifact.json`
  with the live URL, and a rebuilt `INDEX.md`. Idempotent on the stable
  `artifact_id`, so N republishes yield one directory; metadata a republish
  omits is carried forward rather than blanked. Commits are pathspec-scoped to
  the artifact paths, refuse on a protected branch, and never push. New
  `artifacts` key in `kit.json`; `_markdown.py` carries both (deliberately
  limited, stdlib-only) conversion directions. 27 tests.

- 2026-08-03 — **PR replies go in-thread, and addressed threads get resolved**
  (owner rule). The poller's prompt said only "reply to each addressed thread"
  and `/pr-babysit` said "reply with reasoning" — neither said *how*, and
  `add_issue_comment` is granted alongside `add_reply_to_pull_request_comment`,
  so answering an inline comment with a general PR-wall comment was the path of
  least resistance. Both now spell out the rule: **inline** comments are
  answered in their thread via `add_reply_to_pull_request_comment` (never a new
  review comment on the same line — that opens a second thread beside the
  owner's); **conversation-tab** comments have no thread on GitHub at all, so
  they get one general comment that quotes what it answers. New machine tool
  `tools/pr-thread` supplies the half that was genuinely missing: resolving a
  review thread is **GraphQL-only** — REST cannot do it and no MCP tool exposes
  `resolveReviewThread` — so "reply and resolve" could not have been fixed by
  prompt wording alone. It lists unresolved threads (node id + the comment id
  to reply to) and resolves them, owning the PAT the way `safe-push` owns push
  policy rather than putting a credential in a prompt. `resolve` **refuses
  unless a reply was posted first**, detected via the `GunAsh-` marker the
  poller already mints (replies post under the owner's PAT, so authorship
  cannot distinguish them) — making "reply, then resolve" mechanical instead of
  a prompt instruction that holds until a session is distracted. Deployed by
  `bootstrap-machine.sh`. Verified against a live PR with 29 unresolved
  threads: listing correct, resolve refused, nothing mutated.

- 2026-08-01 — **Promotion bar is now a second EXISTING repo, today — asked
  actively, and evidence-based** (owner rule). `/retro` step 4 said kit
  promotions were for things "true for EVERY project", a bar high enough to
  reject the same day's self-hosted-runner guidance (two of five repos). The
  replacement is deliberately *present-tense*: **name the existing repo that
  could implement this right now, or already has its own version** — if you
  cannot name one, it stays put. A future need is not a reason to promote;
  when that repo actually needs it, the promotion happens then, with evidence
  instead of a prediction. This is what keeps a low bar from becoming kit
  bloat. Existing duplication is the strongest signal and means the promotion
  is *overdue* — three forked copies of `split_shell_commands` lived in this
  engine, only one had learned to extract `$(…)`, and the gap let a push reach
  a protected branch. `/retro` step 4 and `/idea` step 5 now ask the question
  explicitly (`/idea` before filing, so a process another repo already runs is
  never recorded as project-local); both `CLAUDE.md`s carry the rule so every
  repo inherits it; and the `docs/ARCHITECTURE.md` §8 loop diagram reads
  "which EXISTING repo could use this today? — name it, or it stays put".
  Applicability is not universality: gate by relevance at use time, never by
  exclusion from the kit.

- 2026-08-01 — **Heredoc bodies are stripped before command splitting.** Adding
  newline to the separator set (the morning's bypass fix) made every line of a
  heredoc body parse as its own command, so `git commit -F - <<'EOF' … EOF`
  whose MESSAGE mentioned `git push origin main` blocked itself — a false
  positive sitting directly on the path of writing about the guards. Bodies are
  data, not commands: the opening line is kept, the body dropped, and a real
  command after the terminator is still found. Same principle as blanking
  quoted spans so a commit message may discuss `rm -rf` (2026-07-23). Found by
  running the kit on itself — it blocked the very commit that installed it.

- 2026-08-01 — **The kit now runs on itself.** This repo had NO repo-level
  hooks — `guard_protected_merge` never ran here in any form, and the
  machine-level guard only matches GitHub MCP tools, so a Bash `git push` to
  main was intercepted by nothing but the opt-in `safe-push`. The
  highest-consequence repo on the machine was the only one with zero
  enforcement. Installed by **wiring, not copying**: `.claude/settings.json`
  points the same 16 hook entries at `engine/hooks/_client.py`, the live
  source. A copy would be a second engine drifting from the one under
  development — the exact bug class fixed twice today (three forked splitters;
  a daemon serving pre-update hooks) — and `update.sh` refuses the kit repo
  anyway. Needs zero engine changes: `engine/hooks/` sits at the same depth as
  `.claude/hooks/`, so `PROJECT_ROOT` derivation is unchanged. Adds
  `profiles/ecosystem-kit.json` (gates: unittest suite, install round-trip,
  blast-radius review) and `.claude/kit.json`; `health-check.sh` now DERIVES
  the hooks directory from the wiring instead of assuming `.claude/hooks/`, so
  one script is honest about both layouts. Kit repo 55%/6 ERRs → **100%,
  21/21**; normal installs re-verified unchanged. Closes the 2026-08-01
  kit-not-installed-on-itself issue.
- 2026-08-01 — **Daemon staleness now covers the project profile, not just hook
  code.** `load_kit()` memoizes per process, so a long-lived daemon kept
  enforcing the OLD gates, protected branches and source patterns after an edit
  to `.claude/kit.json` — this morning's `hooks_signature()` fingerprinted
  `hooks/*.py` only. Found within minutes of running the kit on itself: the
  first `session_boot` after writing `.claude/kit.json` still reported the
  default profile. `kit.json` is now part of the signature; verified live that
  touching it retires the daemon.

- 2026-08-01 — **SECURITY: guard_protected_merge could be walked around with
  ordinary shell syntax.** `split_shell_commands` split on `&&`, `||`, `;` and
  nothing else, so `git push | tail -2` parsed as ONE command whose push
  arguments were `['|','tail','-2']` — `tail` read as an explicit, unprotected
  destination — and a push to a protected branch was allowed. Reported by a
  homeassistant session that had already pushed three commits to master
  (064294c, d5c95b2, d9f073b); it correctly declined to patch the guard itself
  and escalated upstream. Verification found the hole wider than reported:
  **18 bypass forms** — pipes (`|`, `|&`), backgrounding (`&`), newlines,
  subshells `(…)`, substitutions `$(…)` and backticks, brace groups, shell
  keywords (`do git push`, `then git push` — the KEYWORD became the command
  word), and wrapper/assignment prefixes (`sudo`, `command`, `nohup`, `env`,
  `FOO=bar`). All now blocked. The splitter is now a single implementation in
  `_constants.py` imported by all three guards; the three private copies had
  already drifted (40/56/40 lines, only one of which extracted `$(…)`), which
  is exactly how such a bug survives being fixed. Documented rule:
  over-split, never under-split — an extra fragment costs at most a false
  positive, a missed fragment is a bypass. `&` stays literal after `>` so
  `2>&1` survives intact. Engine suite 136 → 157 tests; false-positive sweep
  confirms everyday forms including `git push origin <feature> | tail -2` still
  pass. Unrelated to the kit: the reflog shows external tooling checking out
  master and pulling after PR merges (no kit tool does this — verified), which
  is what left the session believing it was on a feature branch.

- 2026-08-01 — `kit-propagate` gains a **hook-wiring policy patch**: kit hook
  wirings missing from a target's `.claude/settings.json` are appended during
  propagation. Without it, a kit change that wires an EXISTING hook onto a NEW
  event ships to installed repos as dead code — `update.sh` deliberately never
  rewrites project-owned `settings.json`, so the module updates but nothing
  calls it. Caught on the same day's pre-commit diary gate, which would have
  been silently inert in all five installed repos (and `health-check` would not
  have flagged it: `docs_contract` was still wired on its other events, so the
  roster check passed). Strictly additive — never removes, reorders, or touches
  a matcher group the template doesn't define; verified against
  homeassistant's real settings, where the project-local `guard_lint_md`
  survives untouched and a second run is a no-op.

- 2026-08-01 — **Diaries are per-MR and written as the work happens** (owner
  change). Scope: new `diary_scope` key, default `"branch"` — one entry per
  branch/MR at `.memory/diary/YYYY-MM-DD-<branch-slug>.md`, dated when the
  branch's diary started and reused for its whole life, so a change's
  discussion and decisions stay together across the days it spans; `"daily"`
  keeps the old behavior, and branch scope falls back to the dated file on a
  detached HEAD or outside git. Timing: `docs_contract` gains a **PreToolUse
  gate on `git commit`** — a pending `decision`/`discussion` flag whose diary
  hasn't been touched blocks the commit, so reasoning lands at the commit that
  carries it rather than being reconstructed at the Stop gate. Narrow by
  design: a plain `code_change` never gates a commit (it rides to Stop), and
  the `git commit` pattern is anchored to a command boundary so `echo git
  commit` can't wedge an unrelated command. `session_boot` now surfaces *this
  branch's* diary (labelling the fallback honestly); `/decide`, `/idea`,
  `/diary`, `/retro`, and the self-check skill were rewritten around
  write-as-you-go; `docs_contract.py diary-path` resolves the current file so
  command flows don't reimplement the rules. Installed repos inherit branch
  scope via `load_kit()` defaults without editing their project-owned
  `kit.json`. Also fixes a latent freshness bug the new gate exposed as a
  1-in-8 flake: mtime comparisons were strict floats against `time.time()`,
  but filesystem mtime granularity is not guaranteed finer than one second, so
  a diary written milliseconds *after* a flag could stat as older and block
  correct work — on the fast path, since `/decide` now writes the diary in the
  same turn. `touched_since()` compares at whole-second resolution,
  inclusively, for both diary and roster files. Engine suite 118 → 136 tests,
  green (20/20 consecutive runs).

- 2026-08-01 — Three fixes from the 2026-08-01 weekly-hygiene sweep, all
  self-diagnosed by the ecosystem running on itself. (1) **health-check.sh now
  ships into targets** (`.claude/scripts/`, installed + refreshed like the
  engine): targets kept whichever copy they were installed with forever, so
  DevContainer sat on a pre-`$CLAUDE_PROJECT_DIR` copy that flagged the kit's
  own canonical wiring as an ERR — a permanent red 85% health score from a
  fixed-upstream bug. Reproduced on a scratch install (ERR=1 → ERR=0 after
  `update.sh`). (2) **Daemon detects its own staleness**: it imports hooks once,
  so a daemon predating an `update.sh` enforces yesterday's rules — a stale
  `guard_protected_merge` wrongly blocked the mylantite#34 rebase on 07-31.
  Every request now compares a signature over all `hooks/*.py` (internals
  included) against load time; on mismatch it retires its socket + PID file,
  answers `Stale daemon:`, and exits, while `_client.py` treats that as a
  fall-back (never a block), clears the auto-start cooldown, and direct-execs
  the current on-disk code. Retirement is ownership-checked so a retiring
  daemon cannot unlink its successor's endpoint. (3) **session_boot counts
  drifted rosters**: `- [ ]` is the convention, but meritick's dated-bullet
  format made the banner report "ISSUES 0 unchecked" against 39 real open
  entries; the counter now falls back to per-entry dated-bullet counting
  (closure markers honored on continuation lines) and flags the drift.
  Engine suite 94 → 118 tests, green.

- 2026-07-31 — `tools/prune-stale-branches`: a daily cron (06:52) that deletes
  merged/stale LOCAL branches across every registered repo — pure git + GitHub
  API, no AI tokens. Two provably-safe tiers: Tier 1 = branches merged into the
  repo's TRUE default (`git branch -d`, which git refuses unless truly merged);
  Tier 2 = branches whose upstream is GONE **and** whose PR is API-confirmed
  merged (`git branch -D`, catches squash-merges Tier 1 can't see). NEVER
  deletes the default branch (resolved from the REMOTE's HEAD via `ls-remote
  --symref`, never the current checkout — a checkout on a feature branch must
  not make that branch look like default), the current branch, worktree-held
  branches, or main/master; a repo whose default can't be resolved is skipped
  whole. `check` mode = read-only dry-run. bootstrap-machine.sh deploys it +
  installs the cron. Dry-run across the 6 repos: 28 stale branches, 0 uncertain.
- 2026-07-30 — boot automation (owner ask: on machine reboot, start WSL → apt
  update/upgrade → start a Remote Control Claude session per repo, resume-or-
  fresh). New `tools/`: `wsl-apt-upgrade.sh` (root, safe unattended `apt-get
  upgrade` — noninteractive, keeps configs, waits on the apt lock, throttled
  once/day; WSL kernel is MS-supplied so no kernel/reboot churn), `start-remote-
  sessions.sh` (owner user: one detached tmux `claude --continue --remote-
  control … || fresh` per registered repo — idempotent, `--check`/`--list`
  modes, optional exclude file + `REMOTE_SESSIONS_MAX` cap), `wsl-boot-
  orchestrator.sh` (root: apt time-boxed then `runuser -l` → the launcher),
  `ecosystem-boot.service` (systemd oneshot, `RemainAfterExit=yes` +
  `KillMode=process` so the spawned tmux sessions survive the unit exiting),
  and `install-boot-automation.sh` (sudo installer for the root+systemd pieces).
  bootstrap-machine.sh now deploys the user launcher and has a manual step for
  the sudo/Windows install. Docs: `docs/BOOT-AUTOMATION.md`. VERIFIED on claude
  2.1.220: Remote Control needs the FULL-SCOPE login (rejects the reduced-scope
  CLAUDE_CODE_OAUTH_TOKEN — the launcher unsets it); interactive `--continue`
  EXITS 1 ("No conversation found") on a dir with no prior interactive session,
  hence the `|| fresh` fallback; end-to-end launch confirmed live + drivable
  from claude.ai/code. NOT automatable (owner-only): the sudo install and the
  Windows Task Scheduler at-logon trigger + keepalive (WSL does not boot on
  Windows reboot — it starts lazily on first access).
- 2026-07-29 — Headless launchers pass explicit --allowedTools (owner A/B = TRUST,
  not skip-permissions). Diagnosis: headless `claude -p` runs auto-mode
  unattended and blocks NETWORK git (fetch/push) + arbitrary code even in
  trusted folders with commands allowlisted — trust was necessary but not
  sufficient. Fix: weekly-hygiene/pr-comment-poller/pr-rebase now grant exactly
  their tools via --allowedTools (hygiene=local git only; poller/rebase=+safe-push
  +GitHub reply tools). Deny list (raw git push/config) + guard hooks still apply
  → far tighter than --dangerously-skip-permissions. Verified headless: network
  git fetch AND github MCP read both run under the grant.
- 2026-07-29 — guard_protected_merge now tracks `cd` and `git -C`, not just
  checkout/switch, when deciding the effective branch. Rebasing a FEATURE
  worktree onto main was wrongly blocked whenever the session's own repo sat
  on a protected branch (effective branch stayed the session repo's) — which
  also blocked the pr-rebase automation's own worktree flow. Now the branch
  actually being rewritten is evaluated; feature rebases pass, on-main
  rebases/merges/pushes still blocked. 10-case test incl. real worktree.
- 2026-07-29 — `tools/pr-rebase` + force-with-lease: a cron detects open PRs whose
  mergeable_state is 'dirty' (real base conflicts) and launches ONE headless
  session per new conflict to rebase onto base, resolve WITH understanding, run
  the gate, and (only if green) force-push-with-lease; aborts + comments
  otherwise. Never merges, never touches base. safe-push now allows
  --force-with-lease / --force-if-includes (bare --force/-f/--mirror/--delete
  still refused; protected-branch check runs first so lease-to-main is still
  refused). guard_dangerous_commands: bare force blocked, lease/if-includes
  allowed (negative-lookahead regex). `check` mode read-only.
- 2026-07-29 — bootstrap-machine.sh is now the kit-versioned home for the
  GitHub MCP tool grants the headless automation needs (read + reply/comment/
  create/update PR, both server variants; merge_pull_request still excluded/
  denied) — no more manual one-liner. Also: deploys all machine tools
  (adds kit-propagate, pr-rebase, unwedge-hooks; tolerant of missing ones),
  installs all four crons, and its manual steps skip-with-warning when run
  without a TTY instead of hot-looping.
- 2026-07-29 — Hook wiring made cwd-independent (fix/hook-cwd-wiring): settings.json.template commands now `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" <hook>` (was bare-relative, which broke every hook when a session's persistent shell cwd drifted into a subdirectory); health-check accepts the new prefix (legacy relative still tolerated), docs/README/CLAUDE/CONVENTIONS + engine docstrings updated; obsoletes the rejected forwarding-shim workaround.
- 2026-07-29 — `tools/kit-propagate`: kit changes now flow to every registered
  repo as automatic update PRs (owner still merges). Daily cron; per repo:
  worktree off origin default → update.sh → policy patches (attribution off)
  → compile+import gate on every hook (repos with project-local engine
  additions fail safe with a logged skip, never a breaking PR) → safe-push →
  PR via GitHub API. Zero AI tokens. `check` mode is strictly read-only.
- 2026-07-29 — Two owner rules encoded at the source (feature/a11y-and-design): (1) accessibility compulsory — WCAG 2.1 AA a11y gate pattern in kit.config.example.{json,md} (G6, wired into standard/full/critical), Accessibility principle §9 in engineering-principles.md, MANDATORY a11y passes in reviewer.md + qa.md (N/A only with justification); (2) design direction lives in-repo — CONVENTIONS.md.template rule + /decide step 7: design decisions update .memory/references/design-direction* first, published claude.ai artifact is a regenerated mirror.
- 2026-07-24 — Knowledge cleanup (chore/knowledge-cleanup): adaptive-ceremony.md becomes the single home of the level→pipeline mapping (express drift resolved: express review = builder's own session, never a spawned task); DA scoring, autonomy rule, handoff checklist, and the "red tests, not prose" mantra de-duplicated into single owners with pointers; diary-template absorbed into /diary and deleted; machine layer documented (README + ARCHITECTURE §11); stale identifiers fixed (HOOK_MODULES→discover_hook_modules, GitHub MCP matcher wording, kit-update qualifier).
- 2026-07-24 — Machine layer versioned + bootstrap (owner: "would a fresh
  machine configure itself?" — it couldn't; now it can). `tools/` gains
  safe-push, weekly-hygiene, and guard_protected_branch.py (previously
  hand-built, unversioned in ~/.claude), plus `tools/bootstrap-machine.sh`:
  automated machine config (deploy tools to ~/.claude/bin + hooks-machine,
  merge guardrail permissions + branch-guard hook wiring into
  settings.local.json, install both cron entries, create dirs) followed by
  interactive manual steps (SSH key, PAT, Claude login, repo registration)
  each running a confirm→VERIFY→retry loop — a failed verification re-asks
  the same step with the failure reason. weekly-hygiene refactored off its
  hardcoded repo list onto the shared machine registry
  (~/.claude/repo-registry) — same review finding as the poller; both tools
  now read it, and the poller's register/unregister manages it. Tools
  auto-detect the claude binary (CLAUDE_BIN override supported).
- 2026-07-24 — `tools/pr-comment-poller`: cron-driven GitHub poller closing the
  "owner comments on a PR, nobody notices until a session opens" gap. Pure API
  polling (no AI cost) until new owner comments appear on an open PR, then one
  headless `claude -p` run in that repo addresses them (worktree for code,
  safe-push, signed replies via trailing marker for loop safety, never merges).
  Credential comes ONLY from owner-provisioned `~/.secrets/github-pat` — the
  tool never scrapes tokens from any config.
- 2026-07-23 — Verification fix pass (16 verifier findings): daemon cooldown file renamed `.daemon.start_attempt` so the `.daemon.*` gitignore glob covers it; installed `.memory/` layout now survives a git round-trip (tracked `cache/.gitignore` = `*`+`!.gitignore`, root `.memory/cache/` snippet line removed + scrubbed on re-install, `.gitkeep` seeded into empty `diary/`/`auto/`); WHERE-less DELETE check mirrors the UPDATE rule (quoted `mysql -e "DELETE FROM x"` now blocked); filesystem/git guard patterns ignore quoted text (commit messages mentioning `rm -rf` no longer block); docs_contract + tdd_gate skip out-of-repo files; conductor delegates write-phases instead of "running them itself"; `/decide`+`/idea` drop docs_contract flags; `file_write_rules` added to schema defaults/example/doc; README/ARCHITECTURE/kit.config.example.md drift corrected. Verified: engine suite 94/94, fresh meritick install + clone round-trip 0 ERR, 8/8 behavioral hook checks.
- 2026-07-23 — install.sh now renders `{{PROJECT}}`/`{{STACK}}`/`{{DATE}}`/`{{REPO_ABS}}` when seeding the `.memory/` roster and CLAUDE.md (was verbatim copy — seeded STATE.md carried a literal `{{DATE}}`, so session_boot's staleness regex could never match); gitignore.snippet gains `.claude/hooks/__pycache__/` (daemon imports write bytecode into target repos); ISSUES/VERIFY template format-examples re-quoted mid-line so session_boot's `- [ ]` counter reads 0, not 1, on a fresh install. Verified by a scratch-repo install: render, idempotent re-run, live session_boot, health-check 17 OK.
- 2026-07-23 — kit v1.0.0 authored
- 2026-07-23 — installer/updater/health-check verified end-to-end against the real engine+templates for all five profiles (install, re-run idempotency, update scope, drift detection, error paths); engine suite 90/90 green
