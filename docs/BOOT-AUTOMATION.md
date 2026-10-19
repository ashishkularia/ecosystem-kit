# Boot automation — apt upgrade + Remote Control sessions on machine start

**Goal (owner, 2026-07-30; re-pointed at native Ubuntu 2026-10-20):** when the
machine boots, run `apt update && upgrade`, and then open a Claude Code **Remote
Control** session per registered repo — each resuming its last conversation or
starting fresh — so you can pick any of them up from
[claude.ai/code](https://claude.ai/code).

It was written for WSL, where the first half of the chain lived on the Windows
side. On a native Ubuntu machine that half simply disappears: systemd is PID 1
from power-on, so there is nothing to start and nothing to keep alive.

## The chain

```
power on / reboot
   │   (no login needed — this is a system unit)
   ▼
systemd (PID 1)
   │
   ▼
ecosystem-boot.service  (oneshot, After=network-online.target)
   │
   ▼
/usr/local/sbin/ecosystem-boot-orchestrator.sh   (root)
   ├─ 1. /usr/local/sbin/ecosystem-apt-upgrade.sh   (root, throttled once/day, time-boxed)
   └─ 2. runuser -l <owner> → ~/.claude/bin/start-remote-sessions.sh
             └─ per repo: tmux → claude --continue --remote-control …
```

## Components

| File (in kit `tools/`) | Installed to | Runs as | Purpose |
|---|---|---|---|
| `ecosystem-apt-upgrade.sh` | `/usr/local/sbin/` | root | Safe unattended `apt upgrade`, throttled to once/day |
| `start-remote-sessions.sh` | `~/.claude/bin/` | owner | One detached tmux Remote Control session per repo |
| `ecosystem-boot-orchestrator.sh` | `/usr/local/sbin/` | root | Sequences apt → sessions; the unit's ExecStart |
| `ecosystem-boot.service` | `/etc/systemd/system/` | root | systemd oneshot that fires at boot |
| `install-boot-automation.sh` | — (run with sudo) | root | Installs the above (owner-run) |

The user launcher is deployed by `bootstrap-machine.sh` (no sudo); the root
pieces are installed by `sudo bash tools/install-boot-automation.sh`, which also
installs `tmux` (the launcher needs it).

## Install

```bash
# 1. user side (no sudo) — deploys start-remote-sessions.sh to ~/.claude/bin
bash tools/bootstrap-machine.sh

# 2. root side (sudo) — tmux, /usr/local/sbin scripts, systemd unit
sudo bash tools/install-boot-automation.sh

# 3. test the chain WITHOUT rebooting
sudo systemctl start ecosystem-boot.service
journalctl -u ecosystem-boot -b
~/.claude/bin/start-remote-sessions.sh --list
```

Then reboot once. That is the only test that proves the boot path: after you log
in, `start-remote-sessions.sh --list` should already show the `claude-*`
sessions and `systemctl status ecosystem-boot` should read `active (exited)`.

## Before you rely on it

- **Trust every registered repo once.** `cd <repo> && claude`, accept the prompt.
  An untrusted folder's session sits at the trust prompt inside tmux, where
  nobody can see it, and never comes online. Trust is recorded per *path*, so a
  repo reached through a symlink can look trusted while its real path (the one in
  `~/.claude/repo-registry`, which is what the launcher uses) is not — check the
  registry path itself. Agents cannot set folder trust.
- **Auth must be the full-scope login** (`claude auth login`, cached in
  `~/.claude/.credentials.json`). See the risk flags below.

## Honest risk flags

- **Unattended `apt upgrade` makes system changes with no one watching.** It's
  restricted to `upgrade` (never removes packages), keeps your existing config
  files, waits for the dpkg lock, and is throttled to once/day. Native Ubuntu
  specifics:
  - **It overlaps `unattended-upgrades`.** That service is normally already
    enabled and covers *security* updates; this step is a second, broader
    upgrader (every update). They serialize on the dpkg lock, they don't corrupt
    each other. To keep only the sessions, delete the deployed copy —
    `sudo rm /usr/local/sbin/ecosystem-apt-upgrade.sh` — and the orchestrator
    skips the step and carries on.
  - **It can install a new kernel and never reboots.** The new kernel takes
    effect at the next reboot you do yourself; `autoremove --purge` keeps the
    running one. (Under WSL the kernel was Microsoft-supplied, so this didn't
    arise.)
  - To pause everything: `sudo systemctl disable ecosystem-boot.service`; to
    freeze specific packages, `apt-mark hold`.
- **N Remote Control sessions auto-start.** Idle sessions cost little (quota is
  spent only when you send a turn), but each is a live login to
  api.anthropic.com. Trim with `~/.claude/remote-sessions.exclude` (one repo
  path per line to skip) or cap with `REMOTE_SESSIONS_MAX=<n>`.
- **Auth is the fragile bit.** Remote Control requires the **full-scope**
  `claude auth login`. It **rejects** the reduced-scope
  `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` (that token is only for the
  headless `claude -p` cron tools). The launcher unsets it defensively. If
  sessions fail with a scope/login error, run `claude` once interactively and
  re-login.
- **A dead session doesn't self-revive at boot only.** `start-remote-sessions.sh`
  is idempotent — re-running revives sessions that died (e.g. a >10-min network
  outage exits Remote Control). To auto-revive, add an OPT-IN cron (not installed
  by default):
  `*/30 * * * * /home/<owner>/.claude/bin/start-remote-sessions.sh >> ~/.claude/remote-sessions.log 2>&1`
  Note the launcher treats any existing `claude-<repo>` tmux session as healthy,
  so a session that is alive but wedged is not revived (see `.memory/ISSUES.md`).

## Operate

```bash
start-remote-sessions.sh            # launch/ensure sessions (idempotent)
start-remote-sessions.sh --check    # dry-run: what would launch
start-remote-sessions.sh --list     # running claude-* tmux sessions
tmux attach -t claude-<repo>        # drive one locally (Ctrl-b d to detach)
sudo ecosystem-apt-upgrade.sh --dry-run   # preview the apt step
journalctl -u ecosystem-boot -b     # boot-chain log for this boot
sudo systemctl disable ecosystem-boot.service   # turn the whole thing off
```

## If this ever runs under WSL again

The Linux side is identical, but WSL does not start on Windows boot — it starts
lazily and the VM idle-shuts-down after ~60s — so nothing would fire the unit.
The Task Scheduler recipe that solved that (at-logon trigger running
`wsl.exe -d <Distro> -u root -e /bin/sh -lc "sleep infinity"`, with "Run only
when user is logged on") was removed from this file when the machine moved to
native Ubuntu; it is preserved at commit `292b926`:
`git show 292b926:docs/BOOT-AUTOMATION.md`. `install-boot-automation.sh` warns
when it detects WSL.
