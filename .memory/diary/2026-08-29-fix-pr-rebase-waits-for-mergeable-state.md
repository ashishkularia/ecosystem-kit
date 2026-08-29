# 2026-08-29 — fix/pr-rebase-waits-for-mergeable-state

## The report

*"can you check we started to ran rebasing of mr when they have conflict. It
runs sometimes and sometimes it doesn't."*

An intermittency report, which is the kind most worth taking literally: the tool
demonstrably works (it resolved homelab#36 at 06:22 today, keeping both sides of
a real `.memory/ISSUES.md` conflict), so the question is what makes it skip.

## Two candidates, one ruled out by evidence

**The attempted-once state key.** `pr-rebase` records `(pr, head_sha, base_sha)`
so an unresolvable conflict is tried once rather than every run. A PR that
failed and never moved would be skipped forever — which would look exactly like
this. Checked all 12 state entries against the live API: **every one is a closed
PR**. Nothing stuck. Not the cause today, though it remains a plausible future
one.

**The mergeability race.** GitHub computes `mergeable_state` asynchronously: a
GET *requests* the computation and returns `mergeable: null` /
`mergeable_state: "unknown"` until it finishes. The detector had:

```python
if ms != "dirty":
    continue  # 'behind'/'blocked'/'unstable'/'unknown' left alone
```

`unknown` — "GitHub has not decided" — was collapsed into the same branch as
"no conflict".

And the bias runs the wrong way. The PRs most likely to be conflicted are the
ones most recently pushed, which are precisely the ones answered `unknown`. So
the resolver was least likely to fire exactly when it was most needed.

I had first-hand evidence and did not connect it: PRs #25, #30 and #35 each
returned `UNKNOWN` on the first poll after a push and settled on a retry, and I
wrote retry loops for my own checks each time. Living with a quirk in one place
while a tool silently loses to it in another.

## The fix

Poll until it settles — 4 attempts, 3s apart, returning immediately when there
is nothing to wait for, so a settled PR still costs one GET. A PR still unknown
after that is **logged and skipped**, never read as clean.

Verified in all three shapes: settles after retries, gives up loudly, and adds
no calls when already settled.

## Not changed

The cron runs 4×/day (08:17, 12:17, 16:17, 20:17), so a conflict appearing at
08:20 waits nearly four hours. That is latency, not failure, and it is a
schedule decision rather than a bug — worth knowing if "it didn't run" sometimes
means "it hasn't run yet".
