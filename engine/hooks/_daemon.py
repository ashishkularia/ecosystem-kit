#!/usr/bin/env python3
"""Hook daemon for the ecosystem-kit engine.

Pre-loads every hook module and dispatches over a Unix socket, eliminating
Python cold-start (~50ms) per invocation.

The hook roster is derived by GLOBBING ``HOOKS_DIR/*.py`` and excluding
``_``-prefixed files (engine internals) and ``tests``. It is NEVER a hardcoded
list — dropping a new ``guard_*.py`` into the directory and restarting the
daemon is all it takes to load it.

Usage:
    python3 _daemon.py {start|stop|status|restart}
"""
import sys
import os
import glob
import json
import signal
import socket
import importlib
import traceback
import io
import threading
import time

HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
SOCKET_PATH = os.path.join(HOOKS_DIR, ".daemon.sock")
PID_FILE = os.path.join(HOOKS_DIR, ".daemon.pid")
LOG_FILE = os.path.join(HOOKS_DIR, ".daemon.log")

sys.path.insert(0, HOOKS_DIR)
try:
    from _constants import BLOCKING_HOOKS
except Exception:
    BLOCKING_HOOKS = {
        "guard_dangerous_commands", "secret_scanner",
        "guard_protected_merge", "docs_contract",
    }

loaded_hooks = {}

# Set by handle_request when it finds the on-disk hook files no longer match
# what this process imported; the accept loop (1s timeout) polls it and exits.
stale_shutdown = threading.Event()

# handle_request swaps the PROCESS-GLOBAL sys.stdout/stderr/stdin around each
# hook call, but clients are served on concurrent threads (the harness fires
# all matcher hooks for one tool call in parallel). Serialize so a fast hook's
# `finally` cannot restore the globals mid-flight under a slow hook.
EXEC_LOCK = threading.Lock()


def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def discover_hook_modules():
    """Glob HOOKS_DIR/*.py, excluding engine internals (_-prefixed) and tests."""
    names = []
    for path in sorted(glob.glob(os.path.join(HOOKS_DIR, "*.py"))):
        base = os.path.splitext(os.path.basename(path))[0]
        if base.startswith("_") or base == "tests":
            continue
        names.append(base)
    return names


def hooks_signature():
    """Fingerprint of every hook file on disk — including _-prefixed internals,
    since a hook's behavior changes when _constants.py does. Compared per
    request against the value captured at load time."""
    sig = []
    for path in sorted(glob.glob(os.path.join(HOOKS_DIR, "*.py"))):
        try:
            st = os.stat(path)
            sig.append((os.path.basename(path), st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append((os.path.basename(path), 0, 0))
    return tuple(sig)


loaded_signature = None


def load_hooks():
    global loaded_hooks, loaded_signature
    loaded_signature = hooks_signature()
    for module_name in discover_hook_modules():
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "main"):
                loaded_hooks[module_name] = module.main
                log(f"Loaded hook: {module_name}")
            else:
                log(f"WARNING: {module_name} has no main() function")
        except Exception as e:
            log(f"ERROR loading {module_name}: {e}")
    log(f"Loaded {len(loaded_hooks)} hooks")


def retire_endpoint():
    """Give up the socket + PID file, but only while we still own them.

    Ownership is the PID file's contents: once a successor has written its own
    PID, these paths are ITS endpoint and unlinking them would strand a live
    daemon with no socket. Idempotent — retiring then exiting is safe."""
    try:
        with open(PID_FILE) as f:
            if int(f.read().strip()) != os.getpid():
                return  # a successor owns the endpoint now
    except (OSError, ValueError):
        return  # already retired, or never ours
    for p in (SOCKET_PATH, PID_FILE):
        try:
            os.unlink(p)
        except OSError:
            pass


def handle_request(data):
    """Handle one hook invocation. Request: {"hook": name, "payload": {...}}.
    Response: {"exit_code": int, "stdout": str, "stderr": str}."""
    try:
        request = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps({"exit_code": 2, "stdout": f"Invalid JSON: {e}", "stderr": ""})

    hook_name = request.get("hook", "")
    payload = request.get("payload", {})

    # A daemon holding hooks imported before update.sh replaced them on disk
    # enforces yesterday's rules (a stale guard_protected_merge wrongly blocked
    # a feature-branch rebase, 2026-07-31). importlib.reload can't fix this —
    # it won't re-evaluate already-imported _-internals — so answer "stale" and
    # exit: the client direct-execs the current on-disk code and auto-restarts
    # a fresh daemon.
    if loaded_signature is not None and hooks_signature() != loaded_signature:
        log("Hook files changed on disk since load — retiring so clients restart me")
        # Retire the socket and PID file BEFORE replying: cmd_start() refuses to
        # start while a live PID file exists, so a successor could not boot until
        # this process finished winding down (leaving hooks on the slow
        # direct-exec path for a whole cooldown window).
        retire_endpoint()
        stale_shutdown.set()
        return json.dumps({"exit_code": 2, "stdout": f"Stale daemon: hook files changed on disk (requested: {hook_name})", "stderr": ""})

    if hook_name not in loaded_hooks:
        return json.dumps({"exit_code": 2, "stdout": f"Unknown hook: {hook_name}", "stderr": ""})

    hook_fn = loaded_hooks[hook_name]
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    stdin_mock = io.StringIO(json.dumps(payload))

    exit_code = 0
    with EXEC_LOCK:
        old_stdout, old_stderr, old_stdin = sys.stdout, sys.stderr, sys.stdin
        sys.stdout, sys.stderr, sys.stdin = stdout_capture, stderr_capture, stdin_mock
        try:
            hook_fn()
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0
        except Exception as e:
            # Apply fail-open/fail-closed policy for an in-hook crash.
            exit_code = 2 if hook_name in BLOCKING_HOOKS else 0
            stderr_capture.write(f"[ecosystem-kit] {hook_name} crashed: {e}\n{traceback.format_exc()}")
        finally:
            sys.stdout, sys.stderr, sys.stdin = old_stdout, old_stderr, old_stdin

    return json.dumps({
        "exit_code": exit_code,
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
    })


def handle_client(conn):
    try:
        data = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
            if b"\n\n" in data:
                data = data[:data.index(b"\n\n")]
                break
        if data:
            response = handle_request(data.decode("utf-8"))
            conn.sendall(response.encode("utf-8"))
    except Exception as e:
        log(f"Client error: {e}")
        try:
            conn.sendall(json.dumps({"exit_code": 0, "stdout": "", "stderr": f"Daemon error: {e}"}).encode("utf-8"))
        except Exception:
            pass
    finally:
        conn.close()


def start_server():
    # AF_UNIX socket paths are limited to ~104 bytes (macOS) / 108 (Linux).
    # A too-deep repo cannot host the daemon; say so instead of dying silently
    # — _client.py falls back to direct execution, so hooks still run.
    if len(SOCKET_PATH.encode("utf-8")) > 103:
        log(
            f"FATAL: socket path too long for AF_UNIX "
            f"({len(SOCKET_PATH)} chars): {SOCKET_PATH} — daemon disabled; "
            f"clients fall back to direct execution."
        )
        return
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    load_hooks()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(10)
    server.settimeout(1.0)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    log(f"Daemon started (PID {os.getpid()})")

    running = True

    def shutdown(signum, frame):
        nonlocal running
        running = False
        log("Shutdown signal received")

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while running and not stale_shutdown.is_set():
            try:
                conn, _ = server.accept()
                threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if running:
                    log(f"Accept error: {e}")
    finally:
        server.close()
        # Ownership-checked: a retired daemon that already handed the endpoint
        # to a successor must not delete the successor's socket/PID file.
        retire_endpoint()
        log("Daemon stopped")


def get_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
        return None


def cmd_start():
    pid = get_pid()
    if pid:
        print(f"Daemon already running (PID {pid})")
        return
    child_pid = os.fork()
    if child_pid == 0:
        os.setsid()
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, 0)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.close(devnull)
        try:
            start_server()
        except Exception:
            # stdio is devnull here — the log file is the only witness.
            log(f"FATAL: daemon crashed during startup:\n{traceback.format_exc()}")
        sys.exit(0)
    else:
        time.sleep(0.3)
        pid = get_pid()
        print(f"Daemon started (PID {pid})" if pid else "Daemon failed to start. Check .daemon.log")


def cmd_stop():
    pid = get_pid()
    if not pid:
        print("Daemon not running")
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        time.sleep(0.1)
        if not get_pid():
            print("Daemon stopped")
            return
    print(f"Daemon still running (PID {pid}). Use kill -9.")


def cmd_status():
    pid = get_pid()
    if pid:
        print(f"Daemon running (PID {pid})")
        print(f"Socket: {SOCKET_PATH}")
        print(f"Hooks discovered: {len(discover_hook_modules())}")
    else:
        print("Daemon not running")


def cmd_restart():
    cmd_stop()
    time.sleep(0.5)
    cmd_start()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: _daemon.py {start|stop|status|restart}")
        sys.exit(1)
    cmd = sys.argv[1]
    {"start": cmd_start, "stop": cmd_stop, "status": cmd_status, "restart": cmd_restart}.get(
        cmd, lambda: (print(f"Unknown command: {cmd}"), sys.exit(1))
    )()
