# Boot automation — apt upgrade + Remote Control sessions on machine start

**Goal (owner, 2026-07-30):** when the machine reboots, WSL starts, runs
`apt update && upgrade`, and then opens a Claude Code **Remote Control** session
per registered repo — each resuming its last conversation or starting fresh — so
you can pick any of them up from [claude.ai/code](https://claude.ai/code).

This is deliberately split into a part the kit automates and a part only you can
do, because **two links in the chain are outside Linux's reach.**

## The chain (and where it can break)

```
Windows login
   │  (WSL does NOT auto-start on reboot — see "Windows side")
   ▼
Task Scheduler task  ──►  wsl.exe starts the distro + holds it open
   │
   ▼
systemd (already PID 1 via /etc/wsl.conf [boot] systemd=true)
   │
   ▼
ecosystem-boot.service  (oneshot, After=network-online.target)
   │
   ▼
/usr/local/sbin/wsl-boot-orchestrator.sh   (root)
   ├─ 1. /usr/local/sbin/wsl-apt-upgrade.sh   (root, throttled once/day, time-boxed)
   └─ 2. runuser -l <owner> → ~/.claude/bin/start-remote-sessions.sh
             └─ per repo: tmux → claude --continue --remote-control …
```

## Components

| File (in kit `tools/`) | Installed to | Runs as | Purpose |
|---|---|---|---|
| `wsl-apt-upgrade.sh` | `/usr/local/sbin/` | root | Safe unattended `apt upgrade`, throttled to once/day |
| `start-remote-sessions.sh` | `~/.claude/bin/` | owner | One detached tmux Remote Control session per repo |
| `wsl-boot-orchestrator.sh` | `/usr/local/sbin/` | root | Sequences apt → sessions; the unit's ExecStart |
| `ecosystem-boot.service` | `/etc/systemd/system/` | root | systemd oneshot that fires on WSL start |
| `install-boot-automation.sh` | — (run with sudo) | root | Installs the above (owner-run) |

The user launcher is deployed by `bootstrap-machine.sh` (no sudo); the root
pieces are installed by `sudo bash tools/install-boot-automation.sh`.

## Install

```bash
# 1. user side (no sudo) — deploys start-remote-sessions.sh to ~/.claude/bin
bash tools/bootstrap-machine.sh

# 2. root side (sudo) — /usr/local/sbin scripts + systemd unit
sudo bash tools/install-boot-automation.sh

# 3. test the Linux chain WITHOUT rebooting
sudo systemctl start ecosystem-boot.service
journalctl -u ecosystem-boot -b
~/.claude/bin/start-remote-sessions.sh --list
```

Then do the **Windows side** below — without it, nothing fires on reboot.

## Windows side (required, manual)

`wsl.exe` does not start on Windows boot; the distro starts lazily on first
access and the WSL2 VM idle-shuts-down (~60s) once nothing is running inside it.
So you need a Task Scheduler task both to *start* WSL at logon and to *keep it
alive*:

1. Distro name: `wsl -l -v` in PowerShell.
2. **Task Scheduler → Create Task**
   - **General:** *Run only when user is logged on* (not "whether logged on or
     not" — WSL2 needs your user context and profile-resident VHD; the SYSTEM
     account gives "There are no running distributions").
   - **Trigger:** *At log on* → your user.
   - **Action:** Program `C:\Windows\System32\wsl.exe`,
     Arguments `-d <DistroName> -u root -e /bin/sh -lc "sleep infinity"`.
   - **Settings:** uncheck *Stop the task if it runs longer than…* so the
     keepalive runs indefinitely.

Starting the distro triggers systemd → `ecosystem-boot.service`. The held-open
`sleep infinity` is the keepalive that stops the VM idle-shutting-down.

## Honest risk flags

- **Unattended `apt upgrade` makes system changes with no one watching.** It's
  restricted to `upgrade` (never removes packages), keeps your existing config
  files, waits for the apt lock, and is throttled to once/day. The WSL kernel is
  Microsoft-supplied (not apt-managed), so there is no kernel swap or reboot.
  Still: it *is* automatic package churn. To pause it: `sudo systemctl disable
  ecosystem-boot.service`, or freeze specific packages with `apt-mark hold`.
- **N Remote Control sessions auto-start.** Idle sessions cost little (quota is
  spent only when you send a turn), but each is a live login to
  api.anthropic.com. Trim with `~/.claude/remote-sessions.exclude` (one repo
  path per line to skip) or cap with `REMOTE_SESSIONS_MAX=<n>`.
- **Auth is the fragile bit.** Remote Control requires the **full-scope**
  `claude auth login` (cached in `~/.claude/.credentials.json`). It **rejects**
  the reduced-scope `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` (that
  token is only for the headless `claude -p` cron tools). The launcher unsets it
  defensively. If sessions fail with a scope/login error, run `claude` once
  interactively and re-login.
- **Trust:** each repo folder must have been trusted once interactively
  (`cd <repo> && claude`, accept the prompt). Agents cannot set folder trust.
- **A dead session doesn't self-revive at boot only.** `start-remote-sessions.sh`
  is idempotent — re-running revives sessions that died (e.g. a >10-min network
  outage exits Remote Control). To auto-revive, add an OPT-IN cron (not installed
  by default):
  `*/30 * * * * /home/<owner>/.claude/bin/start-remote-sessions.sh >> ~/.claude/remote-sessions.log 2>&1`

## Operate

```bash
start-remote-sessions.sh            # launch/ensure sessions (idempotent)
start-remote-sessions.sh --check    # dry-run: what would launch
start-remote-sessions.sh --list     # running claude-* tmux sessions
tmux attach -t claude-<repo>        # drive one locally (Ctrl-b d to detach)
sudo wsl-apt-upgrade.sh --dry-run   # preview the apt step
journalctl -u ecosystem-boot -b     # boot-chain log for this boot
sudo systemctl disable ecosystem-boot.service   # turn the whole thing off
```
