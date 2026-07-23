# GOTCHAS — ecosystem-kit

- 2026-07-23 — bash: `((x++))` returns exit status 1 when x was 0, so under `set -e` it kills the script. Use `x=$((x+1))` in `-e` scripts; `health-check.sh` additionally runs without `-e` because its checks fail on purpose.
- 2026-07-23 — jq is NOT installed on the hosts; every JSON read/write in shell must go through python3.
- 2026-07-23 — The permission classifier blocks top-level agent `cp`/`mv` across directories (and `sed`/`awk`); agents author kit files with the Write tool. Those same commands are fine INSIDE scripts the agent authors (installer, updater, test harnesses).
- 2026-07-23 — Hooks compute PROJECT_ROOT from `realpath(__file__)`; a symlinked `.claude/hooks/` would resolve to the kit repo instead of the project — one more reason install is copy-only.
- 2026-07-23 — Stop hooks MUST honor `stop_hook_active` or they block their own stop forever; `docs_contract` carries the loop-guard.
- 2026-07-23 — `.memory/cache/.gitignore` containing `*` ignores itself too, so the file is never tracked; fresh clones get `cache/` recreated by the installer or the first hook run. Accepted trade-off (see ISSUES).
- 2026-07-23 — `engine/hooks/tests/` must never be installed into targets; `install.sh`/`update.sh` glob `engine/hooks/*.py` only (flat), which naturally excludes the tests dir, and `health-check.sh` warns if a `hooks/tests/` dir shows up in an installed repo.
- 2026-07-23 — `git rev-parse --show-toplevel` returns a physical path; compare against `pwd -P`, not `pwd`, or symlinked checkouts fail the "is repo root" check.
