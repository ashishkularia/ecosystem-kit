# 2026-09-26 — fix/docs-contract-session-scoped-ledger

Reported via a downstream project (mylantite), running two Claude sessions
on one checkout at once — a reviewer and an implementer, splitting a large
plan into parallel packages. The reviewer's Stop kept blocking on "update
CHANGELOG.md" for source edits the implementing session had made and not
yet documented — the shared `.memory/cache/pending.json` had no way to
tell whose flag was whose, so the reviewer inherited the implementer's
open work every time.

Moved the ledger to one JSON file per `session_id`
(`.memory/cache/pending/<session_id>.json`), threading `session_id`
through `handle_post_tool`/`handle_stop`/`handle_pre_commit` (from the
hook payload, matching `tdd_gate.py`/`context_attach.py`'s own idiom) and
through the CLI `flag`/`set-flag` path (from `CLAUDE_CODE_SESSION_ID`,
since `/decide` and `/idea` invoke the script directly with no payload).

Caught one bug in my own first pass while wiring tests: I'd precomputed
`PENDING_DIR = os.path.join(CACHE_DIR, "pending")` once at import time,
which silently stopped picking up the test harness's patched `CACHE_DIR`
(tests patch module globals directly, not `MEMORY_DIR` cascading through
derived constants). Fixed by making `pending_dir()`/`pending_file()`
functions that read `CACHE_DIR` fresh on each call — the same reason
`CACHE_DIR` itself is patched directly in the existing test fixtures
rather than derived from a patched `MEMORY_DIR`.

Also found and fixed a second test file (`test_docs_contract_diary_scope.py`)
that called the old unparameterized `set_flag`/`save_pending` signatures —
not caught by running just the file I was editing tests for; only surfaced
via the full `python3 -m unittest discover engine/hooks/tests` run. All 211
engine tests green after both fixes.

Added `test_flags_are_scoped_per_session`: session A posts a source edit,
session B's Stop must not block, session A's own Stop still must. Fails
without this change (single shared ledger), passes after.

## 2026-09-27 — review fix-up before merge

The mylantite reviewer found three gaps. A payload or CLI call without a
session id fell back to a shared `default` ledger, which recreates the
cross-session block for any session-less event and leaves CLI flags that
no real session's Stop ever reads; it now records and checks nothing. A
satisfied Stop wrote an empty file per session forever; it now deletes the
file. The pre-change shared `pending.json` stayed on disk in every
installed repo; the first write now removes it. One red test per gap, then
the full suite 214/214. The kit has no CI, so that local run is the gate.
