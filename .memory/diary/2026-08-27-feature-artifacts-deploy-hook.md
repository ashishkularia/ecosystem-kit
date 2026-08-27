# 2026-08-27 — feature/artifacts-deploy-hook

## The gap the owner's question exposed

*"have you pushed all artifacts? and also mapped with local hosting."*

Checking rather than answering: `artifacts.kularia.net/` was live, `/homelab/`
served two artifacts, and `/ecosystem-kit/` returned **404**. The checkup
artifact was committed to the repo and published to claude.ai and reachable
nowhere on the homelab.

`artifact_sync` made artifacts **durable**. It never made them **reachable**.
Deploying was a second manual command after every publish — precisely the kind
of step that silently stops happening.

## What already fitted, and what did not

The homelab session's `deploy-artifacts.sh` is better than I expected: multi-repo
by design (`<repo>` is a path segment), atomic replace, regenerates its top index
server-side from what is actually there. Feeding it `docs/artifacts` worked
first try, and `/ecosystem-kit/claude-code-checkup/` resolved with **no nginx
config and no rewrite rules** — the per-directory `index.html` from #28 turning
out to be exactly the shape a static host wants.

One thing did not fit, and it is not mine to fix. Its server-side index globs
`"$r"/*.html` — one level, skipping `index.html`. homelab's flat
`<repo>/<name>.html` lists fine; the kit's nested `<repo>/<slug>/index.html`
yields `<h2>ecosystem-kit</h2><ul></ul>`. An empty section. Two designs written a
day apart against the same site, disagreeing by exactly one directory level,
each correct alone. Left alone: that script lives on an unmerged branch another
session is working in.

## Seam, not destination

The temptation was a kit-owned deploy tool. Wrong: `deploy-artifacts.sh` is
genuinely project-bound infrastructure — Proxmox host, CTID 102, an nginx LXC,
`artifacts.kularia.net` — the category the promotion rule explicitly says stays
put.

So the kit ships the **seam**: `artifacts.deploy_command`, a shell string at the
same trust level as `quality_commands` and `gates.commands`, empty by default.
A repo publishing to S3, GitHub Pages or plain scp needs no kit change at all.

## Ordering is the safety argument

`deploy_command` runs **after** the write and after the commit. That ordering is
the whole case for letting a hook shell out at all: by the time it runs, the
artifact is on disk and in git, so an unreachable host, a typo, or a 300s hang
costs a stale web page and nothing more.

Deploy-first, or fatal-on-failure, would let a homelab outage lose an artifact
that had already been published — trading the durability the hook exists to
provide for the convenience it was added for. Every failure path returns a
status string; none raise.

## Caught by my own test fixture

Adding two keys to `cfg()` broke **15 unrelated tests** at once. `SyncTestBase`
stubs `cfg` with a literal dict, so `main()` calling `deploy(conf, ...)` hit
`KeyError`. A reminder that a hand-built stub of a config function is a second
copy of that function's contract, and adding a key changes both.

## Verified against the live host

Not simulated — republished for real:

```
-> docs/artifacts/claude-code-checkup/ (4 files)
   committed on 'feature/artifacts-deploy-hook'
   deployed: deployed -> https://artifacts.kularia.net/ecosystem-kit/
```

`/ecosystem-kit/claude-code-checkup/` → 200, serving
`<title>Claude Code Checkup</title>`; `/homelab/` untouched.

## Note on this repo's kit.json

`deploy_command` here names an absolute path into `/home/ubuntu/homeassistant`.
Machine-specific, and committed deliberately: it is this project's live config,
and if the repo is ever cloned elsewhere the command simply fails **advisory**
and reports it. That is the fail-open design earning its keep rather than a path
that needs guarding. The `profiles/` seeds are untouched — no other repo
inherits it.
