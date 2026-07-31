# Diary — feature/diary-per-mr

Started 2026-08-01 · PR # (fill in once opened)

<!-- Branch-scoped diary (diary_scope: "branch"): one entry per branch/MR,
appended to as the work happens. New blocks go at the BOTTOM; earlier blocks
are never rewritten. This file is the first one written in the format it
introduces. -->

## Session — designing the per-MR diary

Dear diary,

**Discussed:** Ashish asked for two changes to how diaries work. One, key them
to the MR instead of the day, so all of a change's decisions and discussion live
in one place. Two — and this is the part with teeth — stop writing the diary at
the end. "Diary should be updated alongside the work as decisions are made or
discussions are happening."

The second is the real ask. The first is mostly naming; the second is a change
to *when a gate fires*, and the old design only ever checked at the Stop gate,
which by construction is the end. So a "diary" under the old rules was always a
reconstruction written from whatever survived in context.

**Decided:**

- File is `.memory/diary/YYYY-MM-DD-<branch-slug>.md`, dated when the branch's
  diary STARTED and then reused for the branch's whole life. Considered keying
  on the PR number instead (`PR-16-*.md`) and rejected it: the number doesn't
  exist when the work starts, which is exactly when the first entry needs
  writing. Branch name is knowable from the first keystroke. Keeping the date
  prefix means the filenames still sort chronologically, which several readers
  rely on.
- Fall back to the old dated file on a detached HEAD and outside a git repo. A
  diary keyed on a branch that doesn't exist is worse than a dated one.
- New `diary_scope` key, defaulting to `"branch"`, with `"daily"` preserving the
  old behavior. Because `load_kit()` merges defaults, every already-installed
  repo picks up branch scope without anyone editing its project-owned
  `kit.json`.
- The incremental part is enforced at **`git commit`** (PreToolUse), not by a
  timer or an edit counter. A commit is a natural checkpoint that is emphatically
  *not* the end of the session, and it is exactly when the reasoning behind the
  change is still loaded in your head.
- That gate is deliberately narrow: only `decision` and `discussion` flags gate
  a commit. A plain `code_change` still rides to the Stop gate. I did consider
  gating every commit on a fresh diary entry and rejected it — a hook that
  interrupts routine commits with nothing useful to say is how a guard trains
  people to work around it. Reminder fatigue is a real failure mode; the kit's
  own CLAUDE.md warns about it for `source_patterns`.
- `/decide` now writes the diary block in the same turn as the DECISIONS line.
  DECISIONS holds the rule; the diary holds the story around it — what was
  considered, what was rejected, what nearly went wrong.

**Done:** `diary_path()`/`current_branch()`/`branch_slug()` in docs_contract, the
PreToolUse commit gate, a `diary-path` CLI so command flows don't reimplement
the resolution rules, `session_boot` now showing *this branch's* diary (and
labelling honestly when it's falling back to someone else's), the
`diary_scope` key across defaults + example + schema doc, and the command and
skill templates rewritten around write-as-you-go. 135 tests green, up from 118.

**A bug my own test caught:** the first `git commit` pattern was
`\bgit\s+commit\b`, which matches `echo git commit`. In advisory
`guard_commit_message` that's a harmless false positive; here it *blocks*, so it
would have wedged unrelated commands. Anchored it to a command boundary (start
of string, or after `;`/`&&`/`||`/`|`/newline). The lesson generalizes: a
pattern's precision requirement scales with the severity of what it triggers,
so copying a matcher from an advisory hook into a blocking one is not a safe
refactor.

## Session — the flake that was actually a bug

Dear diary,

Appending mid-work, which is the whole point of the change I'm making.

The suite went green, then failed once, then passed seven runs in a row. A
blocking hook that fails 1-in-8 is worse than one that fails always, so I chased
it: `test_writing_the_diary_unblocks_the_commit`, exit 2 instead of 0.

**The cause was not the test.** `diary_satisfied()` compared a float
`time.time()` captured when the flag was set against the diary's filesystem
mtime, strictly greater. Filesystem mtime granularity is not guaranteed finer
than one second — it is exactly 1s on several filesystems — so a diary written
milliseconds *after* the decision can stat as older, and the gate blocks someone
who did exactly the right thing. Worse, it targets the **fast path**: `/decide`
now writes the diary in the same turn, so the sub-second case is the normal case,
not the exotic one. This bug was latent in the old Stop gate too; the old tests
never saw it because they set mtimes an hour apart.

**Decided:** compare at whole-second resolution, inclusively (`touched_since()`).
The cost is a sub-second window where a diary written just *before* the flag
counts as satisfying it. That is the right trade: a gate that occasionally lets
a same-second write through is a rounding error, while a gate that fires on
correct behavior teaches people to distrust it — and this one blocks commits.

**Done:** `touched_since()` replaces both strict comparisons (diary and roster
files). Regression test loops 25 times, because the original bug survived seven
consecutive green runs; suite then stress-run 20× consecutively, 20/20 green,
136 tests.

**The lesson worth keeping:** an intermittent test failure in a gate is a
correctness report, not noise. My first instinct was "timing artifact in the
test" — it was a real false-block that users would have hit on the most common
path, and re-running until green would have shipped it.

## Session — wrap-up

**Open:** existing repos keep their old dated entries — nothing migrates, and
the fallbacks read them fine, so I left them alone rather than rewriting
history that people wrote by hand. Worth watching whether the commit gate feels
right in practice; if it nags, the narrow flag set is the first dial to turn.
