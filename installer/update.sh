#!/usr/bin/env bash
# update.sh — refresh kit-owned machinery in an already-installed target repo.
#
# Usage: installer/update.sh TARGET_DIR
#
# Refreshes ONLY:
#   * engine        <kit>/engine/hooks/*.py   -> <target>/.claude/hooks/   (tests/ never installed)
#   * scripts       <kit>/scripts/health-check.sh -> <target>/.claude/scripts/
#   * skills        <kit>/templates/skills/*.md -> <target>/.claude/skills/
#   * kit-version   restamped
#
# NEVER touches: .memory/ (knowledge), .claude/kit.json (project-owned profile),
# commands/, agents/, settings.json, settings.local.json, CLAUDE.md, .gitignore.
#
# Prints exactly what changed before the summary.

set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
KIT_ROOT="$(dirname "$SCRIPT_DIR")"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$#" -eq 1 ] || { echo "Usage: installer/update.sh TARGET_DIR" >&2; exit 1; }
[ -d "$1" ] || die "TARGET_DIR does not exist: $1"
TARGET_DIR="$(cd "$1" && pwd -P)"
[ "$TARGET_DIR" != "$KIT_ROOT" ] || die "refusing to update the kit repo itself"

git -C "$TARGET_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "TARGET_DIR is not a git repository: $TARGET_DIR"

CLAUDE_DIR="$TARGET_DIR/.claude"
[ -f "$CLAUDE_DIR/kit.json" ] \
  || die "kit is not installed in $TARGET_DIR (no .claude/kit.json) — run installer/install.sh first"
[ -d "$KIT_ROOT/engine/hooks" ] || die "kit is incomplete: $KIT_ROOT/engine/hooks missing"

echo "Ecosystem Kit updater"
echo "  kit:    $KIT_ROOT"
echo "  target: $TARGET_DIR"
echo ""

NEW=0
CHANGED=0
UNCHANGED=0

refresh_file() { # refresh_file SRC DST REL_LABEL
  local src="$1" dst="$2" label="$3"
  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    echo "  NEW      $label"
    NEW=$((NEW+1))
  elif cmp -s "$src" "$dst"; then
    UNCHANGED=$((UNCHANGED+1))
  else
    cp "$src" "$dst"
    echo "  UPDATED  $label"
    CHANGED=$((CHANGED+1))
  fi
}

# ── Engine refresh (.claude/hooks/) ─────────────────────────────────
echo "Engine (.claude/hooks/):"
mkdir -p "$CLAUDE_DIR/hooks"
engine_count=0
for f in "$KIT_ROOT"/engine/hooks/*.py; do
  refresh_file "$f" "$CLAUDE_DIR/hooks/$(basename "$f")" ".claude/hooks/$(basename "$f")"
  engine_count=$((engine_count+1))
done
[ "$engine_count" -gt 0 ] || die "no engine hooks found under $KIT_ROOT/engine/hooks"

# Hooks present in the target but not shipped by the kit: report, never delete
# (they may be deliberate project-local additions).
for f in "$CLAUDE_DIR"/hooks/*.py; do
  base="$(basename "$f")"
  if [ ! -f "$KIT_ROOT/engine/hooks/$base" ]; then
    echo "  NOTE     .claude/hooks/$base is not shipped by the kit (left in place)"
  fi
done

# ── Scripts refresh (.claude/scripts/) ──────────────────────────────
# Without this, targets keep whichever health-check they were installed with
# forever — DevContainer sat on a pre-$CLAUDE_PROJECT_DIR copy that flagged
# the kit's own canonical wiring as an ERR (2026-08-01 hygiene finding).
echo ""
echo "Scripts (.claude/scripts/):"
mkdir -p "$CLAUDE_DIR/scripts"
refresh_file "$KIT_ROOT/scripts/health-check.sh" "$CLAUDE_DIR/scripts/health-check.sh" ".claude/scripts/health-check.sh"

# ── Skills refresh (.claude/skills/) ────────────────────────────────
echo ""
echo "Skills (.claude/skills/):"
if [ -d "$KIT_ROOT/templates/skills" ]; then
  mkdir -p "$CLAUDE_DIR/skills"
  for f in "$KIT_ROOT"/templates/skills/*.md; do
    refresh_file "$f" "$CLAUDE_DIR/skills/$(basename "$f")" ".claude/skills/$(basename "$f")"
  done
else
  echo "  (kit ships no skill templates)"
fi

# ── kit-version restamp ─────────────────────────────────────────────
KIT_VERSION="$(python3 - "$KIT_ROOT/kit.config.example.json" "$CLAUDE_DIR/kit.json" <<'PYEOF'
import json, sys
for path in sys.argv[1:]:
    try:
        v = json.load(open(path)).get("kit_version")
        if v:
            print(v)
            break
    except (OSError, ValueError):
        continue
else:
    print("1.0.0")
PYEOF
)"
KIT_COMMIT="$(git -C "$KIT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
{
  echo "$KIT_VERSION"
  echo "# updated $(date +%F) from kit commit $KIT_COMMIT"
} > "$CLAUDE_DIR/kit-version"

# ── Summary ─────────────────────────────────────────────────────────
cat <<EOF

Update complete: $NEW new, $CHANGED updated, $UNCHANGED unchanged.
kit-version: $KIT_VERSION (kit commit $KIT_COMMIT)
Untouched by design: .memory/, .claude/kit.json, commands/, agents/, settings*.json, CLAUDE.md.

Next: restart the Claude Code session, then
  bash $TARGET_DIR/.claude/scripts/health-check.sh $TARGET_DIR
EOF
