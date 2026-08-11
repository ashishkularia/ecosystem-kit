#!/usr/bin/env bash
# start-remote-sessions.sh — one detached Remote Control Claude session per repo.
#
# Owner ask (2026-07-30): on machine boot, "initiate remote control sessions for
# all repos, either resume the last session or start a new one." This is the
# user-side half of the boot chain (see docs/BOOT-AUTOMATION.md); the root
# orchestrator calls it via `runuser -l <owner>` after the apt upgrade.
#
# For each registered repo it ensures ONE detached tmux session named
# `claude-<repo>` running (owner ask: "resume the last session or start a new one"):
#     claude --continue --remote-control …   ||   claude --remote-control …
#   --continue  resumes that directory's most recent INTERACTIVE conversation.
#               In interactive mode it EXITS 1 with "No conversation found to
#               continue" when the dir has none (unlike `-p`, which starts fresh
#               silently) — verified on claude 2.1.220. So on that failure we
#               fall back to a fresh session; both outcomes satisfy the ask.
#   --remote-control  makes it drivable from claude.ai/code (a real interactive
#               session held open in tmux — NOT `claude -p`).
#
# CRITICAL — auth: Remote Control requires the FULL-SCOPE interactive login
# (~/.claude/.credentials.json from `claude auth login`). It REJECTS the
# reduced-scope CLAUDE_CODE_OAUTH_TOKEN that `claude setup-token` mints (that
# token is for the headless `claude -p` cron tools only). So this launcher
# defensively UNSETS it — otherwise Remote Control fails with a scope error.
#
# Idempotent: a repo whose tmux session already exists is left running. Re-run
# any time to revive sessions that died (e.g. after a network outage).
#
# Modes:
#   start-remote-sessions.sh            launch/ensure sessions
#   start-remote-sessions.sh --check    dry-run: report what WOULD launch
#   start-remote-sessions.sh --list     list currently-running claude-* sessions
set -uo pipefail

# Remote Control needs the full-scope login, not the reduced-scope token — see above.
unset CLAUDE_CODE_OAUTH_TOKEN

CLAUDE="${CLAUDE_BIN:-$(command -v claude || echo "$HOME/.local/bin/claude")}"
REGISTRY="$HOME/.claude/repo-registry"
EXCLUDE="$HOME/.claude/remote-sessions.exclude"   # optional: one repo path per line to skip
LOG="$HOME/.claude/remote-sessions.log"
MAX="${REMOTE_SESSIONS_MAX:-0}"                    # 0 = no cap
MODE="${1:-run}"

log() { printf '%s %s\n' "$(date -Is)" "$*" >>"$LOG"; }

if ! command -v tmux >/dev/null 2>&1; then
  echo "start-remote-sessions: tmux not installed (apt-get install -y tmux)" >&2
  exit 1
fi
if [ ! -x "$CLAUDE" ] && ! command -v claude >/dev/null 2>&1; then
  echo "start-remote-sessions: claude CLI not found" >&2
  exit 1
fi

# Read registry (one checkout path per line; '#' comments).
repos=()
if [ -f "$REGISTRY" ]; then
  while IFS= read -r line; do
    line="${line%%#*}"; line="$(echo "$line" | tr -d '[:space:]')"
    [ -n "$line" ] && repos+=("$line")
  done < "$REGISTRY"
fi
if [ ${#repos[@]} -eq 0 ]; then
  echo "start-remote-sessions: registry $REGISTRY is empty" >&2
  exit 1
fi

is_excluded() {
  [ -f "$EXCLUDE" ] || return 1
  grep -qxF "$1" "$EXCLUDE"
}

session_name() {  # tmux session names can't contain '.' or ':' — sanitize
  local b; b="$(basename "$1")"       # command subst strips the trailing newline
  printf 'claude-%s' "${b//[^A-Za-z0-9_-]/-}"
}

if [ "$MODE" = "--list" ]; then
  tmux list-sessions -F '#{session_name}  (#{session_windows} win, created #{t:session_created})' 2>/dev/null \
    | grep '^claude-' || echo "(no claude-* sessions running)"
  exit 0
fi

launched=0
for repo in "${repos[@]}"; do
  name="$(session_name "$repo")"
  if [ ! -d "$repo" ]; then
    log "skip $name: no such directory $repo"; echo "[skip] $name: missing dir"; continue
  fi
  if is_excluded "$repo"; then
    echo "[skip] $name: excluded"; continue
  fi
  if tmux has-session -t "$name" 2>/dev/null; then
    echo "[live] $name: already running"; continue
  fi
  if [ "$MAX" -gt 0 ] && [ "$launched" -ge "$MAX" ]; then
    echo "[cap]  $name: REMOTE_SESSIONS_MAX=$MAX reached — not launched"
    log "cap reached ($MAX): $name not launched"; continue
  fi
  prefix="$(basename "$repo")"
  if [ "$MODE" = "--check" ]; then
    echo "[would] $name: claude --continue --remote-control (|| fresh) prefix=$prefix in $repo"
    launched=$((launched + 1)); continue
  fi
  # Launch detached. tmux provides the TTY Remote Control's interactive session
  # needs; the session persists until claude exits or the machine reboots.
  # Resume-or-fresh: --continue exits 1 fast when there's no conversation, so
  # the `||` starts a fresh session in that case.
  rc="$CLAUDE --remote-control --remote-control-session-name-prefix '$prefix'"
  tmux new-session -d -s "$name" -c "$repo" \
    "$CLAUDE --continue --remote-control --remote-control-session-name-prefix '$prefix' || $rc"
  echo "[start] $name: launched in $repo"
  log "launched $name in $repo (prefix=$prefix)"
  launched=$((launched + 1))
done

if [ "$MODE" = "--check" ]; then
  echo "--- $launched session(s) would be launched"
else
  echo "--- $launched session(s) launched this run"
fi
