# 2026-08-27 — feature/artifact-sync

## Where this came from

A `/doctor` run on the kit repo, which turned into a promotion sweep across all
five registered repos, which turned into this. The owner's ask: *"I wanna commit
all the artefacts as html to their git repos... any artefact created will be
synced with git repo in the form of html. Along with artefact, we will also have
the md file of it."*

The promotion bar cleared itself immediately. Scanning every transcript for
`Artifact` tool calls found **37 publishes, all from DevContainer**, across two
artifacts (`ecosystem-plan.html`, `prod-decision.md`) — and every one of them
was published from `/tmp/claude-1000/.../scratchpad/`, which is wiped when the
session ends. Thirty-seven publishes, zero surviving files. DevContainer is
doing this today; that is a named existing repo, not a prediction.

## Probing beat guessing, three times

I nearly wrote the hook against the payload shape shown in the transcripts. Wiring
a throwaway probe build of `artifact_sync.py` first and publishing one real
artifact corrected three things that would each have been a bug:

1. `tool_response` is a **dict**, not the text blob the transcript renders. A
   regex over `"Published <path> at <url>"` would have been fragile for nothing.
2. It carries a stable **`artifact_id`**. That is the idempotency key — without
   it, 37 republishes make 37 directories.
3. **`title` never appears in `tool_input`.** I did not pass one; the tool
   resolved it from the `<title>` tag and returned it. Reading title from the
   input would have named every directory after a temp file.

The probe cost one publish. It saved a rewrite.

## What the tests caught, and what only the live run could

Unit tests caught a genuine bug: `head` was in `_SKIP_TAGS`, so `<title>` was
swallowed before the parser could reach it and every digest came back titleless.

But the commit path passed 25 unit tests and still failed live:

```
commit failed: error: pathspec 'docs/artifacts/claude-code-checkup'
did not match any file(s) known to git
```

`git commit -- <paths>` is a partial commit over paths git **already knows**. On
an artifact's first publish every file is untracked, so it always failed — the
one case that matters most. My fake-git harness answered `status` with a dirty
path, which made the untracked case invisible. Fixed by staging the artifact
paths first; the test now asserts `add` precedes `commit`, is pathspec-scoped,
and never uses `-A`/`--all`/`.`.

A second live-only bug: republishing with just a `label` blanked `description`
in `artifact.json`, because a republish carries only `file_path` + `label` and
the hook overwrote metadata blind. Prior values are now carried forward.

Lesson worth keeping: a fake that always reports the *steady* state hides the
*first-run* state, and first-run is where this hook lives.

## The one real design constraint

Stdlib-only means no `markdown` and no `html2text`, so the HTML↔MD pair cannot
be lossless both ways. Rather than pretend, the published format is stored
byte-for-byte and the counterpart is generated with a "do not edit" banner:
md→html renders a documented subset, html→md is an explicitly lossy digest.
The owner picked this over a metadata-only sidecar, accepting the approximation.

## Owner override, recorded

I recommended write-only with no commit — a hook that commits mid-session can
sweep up unrelated staged work. The owner chose auto-commit on by default. That
is their call; what makes it safe is the scoping: `git add --` then
`git commit --` over the artifact paths only, so the rest of the index is
untouched, plus refusals on protected branches, detached HEAD, and
mid-merge/rebase, and never a push.

Pleasing moment: `guard_dangerous_commands` blocked my own `rm -rf docs/artifacts`
while resetting for a retest. The engine works.

## Still open on this branch

- The four earlier promotion findings are queued next: the commands-delivery
  gap in `update.sh` (kit commands improve and reach nobody — `update.sh`
  refreshes engine + skills only, and `install.sh` is skip-if-exists), promoting
  `dev` (forked in DevContainer *and* mylantite, 130 uses), promoting
  `migration-review` + `security-audit` (one mylantite-specific reference each,
  meritick runs the same stack), and a machine-layer MCP audit.
- `.memory/STATE.md` still says the repos are stamped from `7e0d2d8`/`59916b5`;
  all five are actually on `13dcdcf`.
