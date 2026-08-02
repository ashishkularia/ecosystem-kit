# Diary — feature/pr-reply-in-thread

Started 2026-08-03 · PR # (fill in once opened)

## Session — replies belong where the comment was made

Dear diary,

Ashish wants the PR-comment poller to reply **in the same thread** rather than
opening a new one or dropping a general comment on the PR wall. He invited
questions, so I asked two; he answered both crisply:

- inline comments → reply in-thread **and resolve** once addressed
- PR-wall comments → a new general comment (there is no thread to reply to)

**What was actually wrong.** The tooling was already capable —
`add_reply_to_pull_request_comment` has been in the poller's `--allowedTools`
grant all along. The failure was instructional: the poller's prompt said only
"reply to each addressed thread", and `/pr-babysit` said "reply with reasoning".
Neither says *how*, and `add_issue_comment` is granted right alongside, so
answering an inline comment with a wall comment is the path of least
resistance. A capability nobody is told to use is not a feature.

**The interesting constraint: resolving is GraphQL-only.** REST cannot resolve
a review thread, and no MCP tool exposes `resolveReviewThread` either. So
"reply and resolve" could not be satisfied by prompt wording alone — the
capability genuinely did not exist. I verified that before designing anything:
ran the GraphQL query against a real PR with the PAT and got a clean response.

**Decided: a machine-layer tool, `tools/pr-thread`.** The alternative was
teaching each headless session to hold the PAT and hand-write GraphQL, which
breaks the rule that Claude never handles secret values, and would put a
credential in a prompt. `safe-push` is the precedent: the machine layer owns
the credential and the policy, sessions call a verb. `pr-thread threads` lists
unresolved threads with their node ids and the comment id to reply to;
`pr-thread resolve` closes one.

**The guard I'm most pleased with.** `resolve` REFUSES unless the thread's
newest comment carries the `GunAsh-` marker — i.e. unless a reply was actually
posted first. "Reply, then resolve" was going to be a line in a prompt, and a
rule that lives in a prompt holds until the session is distracted. Now it is
mechanical. It also reuses the marker the poller already mints for loop
protection, so it cost nothing new: replies post under the owner's PAT, so
authorship cannot distinguish them, and the marker is the only signal that
works.

Tested it against mylantite_app#44 — 29 unresolved threads, none replied to —
and it refused, mutating nothing. Verified the count was still 29 afterwards
rather than trusting the exit code.

**Open / deliberately not done:** I did not run the poller for real. It would
launch a headless session against #44 and post replies to a live PR with 29
open threads — that is Ashish's call to make, not a test I get to run. `check`
mode says it would launch (11 new comments), which is as far as I should go
unasked.
