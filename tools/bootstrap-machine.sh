#!/usr/bin/env bash
# bootstrap-machine.sh — configure a fresh machine for the ecosystem.
#
# Everything a machine needs beyond the repos themselves, rebuilt from this
# kit checkout in one run:
#   AUTOMATED — machine tools deployed to ~/.claude/bin + hooks-machine,
#   machine guardrail permissions + hook wiring merged into
#   ~/.claude/settings.local.json, cron entries installed, dirs created.
#   MANUAL (interactive) — steps only the owner can do (credentials, logins,
#   repo registration): each one prompts, waits for your confirmation, then
#   VERIFIES; on failure it explains what failed and asks for the SAME step
#   again until verification passes ('s' skips at your own risk).
#
# Idempotent: safe to re-run any time (also refreshes deployed tools after a
# kit update). Run interactively: bash tools/bootstrap-machine.sh
set -uo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="ashishkularia"
BIN="$HOME/.claude/bin"
HOOKS_MACHINE="$HOME/.claude/hooks-machine"
REGISTRY="$HOME/.claude/repo-registry"
SETTINGS="$HOME/.claude/settings.local.json"

ok()   { echo "  [ok]   $*"; }
act()  { echo "  [do]   $*"; }
warn() { echo "  [warn] $*"; }

echo "== ecosystem-kit machine bootstrap (kit: $KIT) =="

# ── AUTOMATED ────────────────────────────────────────────────────────

act "directories"
mkdir -p "$BIN" "$HOOKS_MACHINE" "$HOME/.secrets"
chmod 700 "$HOME/.secrets"

act "machine tools -> $BIN"
for t in safe-push pr-thread weekly-hygiene pr-comment-poller kit-propagate pr-rebase prune-stale-branches mcp-audit deploy-artifacts unwedge-hooks.py start-remote-sessions.sh; do
  if [ -f "$KIT/tools/$t" ]; then cp "$KIT/tools/$t" "$BIN/$t" && chmod +x "$BIN/$t"
  else warn "tool not in this kit checkout, skipped: $t"; fi
done
cp "$KIT/tools/guard_protected_branch.py" "$HOOKS_MACHINE/guard_protected_branch.py"
chmod +x "$HOOKS_MACHINE/guard_protected_branch.py"
ok "safe-push, pr-thread, weekly-hygiene, pr-comment-poller, kit-propagate, pr-rebase, prune-stale-branches, mcp-audit, deploy-artifacts, unwedge-hooks, start-remote-sessions, guard_protected_branch"

act "machine guardrails -> settings.local.json"
python3 - "$SETTINGS" "$BIN" "$HOOKS_MACHINE" <<'PYEOF'
import json, os, sys
path, bindir, hm = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(path):
    data = json.load(open(path))
perms = data.setdefault("permissions", {})
def union(key, items):
    cur = perms.setdefault(key, [])
    for it in items:
        if it not in cur:
            cur.append(it)
union("allow", [f"Bash({bindir}/safe-push:*)"])
# GitHub MCP tools the headless automation (poller, pr-rebase) needs — read to
# see PRs/threads, write to reply/comment and open/update PRs. BOTH server-name
# variants. merge_pull_request is deliberately EXCLUDED (owner-only, denied
# below). This is the kit-versioned home for the grant — no manual one-liner.
_gh = ("get_me", "get_file_contents", "get_commit", "list_branches",
       "list_commits", "list_issues", "search_repositories", "search_code",
       "pull_request_read", "add_reply_to_pull_request_comment",
       "add_issue_comment", "create_pull_request", "update_pull_request")
union("allow", [f"mcp__{s}__{n}" for s in ("github", "plugin_github_github")
                for n in _gh])
union("deny", ["Bash(git push:*)", "Bash(git config:*)", "Bash(git clean:*)",
               "mcp__github__merge_pull_request",
               "mcp__plugin_github_github__merge_pull_request"])
hooks = data.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])
cmd = f"python3 {hm}/guard_protected_branch.py"
matcher = "mcp__github__|mcp__plugin_github_github__"
if not any(g.get("matcher") == matcher for g in pre):
    pre.append({"matcher": matcher,
                "hooks": [{"type": "command", "command": cmd}]})
json.dump(data, open(path, "w"), indent=2)
open(path, "a").write("\n")
print("  [ok]   safe-push allowed; push/merge-to-main denied; branch guard wired")
PYEOF

act "cron entries"
existing="$(crontab -l 2>/dev/null || true)"
add=""
add_cron() { echo "$existing" | grep -qF "$1" || add="$add$2\n"; }
add_cron "$BIN/weekly-hygiene"    "7 6 * * 1 $BIN/weekly-hygiene >> $HOME/.claude/hygiene-cron.log 2>&1"
add_cron "$BIN/pr-comment-poller" "*/15 7-23 * * * $BIN/pr-comment-poller >> $HOME/.claude/pr-poller-cron.log 2>&1"
add_cron "$BIN/kit-propagate"     "37 6 * * * $BIN/kit-propagate >> $HOME/.claude/kit-propagate-cron.log 2>&1"
add_cron "$BIN/pr-rebase"         "17 8,12,16,20 * * * $BIN/pr-rebase >> $HOME/.claude/pr-rebase-cron.log 2>&1"
add_cron "$BIN/prune-stale-branches" "52 6 * * * $BIN/prune-stale-branches >> $HOME/.claude/prune-branches-cron.log 2>&1"
if [ -n "$add" ]; then
  printf '%s\n%b' "$existing" "$add" | sed '/^$/d' | crontab -
  ok "cron installed/updated (hygiene, PR poller, kit-propagate, pr-rebase, prune-stale-branches)"
else
  ok "cron entries already present"
fi

# ── MANUAL (confirm → verify → retry) ────────────────────────────────

step() {  # $1 title, $2 instructions, $3 verify-fn
  local title="$1" instructions="$2" verify="$3" first=1
  while true; do
    if "$verify"; then ok "$title"; return 0; fi
    # Non-interactive run (piped/headless, no readable /dev/tty): a failed
    # verify can't be prompted, so skip with a warning instead of hot-looping.
    if ! { : < /dev/tty; } 2>/dev/null; then
      warn "$title — needs manual setup and no terminal to prompt; re-run bootstrap interactively"
      return 1
    fi
    echo
    if [ "$first" -eq 1 ]; then
      echo "── MANUAL STEP: $title"
    else
      echo "── STILL FAILING: $title — please redo this step"
    fi
    first=0
    printf '%s\n' "$instructions"
    read -rp "   Press Enter when done ('s' skips at your own risk): " ans </dev/tty
    if [ "$ans" = "s" ]; then warn "$title SKIPPED — re-run bootstrap later"; return 1; fi
  done
}

verify_ssh() {
  ssh -T git@github.com -o BatchMode=yes -o ConnectTimeout=10 2>&1 \
    | grep -q "successfully authenticated"
}

verify_pat() {
  python3 - "$OWNER" <<'PYEOF'
import json, os, stat, sys, urllib.request
owner = sys.argv[1]
p = os.path.expanduser("~/.secrets/github-pat")
if not os.path.isfile(p):
    print("       (no file at ~/.secrets/github-pat)"); sys.exit(1)
mode = stat.S_IMODE(os.stat(p).st_mode)
if mode & 0o077:
    print(f"       (permissions are {oct(mode)} — run: chmod 600 ~/.secrets/github-pat)"); sys.exit(1)
tok = open(p).read().strip()
req = urllib.request.Request("https://api.github.com/user",
    headers={"Authorization": f"Bearer {tok}", "User-Agent": "bootstrap"})
try:
    login = json.loads(urllib.request.urlopen(req, timeout=15).read()).get("login")
except Exception as e:
    print(f"       (API rejected the token: {e})"); sys.exit(1)
if login != owner:
    print(f"       (token belongs to '{login}', expected '{owner}')"); sys.exit(1)
sys.exit(0)
PYEOF
}

verify_gh() {
  local gh_bin
  gh_bin="$(command -v gh 2>/dev/null || echo "$HOME/.local/bin/gh")"
  [ -x "$gh_bin" ] || return 1
  # Presence is not usefulness. An installed-but-unauthenticated gh passes a
  # binary check and then fails the moment a session actually needs a PR —
  # exactly the situation this step exists to prevent. Check auth, and check it
  # WITHOUT GH_TOKEN so we are testing the persisted credential rather than
  # whatever happens to be in this shell.
  env -u GH_TOKEN -u GITHUB_TOKEN "$gh_bin" auth status >/dev/null 2>&1
}

verify_claude() {
  command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ] || return 1
  [ -s "$HOME/.claude/.credentials.json" ]
}

verify_registry() {
  [ -s "$REGISTRY" ] || return 1
  while IFS= read -r line; do
    line="${line%%#*}"; line="$(echo "$line" | tr -d '[:space:]')"
    [ -z "$line" ] && continue
    git -C "$line" remote get-url origin 2>/dev/null | grep -q "github.com" || {
      echo "       (registered path '$line' is not a github checkout)"; return 1; }
  done < "$REGISTRY"
}

verify_boot_automation() {
  # The root install (systemd unit) needs sudo; the Windows Task Scheduler
  # trigger is off-box. Both are owner-only, so this only checks the Linux side.
  systemctl is-enabled ecosystem-boot.service >/dev/null 2>&1 || {
    echo "       (ecosystem-boot.service not installed/enabled)"; return 1; }
}

echo
echo "== manual steps =="

step "GitHub SSH key" \
"   Generate/copy an SSH key for this machine and add it to GitHub:
     ssh-keygen -t ed25519   (if you don't have one)
     then add ~/.ssh/id_ed25519.pub at https://github.com/settings/keys" \
verify_ssh

step "GitHub PAT for automation" \
"   Create a fine-grained PAT (repo scope) at https://github.com/settings/tokens
   and store it for the poller/bootstrap tools ONLY:
     printf '%s' '<TOKEN>' > ~/.secrets/github-pat && chmod 600 ~/.secrets/github-pat" \
verify_pat

step "Claude Code login" \
"   Install Claude Code and log in once interactively:
     https://claude.ai/code — then run: claude   (complete the login flow)" \
verify_claude

step "GitHub CLI (gh)" \
"   gh is the fallback path for PR and issue work when the GitHub MCP server is
   not connected — without it, a session that needs to open a PR has neither.
   No sudo required; ~/.local/bin is already on PATH:

     V=2.98.0   # latest: https://github.com/cli/cli/releases/latest
     cd \"\$(mktemp -d)\"
     curl -sSL -o gh.tgz \\
       \"https://github.com/cli/cli/releases/download/v\$V/gh_\${V}_linux_amd64.tar.gz\"
     curl -sSL -o sums.txt \\
       \"https://github.com/cli/cli/releases/download/v\$V/gh_\${V}_checksums.txt\"
     grep \"gh_\${V}_linux_amd64.tar.gz\" sums.txt | sed \"s|gh_\${V}_linux_amd64.tar.gz|gh.tgz|\" \\
       | sha256sum -c -            # MUST pass before installing
     tar xzf gh.tgz && install -m755 gh_\${V}_linux_amd64/bin/gh \"\$HOME/.local/bin/gh\"

   Verify the checksum before installing, and run ONE download at a time — a
   second curl resuming into the same file produces an oversized, corrupt
   archive that still looks like a normal failure (2026-08-27).

   Then authenticate ONCE, from the PAT the machine layer already owns — no
   second credential, no interactive OAuth, nothing to type:

     gh auth login --with-token < ~/.secrets/github-pat
     gh auth status          # expect: Logged in to github.com account <you>

   --with-token stores the token you hand it; it does NOT mint a new one (the
   interactive flow does). The cost is that the same token then also lives in
   ~/.config/gh/hosts.yml (gh writes it 0600), so rotating means updating both
   files — verify_gh checks the stored copy still works, so drift shows up at
   bootstrap rather than mid-task.

   Every kit machine tool (kit-propagate, pr-thread, pr-comment-poller,
   pr-rebase, prune-stale-branches) reads ~/.secrets/github-pat directly and
   needs no environment variable. This step is only so bare \`gh\` works too." \
verify_gh

step "Register project checkouts" \
"   Clone your project repos, run each repo's kit install
   (bash $KIT/installer/install.sh <path> <profile>), then register each:
     $BIN/pr-comment-poller register <path>" \
verify_registry

step "Boot automation (apt upgrade + Remote Control sessions)" \
"   Install the root pieces (systemd unit + /usr/local/sbin scripts):
     sudo bash $KIT/tools/install-boot-automation.sh
   Then do the WINDOWS side it prints (Task Scheduler at-logon task to start
   WSL + keep it alive) — WSL does not boot on Windows reboot without it.
   Full chain + risk notes: $KIT/docs/BOOT-AUTOMATION.md" \
verify_boot_automation

# ── SUMMARY ──────────────────────────────────────────────────────────

echo
echo "== bootstrap summary =="
for f in "$BIN/safe-push" "$BIN/weekly-hygiene" "$BIN/pr-comment-poller" \
         "$BIN/mcp-audit" "$BIN/deploy-artifacts" "$HOOKS_MACHINE/guard_protected_branch.py"; do
  [ -x "$f" ] && ok "$(basename "$f")" || warn "missing: $f"
done
# The dispatcher being present is not the same as this machine having somewhere
# to publish TO. Every profile now points `artifacts.deploy_command` at it, so
# an unconfigured destination means every repo mirrors artifacts that reach no
# host — which is precisely the state that went unnoticed until 2026-09-01.
if [ -e "$HOME/.claude/artifacts-deploy" ]; then
  ok "artifacts deploy target: $(readlink -f "$HOME/.claude/artifacts-deploy")"
else
  warn "no artifacts deploy target — published artifacts will be mirrored but NOT posted.
         Point it at this machine's deploy script:
           ln -s ~/homeassistant/ops/lxc/deploy-artifacts.sh $HOME/.claude/artifacts-deploy"
fi
crontab -l 2>/dev/null | grep -qF "$BIN/weekly-hygiene" && ok "cron: weekly hygiene" || warn "cron: hygiene missing"
crontab -l 2>/dev/null | grep -qF "$BIN/pr-comment-poller" && ok "cron: PR poller" || warn "cron: poller missing"
echo
echo "Next: $BIN/pr-comment-poller init   (baseline open PRs so history doesn't trigger)"
echo "Then leave a comment on any open PR — that's the whole workflow now."
