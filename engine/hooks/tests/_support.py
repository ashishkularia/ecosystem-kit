#!/usr/bin/env python3
"""Shared test harness for engine hook tests.

Run the suite from the kit repo root with:

    python3 -m unittest discover -s engine/hooks/tests -q

Hooks follow the daemon contract: module-level main() reading a JSON payload
from sys.stdin and exiting via sys.exit(code). run_hook() mimics the daemon:
it swaps stdin/stdout/stderr, catches SystemExit, and returns
(exit_code, stdout, stderr).

If engine/hooks/_constants.py is ever absent (partial checkout), a
spec-conformant stub is injected into sys.modules so hook modules still
import; tests always patch the hook module's own attributes (load_kit,
MEMORY_DIR, ...) for determinism, so which _constants got imported does not
change outcomes.
"""
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import types

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
HOOKS_DIR = os.path.dirname(TESTS_DIR)

if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

DEFAULT_KIT = {
    "kit_version": "1.0.0",
    "project": "test-project",
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
    "diary": True,
}


def make_kit(**overrides):
    """A fresh kit dict with overrides applied."""
    kit = json.loads(json.dumps(DEFAULT_KIT))
    kit.update(overrides)
    return kit


def _ensure_constants():
    """Import the real _constants, or inject a spec-conformant stub."""
    if "_constants" in sys.modules:
        return sys.modules["_constants"]
    if os.path.exists(os.path.join(HOOKS_DIR, "_constants.py")):
        return importlib.import_module("_constants")

    stub = types.ModuleType("_constants")
    stub.HOOKS_DIR = HOOKS_DIR
    stub.PROJECT_ROOT = tempfile.mkdtemp(prefix="kit-test-root-")
    stub.MEMORY_DIR = os.path.join(stub.PROJECT_ROOT, ".memory")
    stub.KIT_JSON = os.path.join(stub.PROJECT_ROOT, ".claude", "kit.json")
    stub.BLOCKING_HOOKS = {
        "guard_dangerous_commands", "secret_scanner",
        "guard_protected_merge", "docs_contract",
    }
    stub.load_kit = lambda force_reload=False: make_kit()
    stub.SECRET_PATTERNS = []
    stub.PASSWORD_PATTERN = r"""password\s*[:=]\s*['"]([^'"]+)['"]"""
    stub.GENERIC_SECRET_PATTERN = r"""secret\s*[:=]\s*['"]([^'"]{8,})['"]"""
    stub.ALLOWED_PASSWORD_VALUES = {"password", "secret", "", "changeme", "example"}
    stub.DESTRUCTIVE_GIT_PATTERNS = []
    stub.DESTRUCTIVE_GIT_CASE_SENSITIVE = []
    stub.ENV_STAGING_PATTERNS = []
    stub.DESTRUCTIVE_FILESYSTEM_PATTERNS = []
    stub.DB_DESTRUCTIVE_PATTERNS = []
    stub.VALID_COMMIT_TYPES = {
        "feat", "fix", "chore", "refactor", "test",
        "docs", "style", "perf", "ci", "build", "revert",
    }
    stub.SOURCE_EXTENSIONS = {".php", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rb"}
    stub.PROTECTED_FILES = [".claude/settings.local.json"]
    sys.modules["_constants"] = stub
    return stub


def load_hook(name):
    """Import (once) a hook module by basename."""
    _ensure_constants()
    return importlib.import_module(name)


def run_hook(module, payload):
    """Invoke module.main() the way the daemon does.

    Returns (exit_code, stdout, stderr).
    """
    stdin = io.StringIO(json.dumps(payload))
    stdout = io.StringIO()
    stderr = io.StringIO()
    old = (sys.stdin, sys.stdout, sys.stderr)
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    exit_code = 0
    try:
        module.main()
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 0
    finally:
        sys.stdin, sys.stdout, sys.stderr = old
    return exit_code, stdout.getvalue(), stderr.getvalue()


@contextlib.contextmanager
def patched(module, **attrs):
    """Temporarily replace attributes on a module (restores on exit)."""
    missing = object()
    saved = {name: getattr(module, name, missing) for name in attrs}
    for name, value in attrs.items():
        setattr(module, name, value)
    try:
        yield module
    finally:
        for name, value in saved.items():
            if value is missing:
                delattr(module, name)
            else:
                setattr(module, name, value)


def bash_payload(command, **extra):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    payload.update(extra)
    return payload


def write_payload(file_path, content, **extra):
    payload = {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}
    payload.update(extra)
    return payload


def edit_payload(file_path, new_string, **extra):
    payload = {"tool_name": "Edit", "tool_input": {"file_path": file_path, "new_string": new_string}}
    payload.update(extra)
    return payload
