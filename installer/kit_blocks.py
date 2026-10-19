#!/usr/bin/env python3
"""kit_blocks — keep the kit-managed blocks of a project's CLAUDE.md in sync.

Usage: kit_blocks.py TEMPLATE TARGET

CLAUDE.md is project-owned, which is why `update.sh` never used to touch it —
and why a policy added to `templates/CLAUDE.md.template` reached only NEW
installs (2026-10-19: five repos got the scratch directory but not the rule
that tells Claude to use it). The owner approved one narrow exception
(2026-10-20): text between a matching pair of marker lines is kit-owned.

    <!-- kit:begin NAME (any note) -->
    ...kit-owned text, rewritten on every update...
    <!-- kit:end NAME -->

The template is the single source of truth: each block in TEMPLATE is synced
into TARGET. Per block —

    present in TARGET, identical   -> nothing
    present in TARGET, different   -> the begin..end lines are replaced
    absent from TARGET             -> appended once, after a blank line
    malformed in TARGET            -> KEPT, file untouched for that block

Everything outside the markers is preserved byte for byte. Malformed means a
lone or duplicated marker, end before begin, or another block's marker inside
(blocks do not nest); a CRLF file is KEPT wholesale rather than half-converted.
Markers are recognised only as a whole line, flush left, so prose, code samples
and indented examples that mention one are ignored.

Text is spliced as lines (never `re.sub`, which would read `\\1` in a policy as
a group reference). The file is replaced atomically through its real path, so a
CLAUDE.md that is a symlink stays one. A broken TEMPLATE is the kit's bug and
exits 1 without touching anything; blocks may not contain `{{placeholders}}`
because update.sh does not render them.

Output: one human line per change, then `@counts new=N changed=N unchanged=N
kept=N` for update.sh to fold into its summary. Stdlib only.
"""
import os
import re
import shutil
import sys

LABEL = "CLAUDE.md"
BEGIN_RE = re.compile(r"^<!-- kit:begin ([a-z0-9][a-z0-9-]*)(?: .*)? -->$")
END_RE = re.compile(r"^<!-- kit:end ([a-z0-9][a-z0-9-]*) -->$")


class BlockError(Exception):
    """The TEMPLATE is unusable — a kit bug, never a project problem."""


def _markers(lines):
    found = []
    for i, line in enumerate(lines):
        m = BEGIN_RE.match(line)
        if m:
            found.append((i, "begin", m.group(1)))
            continue
        m = END_RE.match(line)
        if m:
            found.append((i, "end", m.group(1)))
    return found


def spans(lines):
    """Return (good, bad): good maps name -> (begin_idx, end_idx) for blocks with
    exactly one begin and one end, in order, nothing else between; bad maps the
    rest to a human reason."""
    markers = _markers(lines)
    names = []
    for _, _, name in markers:
        if name not in names:
            names.append(name)
    good, bad = {}, {}
    for name in names:
        begins = [i for i, kind, n in markers if n == name and kind == "begin"]
        ends = [i for i, kind, n in markers if n == name and kind == "end"]
        if len(begins) != 1 or len(ends) != 1:
            bad[name] = (f"{len(begins)} begin and {len(ends)} end markers; "
                         f"expected exactly one of each")
            continue
        begin, end = begins[0], ends[0]
        if end < begin:
            bad[name] = "end marker comes before begin marker"
            continue
        inner = [n for i, _kind, n in markers if begin < i < end]
        if inner:
            bad[name] = f"marker for '{inner[0]}' inside the block (blocks cannot nest)"
            continue
        good[name] = (begin, end)
    return good, bad


def _append(lines, block):
    body = list(lines)
    if body and body[-1] == "":
        body.pop()  # the file's final newline; re-added below
    if body and body[-1].strip():
        body.append("")  # one blank line between existing policy and the block
    return body + block + [""]


def sync(template_text, target_text):
    """Return (new_target_text, [(name, status, detail), ...]); status is one of
    INSERTED UPDATED UNCHANGED KEPT. Raises BlockError for a broken template."""
    t_lines = template_text.split("\n")
    t_good, t_bad = spans(t_lines)
    if t_bad:
        name, why = next(iter(t_bad.items()))
        raise BlockError(f"template block '{name}': {why}")
    order = sorted(t_good, key=lambda n: t_good[n][0])
    for name in order:
        begin, end = t_good[name]
        if any("{{" in line for line in t_lines[begin:end + 1]):
            raise BlockError(f"template block '{name}' contains an unrendered "
                             f"placeholder; blocks are copied verbatim")
    if "\r" in target_text:
        return target_text, [(n, "KEPT", "CRLF line endings are not supported")
                             for n in order]

    lines = target_text.split("\n")
    results = []
    for name in order:
        block = t_lines[t_good[name][0]:t_good[name][1] + 1]
        good, bad = spans(lines)
        if name in bad:
            results.append((name, "KEPT", bad[name]))
        elif name in good:
            begin, end = good[name]
            if lines[begin:end + 1] == block:
                results.append((name, "UNCHANGED", ""))
            else:
                lines[begin:end + 1] = block
                results.append((name, "UPDATED", ""))
        else:
            lines = _append(lines, block)
            results.append((name, "INSERTED", "appended at end of file"))
    return "\n".join(lines), results


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _write_atomic(path, text):
    real = os.path.realpath(path)  # write THROUGH a symlinked CLAUDE.md
    tmp = os.path.join(os.path.dirname(real), f".{os.path.basename(real)}.kit-tmp-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        shutil.copymode(real, tmp)
        os.replace(tmp, real)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _counts(results):
    tally = {"INSERTED": 0, "UPDATED": 0, "UNCHANGED": 0, "KEPT": 0}
    for _name, status, _detail in results:
        tally[status] += 1
    return (f"@counts new={tally['INSERTED']} changed={tally['UPDATED']} "
            f"unchanged={tally['UNCHANGED']} kept={tally['KEPT']}")


def main(argv):
    if len(argv) != 3:
        print("Usage: kit_blocks.py TEMPLATE TARGET", file=sys.stderr)
        return 2
    template_path, target_path = argv[1], argv[2]
    try:
        template_text = _read(template_path)
    except OSError as e:
        print(f"kit_blocks: cannot read template: {e}", file=sys.stderr)
        return 1
    if not os.path.isfile(target_path):
        print(f"  NOTE     {LABEL} missing — install.sh seeds it (no blocks synced)")
        print(_counts([]))
        return 0
    try:
        target_text = _read(target_path)
        new_text, results = sync(template_text, target_text)
    except BlockError as e:
        print(f"kit_blocks: template is unusable: {e}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as e:
        print(f"kit_blocks: cannot read {LABEL}: {e}", file=sys.stderr)
        return 1
    if new_text != target_text:
        _write_atomic(target_path, new_text)
    for name, status, detail in results:
        if status == "INSERTED":
            print(f"  INSERTED {LABEL} block '{name}' ({detail})")
        elif status == "UPDATED":
            print(f"  UPDATED  {LABEL} block '{name}'")
        elif status == "KEPT":
            print(f"  KEPT     {LABEL} block '{name}' ({detail}) — fix the markers by hand")
    print(_counts(results))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
