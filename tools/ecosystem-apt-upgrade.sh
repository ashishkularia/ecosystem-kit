#!/usr/bin/env bash
# ecosystem-apt-upgrade.sh — unattended, safe `apt upgrade` at boot (runs as root).
#
# Part of the boot-automation chain (see docs/BOOT-AUTOMATION.md). Called by
# ecosystem-boot-orchestrator.sh, which is the ExecStart of the ecosystem-boot
# systemd oneshot unit. Can also be run standalone: `sudo ecosystem-apt-upgrade.sh`.
#
# WHY the flags:
#   DEBIAN_FRONTEND=noninteractive  suppress debconf TUI prompts
#   NEEDRESTART_MODE=a              stop needrestart interjecting (Ubuntu 22.04+)
#   --force-confdef/--force-confold keep existing config files instead of
#                                   blocking on the "replace config?" prompt
#   DPkg::Lock::Timeout=600         WAIT up to 10m for the dpkg lock instead of
#                                   dying with "Could not get lock" — on a real
#                                   boot, unattended-upgrades and the apt-daily
#                                   timers are usually running at the same time
#   Dpkg::Use-Pty=0                 clean non-tty log output
#   `upgrade` (never `dist-upgrade`) never removes packages — safe unattended.
#   `apt-get` (never `apt`)         apt has no stable CLI for scripts.
#
# NATIVE UBUNTU — read before leaving this on:
#   * unattended-upgrades is usually already enabled and handles SECURITY
#     updates. This is a second, broader upgrader (every update, not just
#     security). The two serialize on the dpkg lock; they do not corrupt each
#     other. To skip this step entirely, delete the deployed copy
#     (/usr/local/sbin/ecosystem-apt-upgrade.sh) — the orchestrator skips it
#     when absent and still starts the sessions.
#   * It can install a new KERNEL. It never reboots: the new kernel only takes
#     effect at the next reboot. `autoremove --purge` keeps the running kernel.
#
# THROTTLE: a machine can reboot several times a day, and this fires on each
# boot. A daily stamp file makes it a no-op after the first successful run of
# the calendar day.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

LOG=/var/log/ecosystem-apt-upgrade.log
STAMP=/var/lib/ecosystem-apt-upgrade.stamp
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# --dry-run is a preview only — no root, no apt lock needed.
if [ "$DRY" -eq 1 ]; then
  echo "[dry-run] would run: apt-get update + apt-get upgrade + autoremove --purge"
  echo "[dry-run] log target: $LOG   stamp: $STAMP"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "ecosystem-apt-upgrade: must run as root (needs the apt lock)" >&2
  exit 1
fi

# Throttle to once per calendar day.
if [ -f "$STAMP" ] && [ "$(date +%F)" = "$(date -r "$STAMP" +%F)" ]; then
  echo "ecosystem-apt-upgrade: already ran today ($(date +%F)); skipping"
  exit 0
fi

{
  echo "=== $(date -Is) ecosystem-apt-upgrade start ==="
  apt-get update -qq -o DPkg::Lock::Timeout=600
  apt-get -y \
    -o Dpkg::Options::=--force-confdef \
    -o Dpkg::Options::=--force-confold \
    -o Dpkg::Use-Pty=0 \
    -o DPkg::Lock::Timeout=600 \
    upgrade
  apt-get -y -o DPkg::Lock::Timeout=600 autoremove --purge
  echo "=== $(date -Is) ecosystem-apt-upgrade done ==="
} >>"$LOG" 2>&1

touch "$STAMP"
echo "ecosystem-apt-upgrade: complete (log: $LOG)"
