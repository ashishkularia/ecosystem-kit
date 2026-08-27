# 2026-08-27 — feature/artifacts-viewable-and-servable

## Reading another session's work found a bug in mine

Owner mentioned a homelab session was hosting artifacts locally via a static npm
server, and asked whether the kit should absorb it. Reading
`homeassistant/artifacts/` turned up something more useful than a hosting
recipe — a flaw in `artifact_sync`, shipped that same day.

Their `build.py` exists because **artifact sources are fragments**: no
`<!doctype>`, `<html>`, `<head>` or `<body>`, because the claude.ai host
supplies those at publish time and rejects pages that bring their own. Their
README states it plainly: *"That makes them unrenderable anywhere else."*

`artifact_sync` stores the source verbatim — correct for republishing, and
exactly wrong for the owner's original ask, *"so I can view it"*. Confirmed on
the artifact already committed to main:

```
<!doctype              ABSENT
<html                  ABSENT
<body                  ABSENT
<meta name="viewport"  ABSENT
```

A browser will render that, but in quirks mode with no viewport meta. I had
half-delivered "view it" and not noticed, because I only ever looked at the
*published* page — which is the one place the skeleton gets supplied for you.

## What to take, and what to leave

The promotion bar asks which repo could adopt this today. Two were already
solving the same problem separately — homeassistant by hand, ecosystem-kit via
`artifact_sync` — which by our own rule means the kit was late.

But only half of their design is durable:

- **Take**: fragment → standalone wrapping. Genuinely reusable, and the thing
  `artifact_sync` was missing.
- **Leave**: `src/` + `dist/` + `make artifacts`, a hand-maintained README table,
  and publish-by-hand. `artifact_sync` already captures on publish, is
  idempotent on `artifact_id`, and regenerates its own index — their table is a
  drift risk we do not need to inherit.

Taking only the durable half is what stops the kit accreting one repo's
workflow.

## The shell had to be a new one

`_markdown` already had `_HTML_SHELL`, and reusing it was tempting and wrong: it
sets its own font, palette and measure, which is right for rendering a bare
markdown file and actively harmful for an artifact that ships a complete design
of its own. Every mirrored artifact would have rendered subtly unlike its
published self.

So `_FRAGMENT_SHELL` carries only the reset the artifact host itself applies —
the same conclusion `build.py` reached independently, and its comment says so
for the same reason. Verified the artifact's own `Bricolage Grotesque` and
palette survive wrapping.

## index.html, not <slug>.html

Both make an artifact viewable; only `index.html` makes the tree *servable*,
because every static server resolves `/<slug>/` to it with no config, no rewrite
rules and no build step. Since the owner is serving these from a static npm
server, "openable from disk" and "servable as a site" had to be the same file.

It also removed a redundant file: a markdown source is already the readable
form, so emitting both `<slug>.html` and `index.html` was pure duplication. One
existing test asserted the old name and was updated to the new contract — a real
behavior change, not a test papered over.

Proved by actually serving it rather than reasoning about it:

```
GET /                        200  text/html   <title>Artifacts</title>
GET /claude-code-checkup/    200  <!doctype html>
```

## The feature demonstrated itself, twice

The scratchpad copy of the artifact source was wiped by a session restart —
again. But the repo copy survived, so I republished **from the repo**, passing
the existing URL, and the live artifact updated in place. That is precisely the
workflow the README describes, exercised by accident.

## Note for the homelab session

`homeassistant/artifacts/` is now redundant with the kit, but **not yet
superseded in that repo**: it holds two real artifacts (`build-plan`,
`sim-rig`) whose URLs live only in its README table. Migrating them means
republishing each from its `src/` file so `artifact_sync` captures id, URL and
metadata — not moving files by hand. That is the other session's call and their
repo; flagged here, not done.
