# 2026-10-20 — chore/boot-automation-ubuntu

## What the owner asked

"If you remember, we set up something that would auto start the claude session
when the system gets rebooted. Now the OS has changed from Windows WSL to Ubuntu.
So change it accordingly."

## I did not remember — I looked

Nothing about this was in my context, so I searched instead of pretending:
kit docs and ledgers, crontab, systemd (system and user), shell profiles,
`~/.claude/bin`. It is the 2026-07-30 boot automation: `docs/BOOT-AUTOMATION.md`
plus `tools/{wsl-apt-upgrade,wsl-boot-orchestrator}.sh`, `ecosystem-boot.service`,
`install-boot-automation.sh` and the user launcher `start-remote-sessions.sh`.

## What the machine actually is now

- Native Ubuntu 26.04.1 on bare metal: `systemd-detect-virt` = `none`, no
  `/run/WSL`, no `microsoft` in `/proc/version`, no `/etc/wsl.conf`.
- **None of the old chain is installed.** No unit, nothing in `/usr/local/sbin`.
  Only the user launcher survived (it lives in `~/.claude/bin`, migrated with the
  home directory, and is byte-identical to `tools/`).
- **`tmux` is not installed** — the launcher exits 1 without it.
- `sudo` asks for a password, so I cannot do the root install.
- `unattended-upgrades` is installed and enabled.
- `claude` 2.1.303 still has `--continue`, `--remote-control` and
  `--remote-control-session-name-prefix`; credentials file present;
  `NetworkManager-wait-online` enabled, so `network-online.target` means something.

## What was WSL-specific and what was not

WSL-specific: the whole Windows half (Task Scheduler at-logon task, the
`wsl.exe … sleep infinity` keepalive), the `/etc/wsl.conf` check, and the apt
script's premise that the kernel is Microsoft-supplied. Not WSL-specific: the
systemd oneshot, `runuser -l`, the tmux launcher — so those keep their shape.
Native Ubuntu *removes* a manual step: systemd is PID 1 from power-on.

## The decision I weighed most: the apt step

On native Ubuntu it is no longer harmless boilerplate. `unattended-upgrades` is
already doing security updates; the boot step is a second, broader upgrader that
can pull in a new kernel (never rebooting). It was an explicit owner requirement,
so I kept it, made the doc and the script say what it now does, and left the
opt-out as "delete the deployed script" (the orchestrator already skips a missing
one). The owner may well prefer to drop it; that is a one-command change.

## Things I found that are not code

- **`/home/ubuntu/DevContainer/grade5` is untrusted.** Trust is keyed by path:
  `/home/ubuntu/grade5` (the symlink) is recorded as trusted, the real path the
  registry — and so the launcher — uses is not. That session would sit at the
  trust prompt inside tmux where nobody can see it. One manual step
  (`cd /home/ubuntu/DevContainer/grade5 && claude`, accept). I read only the
  `hasTrustDialogAccepted` booleans from `~/.claude.json`, nothing else in it.
- The registry has 7 entries including the kit itself and the `DevContainer`
  parent, so 7 tmux sessions. Trim with `~/.claude/remote-sessions.exclude`.

## Verification — and its limit

Done without root: exec bits survived the rewrite; `bash -n` on all five scripts;
`systemd-analyze verify` on the unit (clean once ExecStart points at a real file);
apt `--dry-run`; the launcher's `--check` against the real registry with a `tmux`
shim (7 repos resolved, session names sane). **Not done, cannot be done by me:**
the sudo install, `systemctl start`, and — the only real proof — a reboot. I did
not run the orchestrator even with stubs: its logic is unchanged from the version
verified live on WSL (I changed comments and one path), and a stubbed copy would
test the stub.

## Not done

- A trust preflight in the launcher (`--check` could warn about untrusted paths).
  New feature, not an OS change; reported instead.
- Installing anything. The owner runs `sudo bash tools/install-boot-automation.sh`.
