#!/usr/bin/env bash
# install-boot-automation.sh — install the WSL boot chain (RUN WITH sudo).
#
#   sudo bash tools/install-boot-automation.sh
#
# Does the root-only steps that bootstrap-machine.sh can't: deploy the two root
# scripts to /usr/local/sbin, install + enable the systemd oneshot unit, and
# verify prerequisites. The USER launcher (start-remote-sessions.sh) is deployed
# separately by bootstrap-machine.sh into ~/.claude/bin (no sudo).
#
# After this runs, the LINUX side is done. The WINDOWS side (Task Scheduler to
# start WSL at logon + keep it alive) is printed at the end and MUST be done by
# hand — WSL does not boot on Windows reboot on its own. See docs/BOOT-AUTOMATION.md.
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
if ! grep -qs 'systemd=true' /etc/wsl.conf; then
  warn "/etc/wsl.conf lacks 'systemd=true' under [boot] — the unit needs systemd."
  warn "Add it, then 'wsl.exe --shutdown' from Windows (wait ~8s) before relaunch."
else
  ok "/etc/wsl.conf has systemd=true"
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
for s in wsl-apt-upgrade.sh wsl-boot-orchestrator.sh; do
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

# 5. Summary + Windows-side handoff -----------------------------------------
cat <<EOF

== Linux side installed ==
  Test the whole chain now, without rebooting:
     sudo systemctl start ecosystem-boot.service
     journalctl -u ecosystem-boot -b          # root: apt + orchestrator log
     sudo -u $OWNER $USER_LAUNCHER --list     # the running Remote Control sessions
  Then open https://claude.ai/code — each repo appears as an online session.

== WINDOWS SIDE — REQUIRED, do this by hand ==
  WSL does NOT start on Windows reboot; it starts lazily on first access and
  idle-shuts-down when nothing is running. To make boot automation actually
  fire on every Windows login, create a Task Scheduler task:

    1. Find your distro name (PowerShell):   wsl -l -v
    2. Task Scheduler > Create Task:
         General : "Run only when user is logged on"  (NOT "whether logged on or not")
         Trigger : At log on -> your user
         Action  : Program : C:\\Windows\\System32\\wsl.exe
                   Args    : -d <DistroName> -u root -e /bin/sh -lc "sleep infinity"
    3. Set the task to allow running indefinitely (Settings tab: uncheck
       "Stop the task if it runs longer than").

  Starting the distro fires this unit (via systemd); the held-open 'sleep
  infinity' keeps the WSL2 VM from idle-shutting-down a minute later. See
  docs/BOOT-AUTOMATION.md for the why and for troubleshooting.
EOF
