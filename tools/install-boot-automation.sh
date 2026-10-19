#!/usr/bin/env bash
# install-boot-automation.sh — install the boot chain (RUN WITH sudo).
#
#   sudo bash tools/install-boot-automation.sh
#
# Does the root-only steps that bootstrap-machine.sh can't: install tmux, deploy
# the two root scripts to /usr/local/sbin, install + enable the systemd oneshot
# unit, and verify it. The USER launcher (start-remote-sessions.sh) is deployed
# separately by bootstrap-machine.sh into ~/.claude/bin (no sudo).
#
# Native Ubuntu: after this runs there is nothing else to set up — systemd starts
# the unit at every boot, no login needed. (Under WSL nothing starts the distro at
# Windows boot; see the WSL note in docs/BOOT-AUTOMATION.md.)
#
# Idempotent: safe to re-run after a kit update to refresh the deployed scripts.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="${SUDO_USER:-ubuntu}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0" >&2
  exit 1
fi

ok()   { echo "  [ok]   $*"; }
act()  { echo "  [do]   $*"; }
warn() { echo "  [warn] $*"; }

echo "== install boot automation (kit: $KIT, owner: $OWNER) =="

# 1. Prereqs -----------------------------------------------------------------
act "checking prerequisites"
if [ "$(ps -p 1 -o comm= 2>/dev/null)" = "systemd" ]; then
  ok "systemd is PID 1"
else
  warn "PID 1 is not systemd — ecosystem-boot.service will never run on this host."
fi
if grep -qis microsoft /proc/version; then
  warn "this looks like WSL: nothing starts the distro at Windows boot, so the unit only"
  warn "fires when you open it by hand. See the WSL note in docs/BOOT-AUTOMATION.md."
fi
if ! command -v tmux >/dev/null 2>&1; then
  act "installing tmux (required by the session launcher)"
  DEBIAN_FRONTEND=noninteractive apt-get install -y tmux >/dev/null 2>&1 \
    && ok "tmux installed" || warn "tmux install failed — install it manually"
else
  ok "tmux present"
fi

# 2. Root scripts -> /usr/local/sbin ----------------------------------------
act "deploying root scripts to /usr/local/sbin"
for s in ecosystem-apt-upgrade.sh ecosystem-boot-orchestrator.sh; do
  install -o root -g root -m 0755 "$KIT/tools/$s" "/usr/local/sbin/$s"
  ok "/usr/local/sbin/$s"
done

# 3. User launcher must be present (deployed by bootstrap-machine.sh) --------
USER_LAUNCHER="/home/$OWNER/.claude/bin/start-remote-sessions.sh"
if [ -x "$USER_LAUNCHER" ]; then
  ok "user launcher present: $USER_LAUNCHER"
else
  warn "user launcher missing: $USER_LAUNCHER"
  warn "run (as $OWNER, no sudo):  bash $KIT/tools/bootstrap-machine.sh"
fi

# 4. systemd unit ------------------------------------------------------------
act "installing systemd unit"
sed "s/^Environment=BOOT_OWNER=.*/Environment=BOOT_OWNER=$OWNER/" \
  "$KIT/tools/ecosystem-boot.service" > /etc/systemd/system/ecosystem-boot.service
systemctl daemon-reload
systemctl enable ecosystem-boot.service >/dev/null 2>&1
ok "ecosystem-boot.service installed + enabled (BOOT_OWNER=$OWNER)"
if systemd-analyze verify /etc/systemd/system/ecosystem-boot.service 2>/dev/null; then
  ok "unit passes systemd-analyze verify"
else
  warn "systemd-analyze verify reported problems — run it by hand to see them"
fi

# 5. Summary -----------------------------------------------------------------
cat <<EOF

== Installed ==
  Test the whole chain now, without rebooting:
     sudo systemctl start ecosystem-boot.service
     journalctl -u ecosystem-boot -b          # root: apt + orchestrator log
     sudo -u $OWNER $USER_LAUNCHER --list     # the running Remote Control sessions
  Then open https://claude.ai/code — each repo appears as an online session.

  The real proof is a reboot: after login, \`start-remote-sessions.sh --list\`
  should already show the sessions, and \`systemctl status ecosystem-boot\`
  should read "active (exited)".

  Before relying on it: every registered repo folder must have been trusted once
  interactively (cd <repo> && claude), or its session waits at the trust prompt
  inside tmux where nobody can see it. See docs/BOOT-AUTOMATION.md.
EOF
