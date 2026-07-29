#!/usr/bin/env python3
"""Hook client for the ecosystem-kit engine.

Connects to the hook daemon (fast path) and falls back to direct execution of
the hook file if the daemon is unavailable.

Usage (wired from .claude/settings.json):
    python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" <hook_name>

$CLAUDE_PROJECT_DIR is set by Claude Code to the project root on every hook
run, making the wiring independent of the session's current working directory.
The engine itself derives its paths from realpath(__file__), so this file
needs no knowledge of how it was invoked.

Fail-open vs fail-closed
------------------------
The v1 flaw was that ANY advisory-hook bug could block every tool call. Here,
on an ENGINE/plumbing failure (daemon crash, missing file, unexpected
exception) we exit 0 with a stderr warning UNLESS the hook is in
BLOCKING_HOOKS, in which case we fail CLOSED (exit 2). Individual hook files
apply the same policy in their own __main__ guards, giving defense in depth.
"""
import sys
import os
import json
import socket
import subprocess
import time

HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
SOCKET_PATH = os.path.join(HOOKS_DIR, ".daemon.sock")
DAEMON_SCRIPT = os.path.join(HOOKS_DIR, "_daemon.py")
CONNECT_TIMEOUT = 0.5      # seconds to establish the socket connection
RESPONSE_TIMEOUT = 45.0    # ceiling on waiting for the daemon reply (returns early)
# Dot after "daemon" is load-bearing: the installer's gitignore snippet covers
# daemon runtime files with the glob `.claude/hooks/.daemon.*`.
AUTO_START_COOLDOWN_FILE = os.path.join(HOOKS_DIR, ".daemon.start_attempt")
AUTO_START_COOLDOWN_SECONDS = 60

sys.path.insert(0, HOOKS_DIR)
try:
    from _constants import BLOCKING_HOOKS
except Exception:
    BLOCKING_HOOKS = {
        "guard_dangerous_commands", "secret_scanner",
        "guard_protected_merge", "docs_contract",
    }


def fail(hook_name, message):
    """Apply the fail-open/fail-closed policy for an engine-level failure."""
    print(f"[ecosystem-kit] {hook_name}: {message}", file=sys.stderr)
    sys.exit(2 if hook_name in BLOCKING_HOOKS else 0)


def try_daemon(hook_name, payload_str):
    """Try to execute via daemon. Returns (success, exit_code, stdout, stderr)."""
    if not os.path.exists(SOCKET_PATH):
        return False, 0, "", ""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect(SOCKET_PATH)
        sock.settimeout(RESPONSE_TIMEOUT)

        try:
            payload = json.loads(payload_str) if payload_str else {}
        except json.JSONDecodeError:
            payload = {}

        request = json.dumps({"hook": hook_name, "payload": payload}) + "\n\n"
        sock.sendall(request.encode("utf-8"))

        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
        sock.close()

        response = json.loads(data.decode("utf-8"))
        # A daemon started before this hook file existed reports it as unknown.
        # Fall back to direct exec rather than blocking forever (bootstrap
        # deadlock: restarting the daemon itself needs a tool call).
        if response.get("exit_code") == 2 and response.get("stdout", "").startswith("Unknown hook:"):
            return False, 0, "", ""
        return True, response.get("exit_code", 0), response.get("stdout", ""), response.get("stderr", "")
    except (socket.error, ConnectionRefusedError, json.JSONDecodeError, OSError):
        return False, 0, "", ""


def try_auto_start():
    """Try to auto-start the daemon. Rate-limited to once per cooldown period."""
    if os.path.exists(AUTO_START_COOLDOWN_FILE):
        try:
            if time.time() - os.path.getmtime(AUTO_START_COOLDOWN_FILE) < AUTO_START_COOLDOWN_SECONDS:
                return False
        except OSError:
            pass
    try:
        with open(AUTO_START_COOLDOWN_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass
    try:
        subprocess.Popen(
            [sys.executable, DAEMON_SCRIPT, "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=HOOKS_DIR,
        )
        time.sleep(0.5)
        return os.path.exists(SOCKET_PATH)
    except Exception:
        return False


def fallback_direct(hook_name, payload_str):
    """Fall back to direct execution of the hook script."""
    hook_file = os.path.join(HOOKS_DIR, f"{hook_name}.py")
    if not os.path.exists(hook_file):
        fail(hook_name, f"hook file not found: {hook_file}")
    try:
        result = subprocess.run(
            [sys.executable, hook_file],
            input=payload_str, capture_output=True, text=True,
            # Same ceiling as the daemon RESPONSE_TIMEOUT: cold-start-slow
            # hooks (node-based linters etc.) exceeded 30s on WSL2 in v1.
            timeout=45, cwd=os.getcwd(),
        )
        emit(result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        fail(hook_name, "hook timed out")
    except Exception as e:
        fail(hook_name, f"engine error: {e}")


def emit(exit_code, stdout, stderr):
    """Print captured output and exit. On a blocking exit the harness relays
    STDERR to the model; guards write block reasons to stdout, so mirror stdout
    onto stderr when there is no stderr, otherwise the block reads as
    'No stderr output'."""
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    if exit_code == 2 and stdout and not stderr:
        print(stdout, end="", file=sys.stderr)
    sys.exit(exit_code)


def main():
    if len(sys.argv) < 2:
        print("Usage: _client.py <hook_name>", file=sys.stderr)
        sys.exit(1)

    hook_name = sys.argv[1]

    payload_str = ""
    if not sys.stdin.isatty():
        try:
            payload_str = sys.stdin.read()
        except Exception:
            pass

    success, exit_code, stdout, stderr = try_daemon(hook_name, payload_str)
    if success:
        emit(exit_code, stdout, stderr)

    if try_auto_start():
        success, exit_code, stdout, stderr = try_daemon(hook_name, payload_str)
        if success:
            emit(exit_code, stdout, stderr)

    fallback_direct(hook_name, payload_str)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Last-resort engine failure: apply policy for whatever hook was named.
        name = sys.argv[1] if len(sys.argv) > 1 else ""
        fail(name, f"client crashed: {e}")
