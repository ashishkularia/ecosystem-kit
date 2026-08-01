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

**Open:** whether all three are warranted or just the skill. My instinct is the
skill plus the context template earn their place immediately, and the reference
doc only if the generic principles turn out to be more than a page. Ashish
decides; this is an IDEAS entry, not a plan — the kit's own rule is that ideas
are never acted on unasked.
