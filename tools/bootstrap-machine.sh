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
for t in safe-push weekly-hygiene pr-comment-poller; do
  cp "$KIT/tools/$t" "$BIN/$t" && chmod +x "$BIN/$t"
done
cp "$KIT/tools/guard_protected_branch.py" "$HOOKS_MACHINE/guard_protected_branch.py"
chmod +x "$HOOKS_MACHINE/guard_protected_branch.py"
ok "safe-push, weekly-hygiene, pr-comment-poller, guard_protected_branch"

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
CRON_HYGIENE="7 6 * * 1 $BIN/weekly-hygiene >> $HOME/.claude/hygiene-cron.log 2>&1"
CRON_POLLER="*/15 7-23 * * * $BIN/pr-comment-poller >> $HOME/.claude/pr-poller-cron.log 2>&1"
existing="$(crontab -l 2>/dev/null || true)"
add=""
echo "$existing" | grep -qF "$BIN/weekly-hygiene"     || add="$add$CRON_HYGIENE\n"
echo "$existing" | grep -qF "$BIN/pr-comment-poller"  || add="$add$CRON_POLLER\n"
if [ -n "$add" ]; then
  printf '%s\n%b' "$existing" "$add" | sed '/^$/d' | crontab -
  ok "cron installed (weekly hygiene Mon 06:07; PR poller every 15 min, 07-23h)"
else
  ok "cron entries already present"
fi

# ── MANUAL (confirm → verify → retry) ────────────────────────────────

step() {  # $1 title, $2 instructions, $3 verify-fn
  local title="$1" instructions="$2" verify="$3" first=1
  while true; do
    if "$verify"; then ok "$title"; return 0; fi
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

step "Register project checkouts" \
"   Clone your project repos, run each repo's kit install
   (bash $KIT/installer/install.sh <path> <profile>), then register each:
     $BIN/pr-comment-poller register <path>" \
verify_registry

# ── SUMMARY ──────────────────────────────────────────────────────────

echo
echo "== bootstrap summary =="
for f in "$BIN/safe-push" "$BIN/weekly-hygiene" "$BIN/pr-comment-poller" \
         "$HOOKS_MACHINE/guard_protected_branch.py"; do
  [ -x "$f" ] && ok "$(basename "$f")" || warn "missing: $f"
done
crontab -l 2>/dev/null | grep -qF "$BIN/weekly-hygiene" && ok "cron: weekly hygiene" || warn "cron: hygiene missing"
crontab -l 2>/dev/null | grep -qF "$BIN/pr-comment-poller" && ok "cron: PR poller" || warn "cron: poller missing"
echo
echo "Next: $BIN/pr-comment-poller init   (baseline open PRs so history doesn't trigger)"
echo "Then leave a comment on any open PR — that's the whole workflow now."
