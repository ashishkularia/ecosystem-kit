#!/usr/bin/env bash
# install.sh — install the ecosystem kit into a target project repo, BY COPY.
#
# Usage: installer/install.sh TARGET_DIR PROFILE_NAME [--force]
#
#   TARGET_DIR    root of a git repository to install into
#   PROFILE_NAME  a profile from <kit>/profiles/ (mylantite | grade5 | meritick | homelab | devcontainer)
#   --force       overwrite existing project-customized commands/agents/skills
#
# Guarantees:
#   * Idempotent — safe to re-run at any time.
#   * NEVER overwrites existing .memory/ content (knowledge is seeded only where missing).
#   * NEVER overwrites an existing .claude/kit.json (project-owned after first install).
#   * NEVER overwrites an existing .claude/settings.json (prints a manual-merge diff instead).
#   * Engine hooks ARE overwritten (they are kit-owned machinery).
#
# All JSON work goes through python3 (jq is not installed on these hosts).

set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
KIT_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
  cat <<'EOF'
Usage: installer/install.sh TARGET_DIR PROFILE_NAME [--force]

  TARGET_DIR    root of a git repository to install into
  PROFILE_NAME  a profile from profiles/ (mylantite | grade5 | meritick | homelab | devcontainer)
  --force       overwrite existing project-customized commands/agents/skills
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }

# ── Argument parsing ────────────────────────────────────────────────
FORCE=0
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    -*)        usage >&2; die "unknown flag: $arg" ;;
    *)         POSITIONAL+=("$arg") ;;
  esac
done
[ "${#POSITIONAL[@]}" -eq 2 ] || { usage >&2; exit 1; }

TARGET_DIR_RAW="${POSITIONAL[0]}"
PROFILE_NAME="${POSITIONAL[1]%.json}"

# ── Validate kit source layout ──────────────────────────────────────
[ -d "$KIT_ROOT/engine/hooks" ]            || die "kit is incomplete: $KIT_ROOT/engine/hooks missing"
[ -f "$KIT_ROOT/engine/hooks/_client.py" ] || die "kit is incomplete: engine/hooks/_client.py missing"
[ -d "$KIT_ROOT/templates" ]               || die "kit is incomplete: $KIT_ROOT/templates missing"

PROFILE_FILE="$KIT_ROOT/profiles/$PROFILE_NAME.json"
[ -f "$PROFILE_FILE" ] || die "unknown profile '$PROFILE_NAME' (no $PROFILE_FILE). Available: $(cd "$KIT_ROOT/profiles" 2>/dev/null && ls *.json 2>/dev/null | tr '\n' ' ')"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$PROFILE_FILE" \
  || die "profile $PROFILE_FILE is not valid JSON"

# ── Validate target ─────────────────────────────────────────────────
[ -d "$TARGET_DIR_RAW" ] || die "TARGET_DIR does not exist: $TARGET_DIR_RAW"
TARGET_DIR="$(cd "$TARGET_DIR_RAW" && pwd -P)"
[ "$TARGET_DIR" != "$KIT_ROOT" ] || die "refusing to install the kit into itself"

git -C "$TARGET_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "TARGET_DIR is not a git repository: $TARGET_DIR"
GIT_TOP="$(git -C "$TARGET_DIR" rev-parse --show-toplevel)"
[ "$GIT_TOP" = "$TARGET_DIR" ] \
  || die "TARGET_DIR is not the repository root (toplevel is $GIT_TOP) — install at the root"

CLAUDE_DIR="$TARGET_DIR/.claude"
MEM_DIR="$TARGET_DIR/.memory"

echo "Ecosystem Kit installer"
echo "  kit:     $KIT_ROOT"
echo "  target:  $TARGET_DIR"
echo "  profile: $PROFILE_NAME"
[ "$FORCE" -eq 1 ] && echo "  mode:    --force (commands/agents/skills will be overwritten)"
echo ""

mkdir -p "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/commands" "$CLAUDE_DIR/agents" "$CLAUDE_DIR/skills"
mkdir -p "$MEM_DIR/contexts" "$MEM_DIR/references" "$MEM_DIR/diary" "$MEM_DIR/auto" "$MEM_DIR/cache"

# ── Template rendering ({{PROJECT}} {{STACK}} {{DATE}} {{REPO_ABS}}) ──
# Seeded knowledge files must carry real values: session_boot's staleness
# check needs "Last validated: YYYY-MM-DD" to be an actual date, and roster
# headers should name the project, not a placeholder.
PROJECT_NAME="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('project', sys.argv[2]))" "$PROFILE_FILE" "$PROFILE_NAME")"
STACK_NAME="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('stack',''))" "$PROFILE_FILE")"
TODAY="$(date +%F)"

render_file() { # render_file SRC DST — copy SRC to DST substituting placeholders
  python3 - "$1" "$2" "$PROJECT_NAME" "$STACK_NAME" "$TODAY" "$TARGET_DIR" <<'PYEOF'
import sys
src, dst, project, stack, today, repo = sys.argv[1:7]
with open(src) as fh:
    text = fh.read()
text = (text.replace("{{PROJECT}}", project)
            .replace("{{STACK}}", stack)
            .replace("{{DATE}}", today)
            .replace("{{REPO_ABS}}", repo))
with open(dst, "w") as fh:
    fh.write(text)
PYEOF
}

# ── 1. Engine (kit-owned: always overwritten; tests/ never installed) ─
engine_count=0
for f in "$KIT_ROOT"/engine/hooks/*.py; do
  cp "$f" "$CLAUDE_DIR/hooks/$(basename "$f")"
  engine_count=$((engine_count+1))
done
[ "$engine_count" -gt 0 ] || die "no engine hooks found under $KIT_ROOT/engine/hooks"
# Legacy cooldown file from pre-1.0 rehearsal installs (underscore name was
# not covered by the .daemon.* gitignore glob; the engine now writes
# .daemon.start_attempt).
rm -f "$CLAUDE_DIR/hooks/.daemon_start_attempt"
echo "  engine:   $engine_count hook module(s) installed to .claude/hooks/"

# ── 2. Commands / agents / skills (project-customizable: keep existing) ─
copy_md() { # copy_md SRC_DIR DST_DIR LABEL
  local src="$1" dst="$2" label="$3" copied=0 kept=0 f base
  if [ ! -d "$src" ]; then
    echo "  $label: (no templates shipped)"
    return 0
  fi
  for f in "$src"/*.md; do
    base="$(basename "$f")"
    if [ -f "$dst/$base" ] && [ "$FORCE" -eq 0 ]; then
      kept=$((kept+1))
    else
      cp "$f" "$dst/$base"
      copied=$((copied+1))
    fi
  done
  if [ "$kept" -gt 0 ]; then
    echo "  $label: $copied copied, $kept kept as-is (project-customized; --force overwrites)"
  else
    echo "  $label: $copied copied"
  fi
}
copy_md "$KIT_ROOT/templates/commands" "$CLAUDE_DIR/commands" "commands"
copy_md "$KIT_ROOT/templates/agents"   "$CLAUDE_DIR/agents"   "agents"
copy_md "$KIT_ROOT/templates/skills"   "$CLAUDE_DIR/skills"   "skills"

# ── 3. Memory roster (knowledge: seed ONLY where missing, never clobber) ─
seeded=0 existing=0
for t in "$KIT_ROOT"/templates/memory/*.md.template; do
  base="$(basename "$t" .template)"
  if [ -f "$MEM_DIR/$base" ]; then
    existing=$((existing+1))
  else
    render_file "$t" "$MEM_DIR/$base"
    seeded=$((seeded+1))
  fi
done
echo "  memory:   $seeded roster file(s) seeded, $existing left untouched"
for name in STATE DECISIONS ISSUES IDEAS GOTCHAS CONVENTIONS VERIFY CHANGELOG DOCS-CHANGELOG; do
  [ -f "$MEM_DIR/$name.md" ] || echo "  WARN: .memory/$name.md still missing (kit ships no template for it?)"
done

# cache/ self-ignores via a TRACKED .gitignore ("*" + "!.gitignore") so the
# directory survives a clone. Upgrade an older bare-"*" file in place.
if [ ! -f "$MEM_DIR/cache/.gitignore" ] || ! grep -qxF '!.gitignore' "$MEM_DIR/cache/.gitignore"; then
  printf '*\n!.gitignore\n' > "$MEM_DIR/cache/.gitignore"
fi

# Empty knowledge dirs must survive the git round-trip (clone/CI): git tracks
# no empty directories, so seed .gitkeep where nothing else is tracked.
for d in diary auto; do
  if [ -z "$(ls -A "$MEM_DIR/$d" 2>/dev/null)" ]; then
    : > "$MEM_DIR/$d/.gitkeep"
  fi
done

if [ -f "$KIT_ROOT/templates/memory/contexts/README.md" ] && [ ! -f "$MEM_DIR/contexts/README.md" ]; then
  cp "$KIT_ROOT/templates/memory/contexts/README.md" "$MEM_DIR/contexts/README.md"
fi
for r in "$KIT_ROOT"/templates/memory/references/*.md; do
  base="$(basename "$r")"
  [ -f "$MEM_DIR/references/$base" ] || cp "$r" "$MEM_DIR/references/$base"
done

# ── 4. Profile -> kit.json (project-owned after first install) ──────
if [ -f "$CLAUDE_DIR/kit.json" ]; then
  echo "  kit.json: exists — kept (project-owned; never overwritten by the installer)"
else
  cp "$PROFILE_FILE" "$CLAUDE_DIR/kit.json"
  echo "  kit.json: written from profiles/$PROFILE_NAME.json (now project-owned)"
fi

# ── 5. settings.json (hook wiring, relative commands) ───────────────
SETTINGS_TPL="$KIT_ROOT/templates/settings.json.template"
if [ ! -f "$SETTINGS_TPL" ]; then
  echo "  WARN: templates/settings.json.template missing from kit — settings.json not managed"
elif [ ! -f "$CLAUDE_DIR/settings.json" ]; then
  cp "$SETTINGS_TPL" "$CLAUDE_DIR/settings.json"
  echo "  settings.json: written from template"
elif diff -q "$SETTINGS_TPL" "$CLAUDE_DIR/settings.json" >/dev/null 2>&1; then
  echo "  settings.json: exists, identical to kit template"
else
  echo "  settings.json: EXISTS and differs from the kit template — NOT overwritten."
  echo "  Manual merge required; template vs. installed diff:"
  diff -u "$SETTINGS_TPL" "$CLAUDE_DIR/settings.json" | head -n 80 || true
  echo "  (full diff: diff -u $SETTINGS_TPL $CLAUDE_DIR/settings.json)"
fi

# ── 6. settings.local.json (per-machine, untracked): merge autoMemoryDirectory ─
python3 - "$CLAUDE_DIR/settings.local.json" "$KIT_ROOT/templates/settings.local.json.template" "$MEM_DIR/auto" <<'PYEOF'
import json, os, sys

target, template, auto_dir = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(target):
    with open(target) as fh:
        data = json.load(fh)  # invalid JSON here is a real problem: fail fast
elif os.path.exists(template):
    try:
        with open(template) as fh:
            data = json.load(fh)
    except ValueError:
        data = {}
data["autoMemoryDirectory"] = auto_dir
with open(target, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
print(f"  settings.local.json: autoMemoryDirectory -> {auto_dir}")
PYEOF

# ── 7. CLAUDE.md (durable policy file: seed only if the repo has none) ─
if [ -f "$TARGET_DIR/CLAUDE.md" ]; then
  echo "  CLAUDE.md: exists — kept (make sure it points into .memory/)"
elif [ -f "$KIT_ROOT/templates/CLAUDE.md.template" ]; then
  render_file "$KIT_ROOT/templates/CLAUDE.md.template" "$TARGET_DIR/CLAUDE.md"
  echo "  CLAUDE.md: seeded from template — customize for this project"
else
  echo "  WARN: no CLAUDE.md in target and kit ships no template"
fi

# ── 8. .gitignore (append snippet lines that are not already present) ─
SNIPPET="$KIT_ROOT/templates/gitignore.snippet"
if [ -f "$SNIPPET" ]; then
  touch "$TARGET_DIR/.gitignore"
  # Scrub the legacy ".memory/cache/" line older kit versions appended: it
  # excludes the whole dir, which makes the tracked cache/.gitignore
  # mechanism impossible (git cannot re-include inside an excluded dir).
  if grep -qxF '.memory/cache/' "$TARGET_DIR/.gitignore"; then
    python3 - "$TARGET_DIR/.gitignore" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as fh:
    lines = fh.readlines()
with open(path, "w") as fh:
    fh.writelines(l for l in lines if l.rstrip("\n") != ".memory/cache/")
PYEOF
    echo "  .gitignore: removed legacy '.memory/cache/' line (cache/ now self-ignores via its tracked .gitignore)"
  fi
  added=0
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "$line" ] && continue
    case "$line" in '#'*) continue ;; esac
    if ! grep -qxF -- "$line" "$TARGET_DIR/.gitignore"; then
      printf '%s\n' "$line" >> "$TARGET_DIR/.gitignore"
      added=$((added+1))
    fi
  done < "$SNIPPET"
  echo "  .gitignore: $added line(s) appended"
else
  echo "  WARN: templates/gitignore.snippet missing from kit — .gitignore not touched"
fi

# ── 9. kit-version stamp ────────────────────────────────────────────
KIT_VERSION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('kit_version','1.0.0'))" "$CLAUDE_DIR/kit.json" 2>/dev/null || echo "1.0.0")"
KIT_COMMIT="$(git -C "$KIT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
{
  echo "$KIT_VERSION"
  echo "# installed $(date +%F) from kit commit $KIT_COMMIT"
} > "$CLAUDE_DIR/kit-version"
echo "  kit-version: $KIT_VERSION (kit commit $KIT_COMMIT)"

# ── Done ────────────────────────────────────────────────────────────
cat <<EOF

Install complete.

Next steps:
  1. Restart the Claude Code session in $TARGET_DIR
     (the SessionStart hook loads STATE/VERIFY/ISSUES/diary + always_load docs every session).
  2. Run the health check:
       bash $KIT_ROOT/scripts/health-check.sh $TARGET_DIR
  3. Review .claude/kit.json — it is project-owned now; tune gates/ceremony/domain_map.
  4. Commit the new files on a branch. Owner merges — Claude never writes to main/master.
EOF
