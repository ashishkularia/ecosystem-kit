# 2026-08-27 — feature/machine-layer-gh

## Why

The GitHub MCP server disconnected repeatedly through a long working session,
and `gh` was not installed. That left **no route at all** to open a PR: three
had to be created through a hand-written REST script reading
`~/.secrets/github-pat`. Owner's instruction: *"add gh if mcp is not
available."*

## The tool I decided not to build

`tools/pr-open` was the obvious kit-shaped answer, and I had already offered it.
It fits the existing decision — *the machine layer owns the credential, sessions
call a verb* — and clears the promotion bar cleanly: five repos, all needing
PRs, none able to use `gh`.

Installing `gh` killed it, correctly. `gh` covers PR **and** issue **and**
review work, is maintained upstream, and needs no kit code to stay current;
`pr-open` would have been a permanently thinner reimplementation the kit had to
carry forever. The machine layer's job here is to ensure `gh` is *present and
authenticated from the credential it already owns*, not to replace it.

Worth recording because the reasoning pointed the wrong way: "this clears the
promotion bar" is an argument for a thing being *kit-shaped*, not for it being
*worth building*. A promotion bar filters what belongs in the kit; it does not
ask whether the thing should exist.

## No second credential

`gh` authenticates from `~/.secrets/github-pat` — the same file `pr-thread` and
`pr-comment-poller` read:

```sh
GH_TOKEN="$(cat ~/.secrets/github-pat)" gh auth status
✓ Logged in to github.com account ashishkularia (GH_TOKEN)
```

`gh auth login` would have minted a separate OAuth token in `hosts.yml`, giving
the machine two GitHub credentials with different scopes and lifetimes. One
credential, one place, already chmod 600.

## The install trap, written into the step

Two attempts failed before one worked, and the cause was mine, not the network:

1. First download stalled partway.
2. I started `curl -C -` **while the first was still running**. Two writers
   interleaved into one file and produced **15,220,015 bytes against an expected
   14,863,663** — larger than the target, so not a truncation at all.
3. I then checksummed the file *while it was still being written* and read the
   mismatches as evidence of a bad download.

A single clean download verified first try. The size comparison is what
diagnosed it: a checksum mismatch tells you the bytes are wrong, never why. The
bootstrap step now states both rules — verify the checksum before installing,
and run one download at a time.

Also learned the hard way: `pkill -f 'gh_2.98.0_linux_amd64'` **killed my own
shell**, because `-f` matches full command lines including the one invoking it.
`pkill -x curl` does not.

## Not done

- No auto-install in `bootstrap-machine.sh`. It prints the step and `verify_gh`
  checks it, matching how the SSH key, PAT and Claude login are handled — those
  are owner actions, not things the script performs. Downloading and installing
  a binary unattended is a heavier act than the rest of that script does.
- `gh` is not added to any repo's `permissions.allow`. The read-only `gh pr
  view`/`gh pr checks` rules already live in ecosystem-kit's
  `.claude/settings.local.json` from the doctor run; other repos can add them
  when they actually see the prompts.
