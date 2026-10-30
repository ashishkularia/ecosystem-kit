# 2026-10-30 — fix/claude-md-blocks-blank-lines

## What happened

The owner asked for mylantite to be brought up to date after #54 merged.
`update.sh` took it from `07d4731` to `1b21ef5` and inserted the scratch and
vault blocks into its CLAUDE.md, and `prettier --check` then failed on four
lines: Prettier wants a blank line between each marker comment and the heading
or text beside it. Mylantite's CI lint runs Prettier on CLAUDE.md, so the
update could not go green. Formatting the project's copy lasts only until the
next update, because `kit_blocks.py` copies each block from the template
verbatim and compares it line for line.

## The fix

The blank lines now sit in the template, and a `ShippedTemplateTest` case holds
every block to them. Against the old template it fails for both blocks; the
full engine suite (310 tests) passes with the fix.

## Why the blocks were missing at all

The cron runs the copy of `kit-propagate` in `~/.claude/bin/`, dated
2026-09-02. It predates the 2026-10-20 change that stages CLAUDE.md, so every
kit-update PR it opened on 2026-10-29 (mylantite #244 and five others) lost
the inserted blocks with its worktree. Every other deployed tool matches
`tools/`. `bootstrap-machine.sh` redeploys it; the script is interactive, so
the redeploy is the owner's, after this merges, so that the next run carries
blocks that pass Prettier.
