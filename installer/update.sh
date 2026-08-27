#!/usr/bin/env bash
# update.sh — refresh kit-owned machinery in an already-installed target repo.
#
# Usage: installer/update.sh TARGET_DIR
#
# Refreshes ONLY:
#   * engine        <kit>/engine/hooks/*.py   -> <target>/.claude/hooks/   (tests/ never installed)
#   * scripts       <kit>/scripts/health-check.sh -> <target>/.claude/scripts/
#   * skills        <kit>/templates/skills/*.md -> <target>/.claude/skills/
#   * commands      <kit>/templates/commands/*.md -> <target>/.claude/commands/  (UNCUSTOMIZED ONLY)
#   * agents        <kit>/templates/agents/*.md   -> <target>/.claude/agents/    (UNCUSTOMIZED ONLY)
#   * kit-version   restamped
#
# NEVER touches: .memory/ (knowledge), .claude/kit.json (project-owned profile),
# settings.json, settings.local.json, CLAUDE.md, .gitignore — nor any command or
# agent a project has edited.
#
# The commands/agents gap (2026-08-27)
# ------------------------------------
# These used to be "untouched by design", on the reasoning that projects
# customize them. The cost was that a kit command could never be IMPROVED:
# templates/commands/pr-babysit.md gained in-thread replies on 2026-08-13 and
# reached none of the five installed repos, because update.sh skipped commands
# and install.sh is skip-if-exists. `install.sh --force` would have delivered it
# by clobbering every project customization — too blunt to use.
#
# The fix distinguishes "stale" from "customized" using a baseline the kit
# already records: .claude/kit-version names the kit COMMIT the target was
# installed/updated from, and update.sh runs inside the kit repo, which has that
# commit's history. So:
#
#   target == current kit template   -> nothing to do
#   target == template AT that commit -> untouched since install; safe to refresh
#   target differs from both          -> project customized it; LEAVE IT, report
#   no usable baseline                -> assume customized; LEAVE IT, report
#
# Conservative by construction: every ambiguous case leaves the project's file
# alone. A project that WANTS the kit version back runs install.sh --force.
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
CUSTOMIZED=0

# The kit commit this target was last installed/updated from — the baseline for
# telling a stale kit file apart from a project-customized one. Line 2 of
# kit-version reads "# updated YYYY-MM-DD from kit commit <sha>".
INSTALLED_COMMIT=""
if [ -f "$CLAUDE_DIR/kit-version" ]; then
  INSTALLED_COMMIT="$(sed -n 's/.*from kit commit \([0-9a-f][0-9a-f]*\).*/\1/p' \
                      "$CLAUDE_DIR/kit-version" | head -1)"
fi
# A sha we cannot resolve is no baseline at all — treat it as absent rather than
# letting `git show` failures read as "unmodified".
if [ -n "$INSTALLED_COMMIT" ] \
   && ! git -C "$KIT_ROOT" rev-parse --verify -q "${INSTALLED_COMMIT}^{commit}" >/dev/null 2>&1; then
  echo "  NOTE     kit-version names commit $INSTALLED_COMMIT, which this kit checkout does not have"
  echo "           (shallow clone or rewritten history) — commands/agents will be left in place"
  echo ""
  INSTALLED_COMMIT=""
fi

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

refresh_seeded_file() { # refresh_seeded_file SRC DST REL_LABEL KIT_REL_PATH
  # For project-OWNED files (commands, agents): refresh only while the target is
  # still byte-identical to the kit template it was installed from. See the
  # header. Every ambiguous case leaves the project's file untouched.
  local src="$1" dst="$2" label="$3" kit_rel="$4"

  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    echo "  NEW      $label"
    NEW=$((NEW+1))
    return
  fi
  if cmp -s "$src" "$dst"; then
    UNCHANGED=$((UNCHANGED+1))
    return
  fi
  if [ -z "$INSTALLED_COMMIT" ]; then
    echo "  KEPT     $label (no baseline to compare against — assumed customized)"
    CUSTOMIZED=$((CUSTOMIZED+1))
    return
  fi

  local baseline
  baseline="$(mktemp)" || { echo "  KEPT     $label (mktemp failed)"; CUSTOMIZED=$((CUSTOMIZED+1)); return; }
  if git -C "$KIT_ROOT" show "$INSTALLED_COMMIT:$kit_rel" > "$baseline" 2>/dev/null; then
    if cmp -s "$baseline" "$dst"; then
      cp "$src" "$dst"
      echo "  UPDATED  $label"
      CHANGED=$((CHANGED+1))
    else
      echo "  KEPT     $label (customized in this project)"
      CUSTOMIZED=$((CUSTOMIZED+1))
    fi
  else
    # The kit did not ship this file at that commit, yet the target has it and
    # it differs — a project-authored file that happens to share a kit name now.
    echo "  KEPT     $label (project-authored; kit did not ship it at $INSTALLED_COMMIT)"
    CUSTOMIZED=$((CUSTOMIZED+1))
  fi
  rm -f "$baseline"
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

# ── Commands and agents refresh (uncustomized only) ─────────────────
for pair in "commands:.claude/commands" "agents:.claude/agents"; do
  kind="${pair%%:*}"
  echo ""
  echo "Commands/agents (${kind}):"
  if [ -d "$KIT_ROOT/templates/$kind" ]; then
    mkdir -p "$CLAUDE_DIR/$kind"
    for f in "$KIT_ROOT/templates/$kind"/*.md; do
      base="$(basename "$f")"
      refresh_seeded_file "$f" "$CLAUDE_DIR/$kind/$base" ".claude/$kind/$base" \
                          "templates/$kind/$base"
    done
  else
    echo "  (kit ships no $kind templates)"
  fi
done

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

Update complete: $NEW new, $CHANGED updated, $UNCHANGED unchanged, $CUSTOMIZED kept (customized).
kit-version: $KIT_VERSION (kit commit $KIT_COMMIT)
Untouched by design: .memory/, .claude/kit.json, settings*.json, CLAUDE.md.
Commands/agents refresh only while still identical to the kit template they were
installed from; anything this project edited is reported as KEPT and left alone.
To deliberately adopt the kit version of a KEPT file: installer/install.sh --force.

Next: restart the Claude Code session, then
  bash $TARGET_DIR/.claude/scripts/health-check.sh $TARGET_DIR
EOF
