#!/usr/bin/env bash
# wsl-boot-orchestrator.sh — the single ExecStart of the ecosystem-boot unit.
#
# Owner ask (2026-07-30): on boot, "start the wsl then run update and upgrade
# once that is done then initiate remote control sessions for all repos."
# systemd runs this as ROOT when the WSL instance starts (see the unit +
# docs/BOOT-AUTOMATION.md). Order:
#   1. apt update && upgrade  (root, throttled to once/day, time-boxed)
#   2. THEN start one Remote Control session per repo, AS the owner user.
#
# The apt step is time-boxed and non-fatal: a stuck dpkg lock must never block
# the sessions from starting. "once that is done" is honored (sessions start
# after apt returns/times out), but a hung apt can't strand the sessions.
set -uo pipefail

OWNER="${BOOT_OWNER:-ubuntu}"
APT="/usr/local/sbin/wsl-apt-upgrade.sh"
# The user launcher runs AS $OWNER (their own script in their own bin) — root
# never executes a user-writable script directly (no privilege escalation).
USER_LAUNCHER="/home/$OWNER/.claude/bin/start-remote-sessions.sh"
APT_TIMEOUT="${BOOT_APT_TIMEOUT:-1800}"

echo "=== $(date -Is) boot-orchestrator start (owner=$OWNER) ==="

# 1. apt upgrade — time-boxed, never fatal to the session launch.
if [ -x "$APT" ]; then
  if timeout "$APT_TIMEOUT" "$APT"; then
    echo "apt upgrade: ok"
  else
    echo "apt upgrade: failed or timed out (rc=$?) — continuing to sessions" >&2
  fi
else
  echo "apt upgrade: $APT not installed — skipping" >&2
fi

# 2. Remote Control sessions — dropped to the owner with a login shell so
#    ~/.profile (PATH, ~/.local/bin) and the full-scope Claude login load.
if [ -x "$USER_LAUNCHER" ]; then
  echo "launching remote sessions as $OWNER..."
  runuser -l "$OWNER" -c "$USER_LAUNCHER" || \
    echo "remote-session launcher exited non-zero (rc=$?)" >&2
else
  echo "remote sessions: $USER_LAUNCHER not found for $OWNER — skipping" >&2
fi

echo "=== $(date -Is) boot-orchestrator done ==="
