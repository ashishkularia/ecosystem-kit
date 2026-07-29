#!/usr/bin/env bash
# wsl-apt-upgrade.sh — unattended, safe `apt upgrade` on WSL start (runs as root).
#
# Part of the boot-automation chain (see docs/BOOT-AUTOMATION.md). Called by
# wsl-boot-orchestrator.sh, which is the ExecStart of the ecosystem-boot systemd
# oneshot unit. Can also be run standalone: `sudo wsl-apt-upgrade.sh`.
#
# WHY the flags (verified against learn.microsoft.com, 2026):
#   DEBIAN_FRONTEND=noninteractive  suppress debconf TUI prompts
#   NEEDRESTART_MODE=a              stop needrestart interjecting (Ubuntu 22.04+)
#   --force-confdef/--force-confold keep existing config files instead of
#                                   blocking on the "replace config?" prompt
#   DPkg::Lock::Timeout=600         WAIT up to 10m for the apt-daily lock instead
#                                   of dying with "Could not get lock"
#   Dpkg::Use-Pty=0                 clean non-tty log output
#   `upgrade` (never `dist-upgrade`) never removes packages — safe unattended.
#   `apt-get` (never `apt`)         apt has no stable CLI for scripts.
# WSL runs a Microsoft-supplied kernel (not apt-managed), so there is no
# kernel-swap / reboot step to worry about.
#
# THROTTLE: the WSL instance cold-starts many times a day (idle shutdown +
# lazy restart), and this fires on each start. A daily stamp file makes it a
# no-op after the first successful run of the calendar day.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

LOG=/var/log/wsl-apt-upgrade.log
STAMP=/var/lib/wsl-apt-upgrade.stamp
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# --dry-run is a preview only — no root, no apt lock needed.
if [ "$DRY" -eq 1 ]; then
  echo "[dry-run] would run: apt-get update + apt-get upgrade + autoremove --purge"
  echo "[dry-run] log target: $LOG   stamp: $STAMP"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "wsl-apt-upgrade: must run as root (needs the apt lock)" >&2
  exit 1
fi

# Throttle to once per calendar day.
if [ -f "$STAMP" ] && [ "$(date +%F)" = "$(date -r "$STAMP" +%F)" ]; then
  echo "wsl-apt-upgrade: already ran today ($(date +%F)); skipping"
  exit 0
fi

{
  echo "=== $(date -Is) wsl-apt-upgrade start ==="
  apt-get update -qq -o DPkg::Lock::Timeout=600
  apt-get -y \
    -o Dpkg::Options::=--force-confdef \
    -o Dpkg::Options::=--force-confold \
    -o Dpkg::Use-Pty=0 \
    -o DPkg::Lock::Timeout=600 \
    upgrade
  apt-get -y -o DPkg::Lock::Timeout=600 autoremove --purge
  echo "=== $(date -Is) wsl-apt-upgrade done ==="
} >>"$LOG" 2>&1

touch "$STAMP"
echo "wsl-apt-upgrade: complete (log: $LOG)"
