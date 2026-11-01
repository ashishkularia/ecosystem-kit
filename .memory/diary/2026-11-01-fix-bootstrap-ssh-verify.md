# 2026-11-01 — fix/bootstrap-ssh-verify

## What happened

The owner merged #56 and asked me, from a mylantite session, to run the
bootstrap. With no terminal attached it deployed the tools (`kit-propagate` and
`prune-stale-branches` in `~/.claude/bin/` now match the kit, #56 included) and
warned that the GitHub SSH key needed manual setup. From the same shell,
`ssh -T git@github.com` answered "successfully authenticated".

## Cause

GitHub refuses a shell, so `ssh -T` exits 1 for a key it accepts. The script
runs under `set -uo pipefail`, and `verify_ssh` piped ssh into `grep -q`, so the
pipe returned ssh's 1 although grep matched. Both came in with the bootstrap
itself (`e9798ef`, 2026-07-24), so the step has never passed: an interactive
run asks for the same step again until it is skipped with `s`.

The script's other `| grep -q` checks read `echo`, `crontab -l` and
`git remote get-url`, which exit 0, so they are not affected.

## Fix

`verify_ssh` keeps the greeting in a variable and greps that.
`test_bootstrap_verify_ssh.py` runs the function under the script's own `set`
line with a stand-in ssh: GitHub's greeting with exit 1 passes, and a refused
key fails. With the old pipe restored, the first test fails. Against
github.com itself the fixed function returns 0.
