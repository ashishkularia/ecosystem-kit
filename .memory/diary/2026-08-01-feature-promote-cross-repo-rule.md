# Diary — feature/promote-cross-repo-rule

Started 2026-08-01 · PR # (fill in once opened)

## Session — lowering the promotion bar

Dear diary,

Ashish: "if any process is capable of being used by more than one repo, then
put the idea in kit. also always explore if the process can benefit any other
repo as well."

**Decided, first, not to file it as an idea** even though he opened with
"another idea is". This is a standing rule about how every future session
works, not something speculative waiting for approval — and IDEAS entries are
explicitly never acted on unasked, so filing it there would have parked a
behavioural rule where it does nothing. It went to DECISIONS as an owner rule
and into the places sessions actually read. I could be wrong about that reading
of his intent, so I'm flagging it rather than burying it.

**What made it concrete:** I went looking for where the rule would bite and
found `/retro` step 4 already had a promotion step — with the bar set at
anything "true for EVERY project using the ecosystem kit". That is a *much*
higher bar than what he asked for, and it fails on today's own work: the
self-hosted-runner guidance is relevant to mylantite and meritick, and not at
all to homelab or grade5. Under the existing wording it is not promotable. Under
his rule it plainly is. So this isn't a nuance — the old text would have
actively rejected the thing we spent the afternoon capturing.

That gave me the phrasing worth keeping: **applicability is not universality.**
Gate a kit artifact by relevance at the point of use — a skill that no-ops where
it doesn't apply — never by keeping it out of the kit.

**The justification I care most about** is one I did not have to invent, because
this repo supplied it today: three forked copies of `split_shell_commands`, only
one of which had learned to extract `$(…)`, and the gap let a push through to a
protected branch. That is exactly the end state of "only one repo needs it today"
— the thing gets copied to the second repo, then the third, and then a fix lands
in one of them. Duplication doesn't just risk inconsistency; it changes the
economics of fixing anything, because patching one copy *feels* like the fix.

**Made it operational, not aspirational.** A promotion rule that lives only in
an architecture diagram is noticed passively, which is the same as not at all —
so: `/retro` step 4 and `/idea` step 5 now ask *could a second repo use this?*
as an explicit step with the question written out; both CLAUDE.mds carry it (the
project template too, so all five repos inherit it on the next propagation); and
the §8 loop diagram's decision line changed from "this learning is not
project-specific" to "could a SECOND repo use this?" — the old line describes a
thing you notice, the new one describes a thing you ask.

## Session — Ashish corrects the bar, and answers my own caveat

Dear diary,

Ashish tightened it before I'd finished: the test is whether **an existing repo
can implement it right now**, not whether some repo might want it later. Future
needs get promoted when the future arrives. The strongest case is another repo
already running something similar.

**He was correcting something I had actually got wrong, not just sharpening
wording.** I had written, in two places, *"'Only one repo needs it today' is a
prediction, not an observation — prefer the kit."* Read plainly that says:
promote on the assumption others will eventually want it. That is speculation,
and it is exactly the failure mode I flagged as an open caveat in the same
breath. I wrote the risk down and then wrote the thing that causes it. Noticing
the tension and still shipping both is worse than missing it.

His rule resolves it cleanly, and the resolution is *present tense*: name the
repo. If you can't name one, you have a guess. That converts the promotion
decision from a judgement about the future into an observation about today —
which is checkable, and therefore enforceable in a command step.

**Decided (revised):** the bar is a second EXISTING repo. Three candidate bars
were on the table and two are now explicitly rejected in DECISIONS, because the
next person will otherwise re-propose one of them: "true for EVERY project" (too
high — rejects the runner guidance) and "could a second repo use this?" (too
vague — invites the speculation above). Also inverted the framing of
duplication: another repo already having its own version doesn't merely *permit*
promotion, it means the promotion is **overdue**. That reads as an alarm rather
than a permission slip, which is the right emotional register given the
`split_shell_commands` fork let a push through.

The runner-guidance example survives the tightening, and is stronger for it: it
qualifies not because five repos might one day run CI, but because mylantite and
meritick **both run self-hosted runners today**. Present tense, nameable, done.

**Open, now much smaller:** I had worried the low bar would cause kit bloat via
speculative promotions. The present-tense test largely closes that — you cannot
promote on "maybe grade5 will need this" when the rule demands you name a repo
that could do it *today*. What remains is the softer boundary: domain-bound
things (schema, business rules, infrastructure names) stay put, and that is a
judgement call rather than a test. I expect we find that line by getting it
wrong once. Still worth watching whether the template count grows faster than
its usefulness — but the sharper risk is now handled by the rule itself rather
than by good intentions.
