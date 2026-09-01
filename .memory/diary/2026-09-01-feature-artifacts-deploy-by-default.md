# 2026-09-01 — feature/artifacts-deploy-by-default

## The question

Owner: "all repos have not posted the artifacts. should it be automatically?
like all the artifacts gets published."

## What was actually wrong

`artifact_sync` does two things after a publish, and only one of them was
automatic anywhere:

| step | config | default | reach |
| --- | --- | --- | --- |
| mirror + commit | `artifacts.enabled` / `commit` | `true` | all 6 repos |
| deploy to a host | `artifacts.deploy_command` | `""` | 3 of 6 repos |

Live on LXC 102 at run start: `devcontainer`, `ecosystem-kit`, `homelab`.
Missing: mylantite (1 artifact) and meritick (1 artifact) — both mirrored, both
committed, both tracked in git, both reaching no host since 2026-08-27. grade5
has published none, so it had nothing to miss.

Root cause: **zero of the seven profiles carried an `artifacts` key at all.**
Every repo that deployed did so because someone hand-edited `.claude/kit.json`
after install. A fresh install of any profile deploys nothing, forever, and says
nothing about it — `deploy()` returns `None` on an empty command, so the hook
report just omits the line.

## The design tension, and how it resolved

The seam itself was right. DECISIONS 2026-08-27 deliberately made
`deploy_command` a shell string rather than a kit-owned deploy tool, because the
only concrete implementation knows a Proxmox host, CTID 102, an nginx LXC and
`artifacts.kularia.net` — project-bound infrastructure the promotion rule keeps
out of the kit. That reasoning still holds and was not overturned.

But it left profiles with two bad options: hardcode
`/home/ubuntu/homeassistant/ops/lxc/deploy-artifacts.sh` (a per-machine absolute
path in a shared kit, making four repos' deploys depend on a fifth being checked
out at one exact location — which is literally what DevContainer's kit.json does
today, with nothing detecting the break), or ship nothing. Shipping nothing is
what happened.

Third option, and the one CLAUDE.md's promotion rule actually prescribes —
*"gate a kit artifact by relevance at use time (a skill that no-ops where it
doesn't apply), never by excluding it from the kit"*: the kit ships the seam and
the relevance gate, the machine supplies the destination.

- `tools/deploy-artifacts` — dispatcher, resolves `$ARTIFACTS_DEPLOY_IMPL` then
  `~/.claude/artifacts-deploy`, execs it with `<project> <dir>`.
- All seven profiles: `bash "$HOME/.claude/bin/deploy-artifacts" {project} {dir}`.
  No `/home/ubuntu` literal, no PATH assumption (the hook's `subprocess` PATH is
  inherited and not guaranteed to include `~/.claude/bin`).
- `bootstrap-machine.sh` deploys it and now warns when no destination is linked.

## Why it exits non-zero when unconfigured

Tempting to exit 0 with a friendly note. That reproduces the exact bug being
fixed — a publish reporting success having posted nothing — except in every repo
instead of two. The deploy is advisory and runs *after* the commit, so a
non-zero exit costs a warning line and never the artifact. A repo that must
never publish says so with `deploy_command: ""`.

## The half that profiles cannot fix

A profile is copied to `kit.json` once at install and is project-owned forever
after; `update.sh` never touches it. So profile changes fix new installs and no
existing one — the same shape as the 2026-08-01 hook-wiring gap. Hence a fourth
`kit-propagate` policy patch, `patch_artifacts_deploy`, which copies the key
from the profile whose `project` matches the target's (so profiles stay the
single source of truth and the patch needs no editing when the seam moves).

Strictly add-only, and that includes an explicit `""`: a repo saying "never
publish me" is a decision, and a policy patch must not be louder than the
project it patches. 7/7 on a scratch fixture run — absent key set, custom value
kept, `""` kept, sibling keys preserved, unknown project no-op, idempotent on
second run, missing kit.json survived.

## Loose ends

- **Backfill is not done.** Posting mylantite's and meritick's existing
  artifacts needs `~/.claude/bin/deploy-artifacts <project> <dir>`, which ssh's
  to the Proxmox host and replaces a served directory; the auto-mode classifier
  blocked it and it is the owner's to run.
- DevContainer's hardcoded path and `artifact_sync`'s silence on an empty
  `deploy_command` are both logged in IDEAS rather than fixed here.
- Worth noting the exposure this generalizes: the deploy script's own header
  says there is no IDP in front of `artifacts.kularia.net` — LAN/tailnet-only
  but unauthenticated within it. Every repo publishing by default means every
  mirrored artifact becomes LAN-readable. `deploy_command: ""` is the per-repo
  opt-out if that is ever the wrong trade for a business repo.
