# 2026-08-29 — fix/artifact-sync-commits-gallery

## Found by pulling, not by testing

A routine sweep across all six repos turned up one untracked file in meritick:

```
?? docs/artifacts/index.html
```

Everything else from that artifact was committed — the source, the digest, the
per-artifact page, `artifact.json`, `INDEX.md`. Only the root gallery was
missing, and the cause was in plain sight:

```python
commit_paths = [rel_target, rel_index]      # rel_index is INDEX.md
```

The gallery is written two lines earlier and never named again.

## Why it stayed invisible

Three repos track the gallery, so nothing looked wrong. But all three got it
from a hand-run `git add docs/artifacts` during a migration — mine, in the
homelab move and the ecosystem-kit change. **meritick was the first repo where
the hook ran unassisted**, and there the omission finally showed.

The sting: the missing file is `index.html`, the one that makes the tree
servable as a static site. A repo relying on auto-deploy would have published a
directory with no index — the feature quietly delivering everything except the
part that makes it usable.

## Testing the rule instead of the incident

The obvious test is "assert the gallery is in the pathspec". It passes forever
and catches nothing else — including the next generated file someone adds.

The one that shipped walks the written output tree and asserts every file falls
under *some* committed path. It knows nothing about galleries, so it covers
whatever the hook writes next.

Verified by reintroducing the bug rather than assuming the tests were sound:

```
AssertionError: written but never committed: docs/artifacts/index.html
```

Both assertions failed, and the general one named the file. A test that has
never been seen to fail is a guess about what it checks.

## Same family as the last two

Three bugs in a row where the hook reported success for something incomplete:
a commit that could not include untracked files, a write git was ignoring, and
now a generated file left out of the commit. Each looked right locally and was
wrong in the repo — which is the failure mode a durability hook has to be most
suspicious of in itself.
