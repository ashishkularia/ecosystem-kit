#!/usr/bin/env bash
# health-check.sh — generic health check for a repo with the ecosystem kit installed.
#
# Usage: scripts/health-check.sh [TARGET_DIR]     (default: current directory)
#
# Checks: kit.json validity + schema conformance, engine presence + Python syntax,
# settings.json wiring == glob of hook modules, memory roster completeness,
# diary staleness, daemon status, and that no project hook wiring leaked into
# user-level settings files. Exit 0 when there are no errors (warnings allowed).
#
# NOTE: deliberately `set -uo pipefail` WITHOUT -e — individual checks are
# expected to fail without aborting the whole run.

set -uo pipefail

TARGET_DIR="${1:-$PWD}"
cd "$TARGET_DIR" 2>/dev/null || { echo "ERROR: cannot cd to $TARGET_DIR"; exit 1; }
TARGET_DIR="$(pwd -P)"

CLAUDE_DIR=".claude"
MEM_DIR=".memory"
OK=0; WARN=0; ERR=0

ok()   { OK=$((OK+1));     echo "  [OK]   $1"; }
warn() { WARN=$((WARN+1)); echo "  [WARN] $1"; }
err()  { ERR=$((ERR+1));   echo "  [ERR]  $1"; }
section() { echo ""; echo "=== $1 ==="; }

if [ ! -d "$CLAUDE_DIR" ]; then
  echo "ERROR: $TARGET_DIR/.claude not found — is the kit installed here? (installer/install.sh)"
  exit 1
fi

echo "Ecosystem Kit Health Check"
echo "=========================="
echo "Target:    $TARGET_DIR"
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# ── 1. kit.json: valid JSON + conforms to the kit.json schema ──────
section "kit.json"

if [ ! -f "$CLAUDE_DIR/kit.json" ]; then
  err "kit.json missing (.claude/kit.json is the project profile)"
else
  kit_report=$(python3 - <<'PYEOF'
import json, sys
try:
    kit = json.load(open(".claude/kit.json"))
except ValueError as e:
    print(f"invalid JSON: {e}")
    sys.exit(0)
if not isinstance(kit, dict):
    print("top level is not an object")
    sys.exit(0)
required = ["kit_version", "project", "stack", "protected_branches", "branch_types",
            "merge_is_deploy", "ceremony", "gates", "containers", "quality_commands",
            "source_patterns", "domain_map", "always_load", "principles", "diary"]
problems = []
missing = [k for k in required if k not in kit]
if missing:
    problems.append("missing keys: " + ", ".join(missing))
ceremony = kit.get("ceremony")
gates = kit.get("gates") or {}
if isinstance(ceremony, dict):
    levels = ceremony.get("levels") or {}
    default = ceremony.get("default")
    if default and levels and default not in levels:
        problems.append(f"ceremony.default '{default}' is not a ceremony level")
    referenced = {g for ids in levels.values() if isinstance(ids, list) for g in ids}
    unknown = sorted(referenced - set(gates))
    if unknown:
        problems.append("ceremony levels reference undefined gates: " + ", ".join(unknown))
for gid, g in (gates.items() if isinstance(gates, dict) else []):
    if not isinstance(g, dict) or not {"name", "desc", "commands"} <= set(g):
        problems.append(f"gate {gid} missing name/desc/commands")
print("; ".join(problems))
PYEOF
)
  if [ -z "$kit_report" ]; then
    proj=$(python3 -c "import json; k=json.load(open('.claude/kit.json')); print(k.get('project','?') + ' (' + k.get('stack','?') + ')')" 2>/dev/null)
    ok "kit.json valid and conforms to schema — project: $proj"
  else
    err "kit.json: $kit_report"
  fi
fi

if [ -f "$CLAUDE_DIR/kit-version" ]; then
  ok "kit-version stamp present ($(head -n 1 "$CLAUDE_DIR/kit-version"))"
else
  warn "kit-version stamp missing (.claude/kit-version)"
fi

# ── 2. Engine: required files present + valid Python ───────────────
section "Engine"

for core in _client.py _daemon.py _constants.py session_boot.py docs_contract.py; do
  if [ -f "$CLAUDE_DIR/hooks/$core" ]; then
    ok "hooks/$core present"
  else
    err "hooks/$core missing (core engine file)"
  fi
done

# Hooks are dispatched via the daemon (module import) or `python3 _client.py
# <hook>` — the executable bit is NOT required, only valid syntax.
compile_fail=0
hook_files=0
for hook in "$CLAUDE_DIR"/hooks/*.py; do
  [ -e "$hook" ] || continue
  hook_files=$((hook_files+1))
  if ! python3 -c "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)" "$hook" 2>/dev/null; then
    err "$(basename "$hook") has Python syntax errors"
    compile_fail=$((compile_fail+1))
  fi
done
if [ "$hook_files" -eq 0 ]; then
  err "no hook modules found in .claude/hooks/"
elif [ "$compile_fail" -eq 0 ]; then
  ok "all $hook_files hook module(s) compile"
fi

if [ -d "$CLAUDE_DIR/hooks/tests" ]; then
  warn "hooks/tests/ present in the installed repo (engine tests belong in the kit only)"
fi

# ── 3. Wiring: settings.json == glob of hook modules ───────────────
section "Hook Wiring"

if [ ! -f "$CLAUDE_DIR/settings.json" ]; then
  err "settings.json missing (it is the single hook-wiring source)"
else
  if python3 -c "import json; json.load(open('.claude/settings.json'))" 2>/dev/null; then
    ok "settings.json is valid JSON"
  else
    err "settings.json has JSON syntax errors"
  fi

  # Parity trick: the last whitespace token of each hook command is the hook
  # name ('python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" session_boot'
  # -> "session_boot") — unaffected by the command prefix. The daemon derives
  # HOOK_MODULES by globbing the hooks dir, so the glob IS the module roster:
  # settings wiring must match it exactly.
  wiring_report=$(python3 - <<'PYEOF'
import json, os
problems = []
try:
    settings = json.load(open(".claude/settings.json"))
except (OSError, ValueError):
    raise SystemExit  # already reported above
wired = set()
bad_prefix = []
# Canonical wiring is cwd-independent via $CLAUDE_PROJECT_DIR (set by Claude
# Code on every hook run); the bare relative form is tolerated for installs
# that predate the cwd fix but breaks when the session cwd leaves the repo root.
ALLOWED_PREFIXES = (
    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py"',
    "python3 .claude/hooks/_client.py",
)
for groups in (settings.get("hooks") or {}).values():
    for g in groups:
        for h in g.get("hooks", []):
            cmd = h.get("command", "")
            if "_client.py" not in cmd:
                continue  # non-kit hook commands are out of scope
            parts = cmd.split()
            if parts:
                wired.add(parts[-1])
            if not cmd.startswith(ALLOWED_PREFIXES):
                bad_prefix.append(cmd)
modules = {f[:-3] for f in os.listdir(".claude/hooks")
           if f.endswith(".py") and not f.startswith("_")}
if modules - wired:
    problems.append("hook modules on disk but not wired: " + ", ".join(sorted(modules - wired)))
if wired - modules:
    problems.append("wired but no hook module on disk: " + ", ".join(sorted(wired - modules)))
if bad_prefix:
    problems.append("unrecognized hook command prefix: " + " | ".join(bad_prefix))
print("; ".join(problems))
PYEOF
)
  if [ -z "$wiring_report" ]; then
    ok "settings.json wiring == hook-module glob (cwd-independent commands)"
  else
    err "wiring drift: $wiring_report"
  fi
fi

# Project hook wiring must live ONLY in .claude/settings.json — never in the
# local override or in user-level settings (machine-level guardrails that do
# not go through _client.py are allowed there).
leak_report=$(python3 - <<'PYEOF'
import json, os
problems = []
for extra in (".claude/settings.local.json",
              os.path.expanduser("~/.claude/settings.json"),
              os.path.expanduser("~/.claude/settings.local.json")):
    try:
        hooks = json.load(open(extra)).get("hooks", {})
    except (OSError, ValueError):
        continue
    leaked = sorted({h["command"].split()[-1]
                     for groups in hooks.values() for g in groups
                     for h in g.get("hooks", []) if "_client.py" in h.get("command", "")})
    if leaked:
        problems.append(f"{extra}: {', '.join(leaked)}")
print("; ".join(problems))
PYEOF
)
if [ -z "$leak_report" ]; then
  ok "no _client.py wiring outside .claude/settings.json"
else
  err "project hook wiring leaked into other settings files: $leak_report"
fi

# ── 4. Daemon ───────────────────────────────────────────────────────
section "Hook Daemon"

if [ -f "$CLAUDE_DIR/hooks/.daemon.pid" ] && kill -0 "$(cat "$CLAUDE_DIR/hooks/.daemon.pid" 2>/dev/null)" 2>/dev/null; then
  ok "daemon running (PID $(cat "$CLAUDE_DIR/hooks/.daemon.pid"))"
else
  warn "daemon not running (auto-starts on first hook call; _client.py falls back to direct exec)"
fi

# ── 5. Memory roster ────────────────────────────────────────────────
section "Memory Roster (.memory/)"

if [ ! -d "$MEM_DIR" ]; then
  err ".memory/ missing entirely"
else
  missing_files=""
  for name in STATE DECISIONS ISSUES IDEAS GOTCHAS CONVENTIONS VERIFY CHANGELOG DOCS-CHANGELOG; do
    [ -f "$MEM_DIR/$name.md" ] || missing_files="$missing_files $name.md"
  done
  if [ -z "$missing_files" ]; then
    ok "all 9 roster files present"
  else
    err "roster files missing:$missing_files"
  fi

  missing_dirs=""
  for d in contexts references diary auto; do
    [ -d "$MEM_DIR/$d" ] || missing_dirs="$missing_dirs $d/"
  done
  if [ -z "$missing_dirs" ]; then
    ok "all knowledge directories present (contexts references diary auto)"
  else
    err "knowledge directories missing:$missing_dirs (re-run install.sh to reseed)"
  fi

  # cache/ is runtime scratch — hooks recreate it on demand, so absence is
  # only a warning. Its .gitignore must contain "*" and "!.gitignore" (the
  # tracked-self-ignore mechanism that lets the dir survive clones).
  if [ ! -d "$MEM_DIR/cache" ]; then
    warn ".memory/cache/ missing (hooks recreate it on demand; install.sh reseeds it)"
  elif [ -f "$MEM_DIR/cache/.gitignore" ] && grep -qxF '*' "$MEM_DIR/cache/.gitignore" 2>/dev/null \
       && grep -qxF '!.gitignore' "$MEM_DIR/cache/.gitignore" 2>/dev/null; then
    ok "cache/ is self-gitignored (tracked .gitignore: '*' + '!.gitignore')"
  else
    warn ".memory/cache/.gitignore missing or lacks '*' + '!.gitignore'"
  fi

  # Every kit.json always_load path must exist — session_boot instructs the
  # agent to Read each one every session.
  if [ -f "$CLAUDE_DIR/kit.json" ]; then
    missing_al=$(python3 - <<'PYEOF'
import json, os
try:
    kit = json.load(open(".claude/kit.json"))
except (OSError, ValueError):
    raise SystemExit
missing = [p for p in kit.get("always_load", []) if not os.path.exists(p)]
print(" ".join(missing))
PYEOF
)
    if [ -z "$missing_al" ]; then
      ok "all kit.json always_load paths exist"
    else
      err "always_load paths missing: $missing_al"
    fi
  fi
fi

# ── 6. Diary staleness ──────────────────────────────────────────────
section "Diary"

diary_enabled=$(python3 -c "import json; print(json.load(open('.claude/kit.json')).get('diary', True))" 2>/dev/null || echo "True")
if [ "$diary_enabled" != "True" ]; then
  ok "diary disabled in kit.json — staleness check skipped"
else
  diary_age=$(python3 - <<'PYEOF'
import glob, os, time
files = glob.glob(".memory/diary/*.md")
if not files:
    print("none")
else:
    newest = max(os.path.getmtime(f) for f in files)
    print(int((time.time() - newest) // 86400))
PYEOF
)
  if [ "$diary_age" = "none" ]; then
    warn "no diary entries yet (.memory/diary/YYYY-MM-DD.md; docs_contract will require one)"
  elif [ "$diary_age" -le 3 ] 2>/dev/null; then
    ok "newest diary entry is ${diary_age} day(s) old"
  else
    warn "newest diary entry is ${diary_age} days old (>3 — is work happening off the record?)"
  fi
fi

# ── 7. Local settings hygiene ───────────────────────────────────────
section "Local Settings"

local_file="$CLAUDE_DIR/settings.local.json"
if [ ! -f "$local_file" ]; then
  warn "settings.local.json missing (installer writes autoMemoryDirectory into it)"
else
  if python3 -c "import json; json.load(open('$local_file'))" 2>/dev/null; then
    ok "settings.local.json is valid JSON"
  else
    err "settings.local.json has JSON syntax errors"
  fi
  if git ls-files --error-unmatch "$local_file" >/dev/null 2>&1; then
    err "settings.local.json is git-tracked (per-machine file — untrack it)"
  else
    ok "settings.local.json is untracked (correct)"
  fi
  amd=$(python3 -c "import json; print(json.load(open('$local_file')).get('autoMemoryDirectory',''))" 2>/dev/null || echo "")
  if [ "$amd" = "$TARGET_DIR/.memory/auto" ]; then
    ok "autoMemoryDirectory -> .memory/auto (in-repo memory)"
  else
    warn "autoMemoryDirectory is '${amd:-unset}' (expected $TARGET_DIR/.memory/auto)"
  fi
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "=========================="
echo "Summary: OK=$OK WARN=$WARN ERR=$ERR"
total=$((OK + WARN + ERR))
if [ "$total" -gt 0 ]; then
  echo "Health score: $(( OK * 100 / total ))% ($OK/$total checks OK)"
fi
echo ""

if [ "$ERR" -eq 0 ] && [ "$WARN" -eq 0 ]; then
  echo "Ecosystem is fully healthy."
  exit 0
elif [ "$ERR" -eq 0 ]; then
  echo "Ecosystem is operational with $WARN warning(s)."
  exit 0
else
  echo "Ecosystem has $ERR error(s). Review the output above."
  exit 1
fi
