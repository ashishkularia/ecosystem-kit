#!/usr/bin/env python3
"""
PostToolUse:Artifact — mirror every published artifact into the repo.

Artifacts are authored in the session scratchpad (`/tmp/.../scratchpad/`),
which is wiped when the session ends. Publishing therefore produced a live URL
and NOTHING on disk: 37 publishes across two artifacts left zero files behind
(observed 2026-08-27). This hook mirrors each publish into the repo so the
artifact is versioned, diffable, reviewable in a PR, and editable in place.

Layout (``artifacts.dir``, default ``docs/artifacts``)::

    docs/artifacts/<slug>/<slug>.<ext>   source, VERBATIM — publish from this
    docs/artifacts/<slug>/<slug>.md      readable digest (HTML sources only)
    docs/artifacts/<slug>/index.html     generated standalone page — open this
    docs/artifacts/<slug>/artifact.json  id, url, title, description, version
    docs/artifacts/index.html            generated gallery
    docs/artifacts/INDEX.md              same, for GitHub / PR review

Each file has one job. The **source** is stored byte-for-byte because that is
what republishing needs. The **digest** is what reads and diffs in a PR. And
``index.html`` is the browser-openable copy, which the source is NOT: an
artifact is a FRAGMENT by contract — the host supplies <!doctype>/<html>/<body>
at publish time and rejects pages that bring their own — so opening the stored
source directly renders in quirks mode with no viewport meta. (Convention
generalized from homeassistant's ``artifacts/build.py``, 2026-08-26.)

Because every directory has an ``index.html`` and the root has a gallery, the
tree is a static site as-is: ``npx serve docs/artifacts`` needs no build step
and no config.

Neither conversion direction is faithful — the kit is stdlib-only, so md->html
renders a documented subset and html->md is a lossy text digest. Generated
files carry a "do not edit" banner.

Idempotency is keyed on ``tool_response.artifact_id``, which is stable across
republishes — filename is not (the same artifact republishes from the same temp
path, and a retitled artifact changes slug). A directory whose artifact.json
carries the id is reused and rewritten in place, so N republishes yield one
directory, not N.

Advisory only — always exits 0. A failure here must never block a publish.
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _constants import PROJECT_ROOT, load_kit
from _markdown import (
    _FRAGMENT_SHELL,
    GENERATED_MD_BANNER,
    html_fragment_to_page,
    html_to_md,
    md_file_to_html_page,
)

INDEX_NAME = "INDEX.md"
META_NAME = "artifact.json"
MAX_SLUG = 60
GIT_TIMEOUT = 20
DEPLOY_TIMEOUT = 300

# Actions the Artifact tool accepts that are NOT a publish. A comment read or
# an asset upload must not create a directory.
NON_PUBLISH_ACTIONS = {
    "list", "comments", "reply", "resolve",
    "upload_asset", "list_assets", "read_asset", "delete_asset",
}


def cfg() -> dict:
    conf = load_kit().get("artifacts") or {}
    return {
        "enabled": conf.get("enabled", True),
        "dir": conf.get("dir") or "docs/artifacts",
        "commit": conf.get("commit", True),
        "commit_type": conf.get("commit_type") or "docs",
        "deploy_command": conf.get("deploy_command") or "",
        "deploy_timeout": conf.get("deploy_timeout") or DEPLOY_TIMEOUT,
    }


def slugify(text: str, fallback: str = "artifact") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:MAX_SLUG].strip("-")
    return slug or fallback


def find_existing(root: str, artifact_id: str):
    """Return the directory already holding this artifact id, if any."""
    if not artifact_id or not os.path.isdir(root):
        return None
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return None
    for name in entries:
        meta_path = os.path.join(root, name, META_NAME)
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                if json.load(f).get("artifact_id") == artifact_id:
                    return os.path.join(root, name)
        except (OSError, ValueError):
            continue
    return None


def unique_dir(root: str, slug: str, artifact_id: str) -> str:
    """A fresh directory for `slug`, disambiguated if the name is taken."""
    candidate = os.path.join(root, slug)
    if not os.path.exists(candidate):
        return candidate
    return os.path.join(root, "%s-%s" % (slug, (artifact_id or "x")[:8]))


def read_text(path: str):
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def write_text(path: str, text: str) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except OSError:
        return False


def meta_line_html(meta: dict) -> str:
    url = meta.get("url") or ""
    bits = []
    if meta.get("title"):
        bits.append("<strong>%s</strong>" % meta["title"])
    if url:
        bits.append('Published at <a href="%s">%s</a>' % (url, url))
    bits.append("Generated from <code>%s</code> by ecosystem-kit." % meta.get("source_file", ""))
    return " &middot; ".join(bits)


def build_index(root: str, rel_dir: str) -> str:
    """Rebuild INDEX.md from the artifact.json files actually on disk."""
    rows = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for name in names:
        meta_path = os.path.join(root, name, META_NAME)
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        title = str(meta.get("title") or name).replace("|", "\\|")
        desc = str(meta.get("description") or "").replace("|", "\\|")
        if len(desc) > 90:
            desc = desc[:87] + "..."
        url = meta.get("url") or ""
        src = meta.get("source_file") or ""
        rows.append(
            "| [%s](%s/%s) | %s | %s | [open](%s) |"
            % (title, name, src, desc, meta.get("updated_at", ""), url)
        )

    header = [
        "# Published artifacts",
        "",
        "Mirrored automatically by the ecosystem-kit `artifact_sync` hook on every",
        "publish. Each directory holds the **source file** (edit this one), a",
        "**generated counterpart** in the other format, and `artifact.json`.",
        "",
        "To change an artifact: edit its source file here, then republish it with its",
        "URL so the live page and this copy stay in step.",
        "",
        "| Artifact | Description | Updated | Live |",
        "| --- | --- | --- | --- |",
    ]
    if not rows:
        rows = ["| _none yet_ | | | |"]
    return "\n".join(header + rows) + "\n"


def build_gallery(root: str) -> str:
    """A static index.html linking every artifact's viewable page.

    This is what makes the tree servable with no build step: any static server
    resolves `/` to this gallery and `/<slug>/` to that artifact's index.html.
    """
    import html as _html

    cards = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for name in names:
        meta_path = os.path.join(root, name, META_NAME)
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        title = _html.escape(str(meta.get("title") or name))
        desc = _html.escape(str(meta.get("description") or ""))
        updated = _html.escape(str(meta.get("updated_at") or ""))
        url = _html.escape(str(meta.get("url") or ""), quote=True)
        live = ' <a class="live" href="%s">live</a>' % url if url.startswith("https://") else ""
        cards.append(
            '  <li><a class="t" href="%s/">%s</a>%s'
            '<p>%s</p><time>%s</time></li>' % (_html.escape(name, quote=True), title, live, desc, updated)
        )
    if not cards:
        cards = ["  <li><p>No artifacts published yet.</p></li>"]

    body = """<h1>Artifacts</h1>
<p class="sub">Mirrored automatically on publish by the ecosystem-kit
<code>artifact_sync</code> hook. Edit an artifact&rsquo;s source file and
republish to its existing URL &mdash; never edit a generated file.</p>
<ul>
%s
</ul>
<style>
  :root{color-scheme:light dark;--bg:#fff;--fg:#161a20;--muted:#5d6470;--rule:#e3e6ea;--link:#0b5fbd}
  @media (prefers-color-scheme:dark){
    :root{--bg:#14171c;--fg:#e6eaf0;--muted:#98a1ae;--rule:#282e38;--link:#7cc7dc}}
  *,*::before,*::after{box-sizing:border-box}
  body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:46rem;
       margin:0 auto;padding:3rem 1.25rem 5rem;line-height:1.6;color:var(--fg);background:var(--bg)}
  h1{font-size:1.7rem;margin:0 0 .4rem}
  .sub{color:var(--muted);margin:0 0 2rem}
  ul{list-style:none;margin:0;padding:0}
  li{padding:1rem 0;border-top:1px solid var(--rule)}
  li:last-child{border-bottom:1px solid var(--rule)}
  a{color:var(--link)}
  .t{font-size:1.1rem;font-weight:600;text-decoration:none}
  .t:hover{text-decoration:underline}
  .live{font-size:.8rem;margin-left:.6rem;opacity:.75}
  li p{margin:.25rem 0 .15rem;color:var(--muted)}
  time{font-size:.8rem;color:var(--muted);opacity:.8}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em}
</style>
""" % "\n".join(cards)

    return _FRAGMENT_SHELL.format(
        title="Artifacts",
        banner="<!-- GENERATED by ecosystem-kit artifact_sync — do not edit. -->",
        body=body,
    )


def git(args, cwd):
    try:
        return subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None


def gitignored(path):
    """True when git would ignore `path`, so writing there is invisible.

    Mirroring reports success on a successful WRITE, which is not the same as
    the file being kept: DevContainer ignores everything by default
    (`.gitignore` line 1 is `*`, with explicit un-ignores), so artifact_sync
    wrote docs/artifacts/, said "mirrored into the repo", and git discarded all
    of it. The files existed locally and would have vanished on a fresh clone
    (observed 2026-08-28). A hook whose whole purpose is durability must not
    call that success.

    `check-ignore -q` exits 0 when ignored and 1 when not — including when the
    match is a NEGATION pattern, which is what makes it safe to trust here.
    """
    r = git(["check-ignore", "-q", "--", path], PROJECT_ROOT)
    return r is not None and r.returncode == 0


def commit(paths, message, conf):
    """Commit ONLY `paths`. Returns a status string for the report.

    Uses a pathspec commit (`git commit -- <paths>`), which takes those paths
    from the working tree and ignores whatever else is staged — a hook firing
    mid-session must never sweep up unrelated work. Refuses on a protected
    branch and during a merge/rebase; never pushes.
    """
    if not conf["commit"]:
        return "not committed (artifacts.commit is false)"

    inside = git(["rev-parse", "--is-inside-work-tree"], PROJECT_ROOT)
    if not inside or inside.returncode != 0:
        return "not committed (not a git work tree)"

    head = git(["rev-parse", "--abbrev-ref", "HEAD"], PROJECT_ROOT)
    branch = (head.stdout.strip() if head and head.returncode == 0 else "") or ""
    protected = load_kit().get("protected_branches") or []
    if branch in protected:
        return "NOT COMMITTED — on protected branch '%s'; commit it on a branch" % branch
    if branch == "HEAD":
        return "not committed (detached HEAD)"

    git_dir = os.path.join(PROJECT_ROOT, ".git")
    for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD"):
        if os.path.exists(os.path.join(git_dir, marker)):
            return "not committed (merge/rebase in progress)"

    status = git(["status", "--porcelain", "--"] + paths, PROJECT_ROOT)
    if status is not None and status.returncode == 0 and not status.stdout.strip():
        # An empty status means either "nothing changed" or "git cannot see
        # these files at all". Those look identical here and could not differ
        # more, so name the second one.
        ignored = [p for p in paths if gitignored(p)]
        if ignored:
            return ("NOT TRACKED — %s is gitignored, so the mirror exists only on "
                    "this machine and disappears on a fresh clone. Un-ignore it "
                    "(a deny-by-default .gitignore needs an explicit `!` rule) "
                    "or point artifacts.dir somewhere tracked." % ignored[0])
        return "no change to commit"

    # `git commit -- <paths>` is a partial commit over paths git already KNOWS;
    # on an artifact's first publish every file is untracked and it fails with
    # "pathspec ... did not match any file(s) known to git". Stage the artifact
    # paths explicitly first — still scoped, still ignores the rest of the index.
    added = git(["add", "--"] + paths, PROJECT_ROOT)
    if added is None or added.returncode != 0:
        detail = (added.stderr or "").strip().splitlines() if added else []
        return "commit failed at stage: %s" % (detail[0] if detail else "git add failed")

    result = git(["commit", "-m", message, "--"] + paths, PROJECT_ROOT)
    if result is None:
        return "commit failed (git unavailable)"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        return "commit failed: %s" % (detail[0] if detail else "unknown error")
    return "committed on '%s'" % branch


def deploy(conf, artifacts_dir):
    """Run artifacts.deploy_command so the mirrored tree reaches its host.

    Mirroring makes an artifact durable; it does not make it *reachable*. A repo
    serving `docs/artifacts/` from somewhere (the kularia homelab publishes it at
    artifacts.kularia.net via an nginx LXC) otherwise needs a human to remember a
    second command after every publish — which is exactly the kind of step that
    silently stops happening.

    The command is a shell string from kit.json, the same trust level as
    `quality_commands` and `gates.commands`: kit.json is project-owned and is
    already how a project tells the ecosystem what to execute. It ships EMPTY,
    so nothing runs unless a project opts in.

    Placeholders: {dir} absolute path to the artifacts tree, {project} the
    kit.json project name (deploy targets usually key on it).

    Advisory: a failed or slow deploy is reported, never fatal — the artifact is
    already written and committed by the time we get here, and a publish must
    not fail because a host is unreachable.
    """
    command = conf["deploy_command"]
    if not command:
        return None

    project = str(load_kit().get("project") or os.path.basename(PROJECT_ROOT))
    try:
        rendered = command.format(dir=artifacts_dir, project=project)
    except (KeyError, IndexError, ValueError) as e:
        return "deploy skipped — bad placeholder in artifacts.deploy_command (%s)" % e

    try:
        r = subprocess.run(rendered, shell=True, cwd=PROJECT_ROOT, capture_output=True,
                           text=True, timeout=conf["deploy_timeout"])
    except subprocess.TimeoutExpired:
        return "deploy TIMED OUT after %ss (artifact is committed; host may be stale)" % conf["deploy_timeout"]
    except (OSError, subprocess.SubprocessError) as e:
        return "deploy failed to start: %s" % e

    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip().splitlines()
        return "deploy FAILED (exit %d): %s" % (r.returncode, detail[-1] if detail else "no output")
    tail = (r.stdout or "").strip().splitlines()
    return "deployed: %s" % (tail[-1] if tail else "ok")


def main():
    try:
        event = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    if event.get("tool_name") != "Artifact":
        sys.exit(0)

    tool_input = event.get("tool_input") or {}
    response = event.get("tool_response")
    if not isinstance(response, dict):
        sys.exit(0)

    # Only real publishes produce a URL; list/comments/asset actions do not.
    if str(tool_input.get("action") or "publish") in NON_PUBLISH_ACTIONS:
        sys.exit(0)
    url = response.get("url")
    source_path = response.get("path") or tool_input.get("file_path")
    if not url or not source_path or not os.path.isfile(source_path):
        sys.exit(0)

    conf = cfg()
    if not conf["enabled"]:
        sys.exit(0)

    source_text = read_text(source_path)
    if source_text is None:
        sys.exit(0)

    artifact_id = response.get("artifact_id") or ""
    source_ext = os.path.splitext(source_path)[1].lower()
    is_markdown = source_ext in (".md", ".markdown")
    base = os.path.splitext(os.path.basename(source_path))[0]
    title = response.get("title") or tool_input.get("title") or base

    root = os.path.join(PROJECT_ROOT, conf["dir"])
    target = find_existing(root, artifact_id) or unique_dir(root, slugify(title, base), artifact_id)
    slug = os.path.basename(target)

    src_name = "%s%s" % (slug, ".md" if is_markdown else ".html")
    alt_name = "%s%s" % (slug, ".html" if is_markdown else ".md")

    # A republish usually carries only file_path + label, so description and
    # favicon arrive empty. Overwriting blind would erase them on every update;
    # carry the previous values forward unless this publish supplies new ones.
    prior = {}
    prior_path = os.path.join(target, META_NAME)
    if os.path.isfile(prior_path):
        try:
            with open(prior_path, "r", encoding="utf-8") as f:
                prior = json.load(f)
        except (OSError, ValueError):
            prior = {}
    if not isinstance(prior, dict):
        prior = {}

    meta = {
        "artifact_id": artifact_id,
        "url": url,
        "title": title,
        "description": tool_input.get("description") or prior.get("description") or "",
        "favicon": tool_input.get("favicon") or prior.get("favicon") or "",
        "version": response.get("version") or "",
        "source_file": src_name,
        "generated_file": "" if is_markdown else alt_name,
        "viewable_file": "index.html",
        "source_format": "markdown" if is_markdown else "html",
        "published_from": source_path,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    written = []
    if write_text(os.path.join(target, src_name), source_text):
        written.append(src_name)

    # index.html is the BROWSER-OPENABLE copy, and the reason the tree is
    # statically servable: `npx serve docs/artifacts` resolves <slug>/ to it.
    # The stored source stays a fragment because that is what republishing
    # needs — an artifact carries no <!doctype>/<html>/<body>, so opening it
    # directly renders in quirks mode with no viewport meta.
    if is_markdown:
        page = md_file_to_html_page(source_text, title, src_name, meta_line_html(meta))
    else:
        page = html_fragment_to_page(source_text, title, src_name)
    if write_text(os.path.join(target, "index.html"), page):
        written.append("index.html")

    if not is_markdown:
        _, digest = html_to_md(source_text)
        body = [
            GENERATED_MD_BANNER.format(source=src_name),
            "",
            "# %s" % title,
            "",
            "> Lossy text digest of `%s`. The published page is the source of truth:" % src_name,
            "> <%s>" % url,
            "",
            "---",
            "",
            digest or "_No extractable text content._",
            "",
        ]
        if write_text(os.path.join(target, alt_name), "\n".join(body)):
            written.append(alt_name)

    if write_text(os.path.join(target, META_NAME), json.dumps(meta, indent=2) + "\n"):
        written.append(META_NAME)

    index_path = os.path.join(root, INDEX_NAME)
    write_text(index_path, build_index(root, conf["dir"]))
    write_text(os.path.join(root, "index.html"), build_gallery(root))

    rel_target = os.path.relpath(target, PROJECT_ROOT).replace(os.sep, "/")
    rel_index = os.path.relpath(index_path, PROJECT_ROOT).replace(os.sep, "/")
    verb = "update" if response.get("updated") else "add"
    status = commit(
        [rel_target, rel_index],
        "%s(artifact): %s %s" % (conf["commit_type"], verb, slug),
        conf,
    )

    deploy_status = deploy(conf, root)

    lines = [
        "Artifact mirrored into the repo (ecosystem-kit artifact_sync):",
        "  -> %s/ (%s)" % (rel_target, ", ".join(written) or "no files written"),
        "  source of truth: %s — the other file is generated, do not edit it" % src_name,
        "  %s" % status,
    ]
    if deploy_status:
        lines.append("  %s" % deploy_status)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(lines),
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ecosystem-kit] artifact_sync: {e}", file=sys.stderr)
        sys.exit(0)
