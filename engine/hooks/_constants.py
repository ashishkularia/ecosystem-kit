#!/usr/bin/env python3
"""Shared constants and kit-profile loader for the ecosystem-kit hook engine.

This module is PROJECT-AGNOSTIC. Everything project-specific lives in
`<repo>/.claude/kit.json` and is read via load_kit(). The static tables here
are security primitives (secret shapes, destructive command shapes) that are
the same in every repo.

Filesystem anchors
------------------
Hooks live at ``<repo>/.claude/hooks/``. realpath() is load-bearing: hooks are
invoked through ``python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py"
<hook>`` and may be reached via a symlink, so a plain abspath(__file__) can
walk to the wrong root. Every hook that needs the repo root must import these
rather than re-deriving them (never from the shell cwd, which can drift).
"""

import json
import os
import re

HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
# <repo>/.claude/hooks -> <repo>/.claude -> <repo>
PROJECT_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
MEMORY_DIR = os.path.join(PROJECT_ROOT, ".memory")
KIT_JSON = os.path.join(PROJECT_ROOT, ".claude", "kit.json")

# Hooks that must FAIL CLOSED (exit 2) if the engine itself crashes. Everything
# else fails OPEN (exit 0 + stderr warning) so an advisory-hook bug can never
# block every tool call. See _client.py / _daemon.py.
BLOCKING_HOOKS = {
    "guard_dangerous_commands",
    "secret_scanner",
    "guard_protected_merge",
    "docs_contract",
}

# ---------------------------------------------------------------------------
# kit.json loader — safe defaults for EVERY key so a missing/partial profile
# never crashes a hook.
# ---------------------------------------------------------------------------

_KIT_DEFAULTS = {
    "kit_version": "0.0.0",
    "project": os.path.basename(PROJECT_ROOT) or "project",
    "stack": "generic",
    "protected_branches": ["main", "master"],
    "branch_types": [
        "feature", "fix", "hotfix", "bugfix", "chore",
        "docs", "refactor", "test", "revert",
    ],
    "merge_is_deploy": False,
    "ceremony": {"default": "standard", "levels": {}},
    "gates": {},
    "containers": {},
    "quality_commands": {"format": [], "lint": [], "typecheck": [], "test": []},
    "source_patterns": [],
    "domain_map": [],
    "always_load": [],
    "principles": {
        "tdd": "advise",
        "fail_fast": "advise",
        "logging": "advise",
        "dead_code": "advise",
        "dry_kiss": "advise",
    },
    "file_write_rules": {"blocked": [], "allowed": []},
    "diary": True,
    # "branch": one diary per branch/MR (`YYYY-MM-DD-<branch-slug>.md`), so a
    # change's discussion and decisions stay together and survive the days it
    # spans. "daily": the legacy one-file-per-date behavior.
    "diary_scope": "branch",
}

_kit_cache = None


def load_kit(force_reload: bool = False) -> dict:
    """Read <repo>/.claude/kit.json, merged over safe defaults.

    Every key in _KIT_DEFAULTS is guaranteed present in the result. Nested
    dicts (ceremony, principles, quality_commands) are shallow-merged so a
    profile that omits a sub-key still gets the default sub-key.
    """
    global _kit_cache
    if _kit_cache is not None and not force_reload:
        return _kit_cache

    data = {}
    try:
        with open(KIT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}

    merged = dict(_KIT_DEFAULTS)
    for key, default in _KIT_DEFAULTS.items():
        if key not in data:
            continue
        value = data[key]
        if isinstance(default, dict) and isinstance(value, dict):
            sub = dict(default)
            sub.update(value)
            merged[key] = sub
        else:
            merged[key] = value
    # Carry through any extra keys a profile defines that we don't model.
    for key, value in data.items():
        if key not in merged:
            merged[key] = value

    _kit_cache = merged
    return merged


# ---------------------------------------------------------------------------
# Static security tables (project-agnostic).
# ---------------------------------------------------------------------------

# Secret detection patterns (used by secret_scanner.py).
SECRET_PATTERNS = [
    ("AWS access key", r"AKIA[0-9A-Z]{16}", "AWS access key ID detected"),
    ("SK-prefixed API key", r"""['"]sk-[a-zA-Z0-9]{10,}['"]""", "OpenAI/Anthropic-style API key detected"),
    ("API key", r"""(?i)api[_\-]?key\s*[:=]\s*['"][^'"]{20,}['"]""", "API key with long value detected"),
    ("Private key", r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private key header detected"),
    ("JWT token", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT token detected"),
    ("GitHub token", r"gh[ps]_[A-Za-z0-9_]{36,}", "GitHub personal/service token detected"),
    ("Stripe key", r"""['"]sk_(test|live)_[A-Za-z0-9]{20,}['"]""", "Stripe secret key detected"),
    ("Cloudflare token", r"""(?i)cf[_\-]?api[_\-]?token\s*[:=]\s*['"][^'"]{20,}['"]""", "Cloudflare API token detected"),
    ("Database URL", r"""(?i)(mysql|postgres|postgresql|redis)://[^'":\s]+:[^'"@\s]+@""", "Database connection string with credentials"),
    ("Bearer token", r"""(?i)bearer\s+[a-zA-Z0-9._\-]{20,}""", "Bearer token detected"),
]

PASSWORD_PATTERN = r"""password\s*[:=]\s*['"]([^'"]+)['"]"""
GENERIC_SECRET_PATTERN = r"""secret\s*[:=]\s*['"]([^'"]{8,})['"]"""
ALLOWED_PASSWORD_VALUES = {"password", "secret", "", "changeme", "example"}

# Destructive git patterns (used by guard_dangerous_commands.py).
DESTRUCTIVE_GIT_PATTERNS = [
    r"git\s+push\s+-f\b",
    # Bare --force blindly overwrites; --force-with-lease / --force-if-includes
    # are the SAFE forms (abort if the remote moved unseen) and are allowed —
    # needed for rebase conflict resolution. Negative lookahead lets them pass.
    r"git\s+push\s+.*--force(?!-with-lease|-if-includes)\b",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-f",
    r"git\s+checkout\s+\.\s*($|[;&|])",
    r"git\s+restore\s+\.\s*($|[;&|])",
]

DESTRUCTIVE_GIT_CASE_SENSITIVE = [
    r"git\s+branch\s+-D\b",
]

# Env/secret staging patterns.
ENV_STAGING_PATTERNS = [
    r"git\s+add\s+.*\.env\b",
    r"git\s+add\s+.*credentials",
    r"git\s+add\s+.*\.pem\b",
    r"git\s+add\s+.*\.key\b",
    r"git\s+add\s+-A\b",
    r"git\s+add\s+--all\b",
    r"git\s+add\s+\.\s*($|[;&|])",
]

# Destructive filesystem patterns.
DESTRUCTIVE_FILESYSTEM_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f",
    r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r",
    r"\bchmod\s+777\b",
]

# Destructive DB patterns. WHERE-less DELETE/UPDATE are handled by dedicated
# checks in guard_dangerous_commands (an end-of-string anchor here was
# defeated by the closing quote of `mysql -e "DELETE FROM users"`).
DB_DESTRUCTIVE_PATTERNS = [
    r"DROP\s+TABLE",
    r"DROP\s+DATABASE",
    r"TRUNCATE\s+TABLE",
]

# Conventional commit types (used by guard_commit_message.py). Kept broad; the
# hook is advisory so a superset is fine across projects.
VALID_COMMIT_TYPES = {
    "feat", "fix", "chore", "refactor", "test",
    "docs", "style", "perf", "ci", "build", "revert",
}

# Source file extensions used by tdd_gate.py when a profile omits source_patterns.
SOURCE_EXTENSIONS = {".php", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rb"}

# Protected file paths that guard_file_writes.py always blocks (project-agnostic).
PROTECTED_FILES = [
    ".claude/settings.local.json",
]


# ── Shell command splitting (security primitive) ────────────────────
# The single implementation for every guard. It used to be copy-pasted into
# guard_protected_merge / guard_dangerous_commands / guard_branch_naming, and
# the copies DRIFTED — only one of them ever learned to extract `$(...)`. A
# security parser with three forks gets fixed in one of them.
#
# The 2026-08-01 bypass: splitting on `&&`, `||`, `;` but not `|` made
# `git push | tail -2` parse as ONE command whose push arguments are
# ['|', 'tail', '-2'], so `tail` read as an explicit (unprotected) destination
# and the push to a protected branch was allowed through.
_REDIRECT_PRECEDING = ">"

# Words that can precede the real command word in a fragment. Left in place,
# they become the "command" a guard inspects, so `do git push` (from a for
# loop) and `sudo git push` both read as not-git and sail past. Assignments
# (`FOO=bar git push`) are stripped by the `=` rule below.
_LEADING_NOISE = frozenset({
    "if", "then", "elif", "else", "fi", "while", "until", "do", "done",
    "for", "in", "case", "esac", "select", "function", "time", "!",
    "sudo", "command", "builtin", "exec", "nohup", "env", "xargs", "eval",
})


def _strip_leading_noise(fragment):
    """Drop shell keywords, wrappers and env assignments so a fragment starts
    with the command word a guard needs to see."""
    tokens = fragment.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _LEADING_NOISE:
            i += 1
            continue
        # VAR=value prefix (never a command word: no '=' before the first '/')
        if "=" in tok and not tok.startswith("=") and "/" not in tok.split("=", 1)[0]:
            i += 1
            continue
        break
    return " ".join(tokens[i:]) if i else fragment


def split_shell_commands(command):
    """Split a shell command line into simple commands, respecting quotes.

    Splits on every unquoted operator that can begin a new command —
    ``&&`` ``||`` ``;`` ``|`` ``&`` and newline — plus the grouping and
    substitution delimiters ``(`` ``)`` ``{`` ``}`` and backticks, so
    ``(git push)``, ``$(git push)`` and ``` `git push` ``` cannot hide a
    command from a guard. ``$(...)`` and backtick bodies are ALSO appended
    whole, so a substitution is still checked when its delimiters are
    unbalanced or nested.

    ``&`` is literal when it follows ``>`` (``2>&1``, ``>&2``) — that is a
    redirection, not a background operator.

    Deliberately OVER-splits rather than under-splits: this feeds security
    guards, where an extra fragment costs at most a false positive, while a
    missed fragment is a bypass.
    """
    commands = []
    current = []
    in_single = False
    in_double = False
    i = 0

    def flush():
        cmd = "".join(current).strip()
        current.clear()
        if not cmd:
            return
        commands.append(cmd)
        stripped = _strip_leading_noise(cmd)
        # Keep BOTH: the raw fragment (patterns that match whole command lines)
        # and the stripped one (guards that inspect the first token).
        if stripped and stripped != cmd:
            commands.append(stripped)

    while i < len(command):
        c = command[i]
        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
            continue
        if not in_single and not in_double:
            if command[i:i + 2] in ("&&", "||"):
                flush()
                i += 2
                continue
            if c == "&":
                prev = "".join(current).rstrip()
                if prev.endswith(_REDIRECT_PRECEDING):
                    current.append(c)  # 2>&1 / >&2 — redirection, not a separator
                    i += 1
                    continue
                flush()
                i += 1
                continue
            if c in (";", "|", "\n", "(", ")", "{", "}", "`"):
                flush()
                i += 1
                continue
        current.append(c)
        i += 1

    flush()

    # Substitution bodies, checked whole as well as via the delimiter splits.
    for pattern in (r"\$\(([^)]+)\)", r"`([^`]+)`"):
        for match in re.finditer(pattern, command):
            inner = match.group(1).strip()
            if inner and inner not in commands:
                commands.append(inner)

    return commands
