# Diary — docs/idea-runner-cicd-guide

Started 2026-08-01 · PR # (fill in once opened)

## Session — capturing the runner/CI learning before it evaporates

Dear diary,

Ashish asked to record an idea: guidance for standing up self-hosted GitHub
runners and troubleshooting CI pipelines, drawn from mylantite, which just
implemented it. He then clarified the shape is open — "skill or reference or
steps, whichever guides it straight on how to do it."

**Discussed:** This is the kit-promotion loop in `docs/ARCHITECTURE.md` §8
firing exactly as designed: a project learns something the hard way, and the
question becomes whether the learning is project-specific or belongs to every
repo. mylantite's `.memory/contexts/ops-ci.md` is genuinely excellent — it
documents a container-based CI pattern where every self-hosted job runs inside
the app image via a composite action, so nothing depends on tools installed on
the runner box.

The tension worth naming, and the reason this idea needs thought rather than a
straight copy: **the kit is project-agnostic and mylantite's document is not.**
Names like `mylantite-ci`, `mylantite_app-network` and `/opt/ci-deps` are
specific; the *principles* underneath them are not. "Self-hosted jobs must not
assume tools on the runner host" is universal. "Tag the CI image with a hash of
the dependency manifests so a stale image can never be silently used" is
universal. Copying the document into the kit would ship mylantite's topology to
homelab and grade5, which is the per-project fork the kit's own CLAUDE.md warns
against.

I checked before proposing: the kit today has **no** runner or CI guidance at
all — the only match for "runner" in `templates/` is "test runner" in
`fix-test-failures.md`, unrelated.

**Decided (proposal shape, for Ashish to rule on):** split by *nature of the
content*, which is how the kit already separates its artifacts —

- The **diagnostic loop** is behavior, so it wants a skill, modelled on
  `fix-test-failures.md`: symptom → likely cause → the command that
  distinguishes them. It stays project-agnostic by reading specifics from
  `kit.json` and the project's own `.memory/contexts/ops-ci.md`, exactly as
  `fix-test-failures` reads `quality_commands.test`.
- The **setup facts and invariants** are durable knowledge, so they want a
  `templates/memory/references/` doc — the kit already ships three
  (`engineering-principles`, `da-checklist`, `team-member-protocol`).
- A per-project `contexts/ops-ci.md` **template** is the third piece: it gives
  each repo the *shape* to fill in (which jobs run where, and why) without the
  kit asserting any repo's topology.

**Added after a second pass over mylantite's ISSUES:** the trap I had missed is
the most generalizable one in the set — **tests that read secrets fail on CI
because the secrets are not there.** mylantite's backend suite needed Stripe
credentials; the CI fix appended placeholders in `backend.sh`, which fixes CI
only. The proper home is a tracked default (`phpunit.xml` `<env>`), and the
reason it wasn't done immediately is the interesting part: it has to be checked
against the test runner's override semantics, or a developer holding REAL keys
gets silently switched to a placeholder. That is exactly the shape of thing a
guide should carry — not "add placeholders", but "here is why the obvious fix
is the wrong home, and what to check before moving it."

Also worth recording as the *why now*: meritick's move wasn't a design choice.
The commit reads `ci: move to the box's self-hosted runner — GitHub-hosted
stopped assigning`. Guidance that assumes self-hosting is a considered
architectural decision will miss the common case, which is that someone ran out
of hosted minutes on a Friday.

## Session — the digest, and why it changed my mind about scope

Dear diary,

The thorough cross-repo sweep came back and it was worth waiting for: it found
substantially more than my first pass, and two items reframe the work.

**First, there is no runner-provisioning runbook anywhere.** Grepping
`--labels|--unattended|registration token|config.sh` across both repos and the
harness returns nothing. Every scrap of registration knowledge is post-hoc — a
`config.out` file, a `.runner` blob, a stale shell script. So this isn't tidying
existing docs into a skill; the primary artifact doesn't exist yet. That makes
the case stronger, not weaker.

**Second, and this is the one I keep thinking about: the runner bakes the
interactive shell's PATH at `config.sh` time.** I verified it — `meritick-1/.path`
opens with nvm's node v24.15.0 and then lists *sixteen Claude Code plugin cache
bin directories*. So the runner's Node is whatever nvm happened to be on the day
someone registered it, a later `nvm use` never reaches it, and unrelated local
tooling leaks into CI's PATH.

That is the *same bug* as this morning's homeassistant failure, where
`guard_lint_md` ran under `/usr/bin/node` v18 while the shell had v24 — just
pointing the other way. Twice in one day, the same root cause: **the environment
a background process inherits is not the one you typed in.** If the eventual
guidance carries one sentence, it should be that one.

**Decided:** capture the digest as `.memory/references/runner-ci-field-notes.md`
rather than inflating the IDEAS entry. Reasons: an idea should stay readable, the
material is research and belongs in `references/`, and pointing the entry at
mylantite's docs alone would rot — those docs are a live project's and will move.
Marked explicitly as research not doctrine, and noted that the kit's `.memory/`
never ships to targets, so nothing project-specific leaks by holding it here.
Claims I verified on the box are marked ✓; the rest are quoted with their source
repo, so a future builder knows what is checked and what is hearsay.

**A judgement I want to flag as mine, not evidence:** I did not fold every
finding into the proposal. Things like mutation-testing ratchets and CI image
pruning are real but belong to whoever builds the thing, not to the decision
about whether to build it. The entry stays a proposal; the notes carry the depth.

**Open:** whether all three are warranted or just the skill. My instinct is the
skill plus the context template earn their place immediately, and the reference
doc only if the generic principles turn out to be more than a page. Ashish
decides; this is an IDEAS entry, not a plan — the kit's own rule is that ideas
are never acted on unasked.
