---
description: Pull the ecosystem kit and apply its engine/skills update to this repo
---

Update this repo's installed ecosystem from the kit.

1. Locate the kit checkout (default `~/ecosystem-kit`; ask if it isn't
   there) and `git pull` it. Compare the kit's version against this repo's
   `.claude/kit-version` and skim the kit's git log for what changed between
   them.
2. Run `bash <kit>/installer/update.sh <this-repo-abs-path>` — it refreshes
   the engine hooks and skills only; it never touches `.memory/`,
   `.claude/kit.json`, or project-customized commands/agents.
3. Review the result: read update.sh's change report, `git diff` the
   `.claude/` tree, and read any changed hook before trusting it.
4. Sanity-check the wiring: every non-underscore hook in `.claude/hooks/`
   appears in `.claude/settings.json`; run the kit's `scripts/health-check.sh`
   against this repo.
5. Restart the session so the refreshed hooks/daemon take effect. Commit the
   update on a `chore/` branch with a `.memory/DOCS-CHANGELOG.md` line —
   never on a protected branch.
