# 2026-08-27 — fix/update-reports-unwired-hooks

## Found by testing the interaction, not either change

PRs #25 (artifact_sync) and #26 (command delivery) were both green in isolation
and merged clean into each other. The bug lives in what happens *after* both
land, and only showed up because I installed a repo from the pre-artifact_sync
commit and ran the new `update.sh` against it:

```
NEW      .claude/hooks/_markdown.py
NEW      .claude/hooks/artifact_sync.py

Artifact matcher wired: False
[ERR]  wiring drift: hook modules on disk but not wired: artifact_sync
Health score: 85% (17/20)
```

The hook arrives and never fires. All five repos would have hit this on their
next `update.sh`.

## It is older than both PRs

Not a regression — a latent flaw. `update.sh` has always refreshed
`.claude/hooks/` while never touching `settings.json`, so **any** hook the kit
added would have landed unwired. Nobody hit it because no new hook had shipped
since the wiring convention settled. `artifact_sync` is simply the first.

CLAUDE.md's "no hardcoded hook rosters" rule says adding a hook means *a file
plus wiring it in the settings template*. Both happened. What was missing is any
path from the template to an already-installed repo's `settings.json` — the
template is only consulted at install time, and only when the file is absent.

## Report, don't wire

The tempting fix is for `update.sh` to merge the missing block into
`settings.json` itself. Rejected: that makes the updater edit a project-owned
file, which contradicts `install.sh` (writes settings.json only when absent,
otherwise prints a manual-merge instruction) and risks clobbering per-project
matcher tuning. mylantite's settings are not the template's.

So it prints the paste-ready block instead, reading the event and matcher from
`templates/settings.json.template` — the kit already knows *where* each hook
belongs, that knowledge just wasn't reaching the user:

```
  ACTION   1 hook(s) delivered but NOT wired — they will not fire:
             - artifact_sync

  "PostToolUse": [
    { "matcher": "Artifact", "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py\" artifact_sync" } ] }
  ]
```

health-check already *detected* the drift correctly. The gap was delivery UX,
not detection — which is why the fix is a printer, not a new check.

## Verified both directions

Per CLAUDE.md, installer changes are proven by installing, not by unit tests.
On a scratch install made from `0eb066a` (pre-artifact_sync):

- before: `[ERR] wiring drift … artifact_sync`, health 85%
- paste exactly the printed block
- after: `[OK] settings.json wiring == hook-module glob`, and a re-run of
  `update.sh` reports `OK  every delivered hook is wired in settings.json`

The 90%-not-100% after the fix is the empty scratch repo's unrelated warnings
(no diary yet, STATE never validated), not wiring.

## Sequencing note

#25 and #26 are already merged, so this could not ride on either. Propagation to
the five repos should wait for this — otherwise every repo takes the ERR and
`artifact_sync` silently does nothing in all of them.
