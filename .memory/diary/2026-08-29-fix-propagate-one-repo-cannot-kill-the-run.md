# 2026-08-29 — fix/propagate-one-repo-cannot-kill-the-run

## The fix I already claimed to have made

#31 was titled *"survive a slow network"* and its body said a timeout now
"degrades to a per-repo failure instead of an escaping traceback". That was
wrong, and re-reading the diff shows why plainly:

```python
except subprocess.TimeoutExpired:
    if check:
        raise RuntimeError(...)      # still fatal
```

`check` defaults to `True`, and the push call relies on the default. So a
timeout kept killing the run; only the exception's *name* changed. I verified
the new message and never verified the new behaviour.

Today's failure was not even a timeout. mylantite's pre-push gate refused the
push with a non-zero exit — a path #31 never touched at all:

```
RuntimeError: safe-push ... failed: error: failed to push some refs
```

grade5, meritick and homelab were never attempted. Identical outcome, third
occurrence.

## Handling calls versus handling the loop

Twice now I have hardened the specific call that failed. Both times the next
failure arrived through a neighbouring call in the same loop and did the same
damage. Patching failure points is unbounded — and worse, silently undone the
moment someone adds a step.

So the isolation moved to the iteration: the per-repo body is wrapped, one
repo's failure is logged, and the loop continues. That holds for steps nobody
has written yet.

The push keeps its own handling as well, because "push refused" is worth saying
in those words — a generic exception line would leave the reader guessing at
what is a routine, expected outcome for a repo whose gate is red.

## Note

Cannot be proven by running from this branch: `kit-propagate` refuses to
propagate unless the kit checkout is on a synced default branch, which is the
right guard and means this needs merging before the run that demonstrates it.
The three remaining repos stay behind until then.
