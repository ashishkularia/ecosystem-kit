# 2026-10-30 — fix/secret-scanner-psql-interpolation

## What the owner asked

In mylantite the owner said to fix every open ISSUES row. One was this kit's:
on 2026-10-21 `secret_scanner` blocked a DB-role bootstrap script holding no
secret, because `CREATE ROLE :"app_user" LOGIN PASSWORD :'app_pass';` matched
the password pattern. The runbook went into mylantite's DEPLOYMENT_GUIDE 1.3
instead, and the row asked for the repro to be reported here. It is fixed here
instead.

## The rule

`password\s*[:=]\s*['"]` took psql's `:'name'` interpolation for an
assignment. What tells them apart is where the colon sits: an assignment puts
it on the key (`password: 'x'`, `password:'x'`) or uses `=`; psql sets it apart
from the keyword and touches the quote. `password : 'x'`, a colon apart from
the key but not touching the quote, still blocks. The generic `secret` pattern
shares the separator.

## Testing

- A test writes the psql lines to a `.sh` path and expects exit 0, and a
  subTest per spacing (`=`, `:` attached, `:` set apart, both patterns) expects
  exit 2.
- With the old `_constants.py` restored, the psql test fails and the rest pass.
- The full engine suite (309 tests) passes.
- The fix's own comment first quoted the repro line, and mylantite's installed
  scanner blocked that edit: the bug, live. The comment describes the form in
  words instead; the repro sits in `tests/`, which the scanner skips.

## Follow-up

Mylantite picks this up with `/kit-update` once this merges.
