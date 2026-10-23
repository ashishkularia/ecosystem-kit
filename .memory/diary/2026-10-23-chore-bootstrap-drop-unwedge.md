# chore/bootstrap-drop-unwedge

## Session — 2026-10-23

- **Context:** the owner asked to keep only the scripts and commands they will
  actually use. `~/.claude/bin` held four files that no kit tool, cron entry or
  settings file references: `merge-dc-constants.py` (its target worktree is
  gone), `phase1-strip-hooks.py` (a July one-time hand-off),
  `resolve-pr-conflict.sh` and `unwedge-hooks.py`. They were moved to
  `~/.claude/bin-retired-2026-10-23/`, not deleted, since no repo holds a copy.
- **Changed:** `tools/bootstrap-machine.sh` stops listing `unwedge-hooks.py`,
  which had never been in `tools/` and made each run print a warning.
- **Verified:** `bash -n` passes; no other file in the kit names the script.
