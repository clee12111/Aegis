# WORKFLOW.md — Dual-Claude Operating Rules

How the human, Claude.ai (advisor), and Claude Code (engineer) work together
on a project. This file is the bridge between the two Claudes — neither can
do the other's job, and the handoff between them is where things break.

These rules are project-agnostic: they apply to any repo run under the
dual-Claude workflow, not one specific codebase.

---

## The three roles

### Human (operator, decider)

- Holds the goal and the "what's right" call
- Decides interpretive questions (design, framing, what something means)
- Verifies findings the advisor proposes
- Approves work the engineer reports
- Cannot directly read the repo with the advisor (must paste or report)
- Final authority on every decision

### Claude.ai (advisor)

- Interprets results, frames research questions, makes architectural calls
- Has project context (briefs, findings, plans) but NOT the live repo
- Cannot directly read or modify code
- Must rely on the human relaying what the engineer reported
- Writes prompts FOR the engineer; does not write code itself
- Strong on judgment, weak on ground truth — assumes risk of working from
  stale assumptions

### Claude Code (engineer)

- Reads, writes, runs against the real repo
- Has live ground truth; lacks accumulated project framing
- Cannot independently judge whether work matches the larger goal
- Strong on mechanism, weak on direction without context
- Risk: solves an imagined system when context-starved

Neither Claude has the full picture alone. The human bridges.

---

## The two failure modes (these are real, both have happened)

### Failure 1 — Engineer context starvation

Symptom: Claude Code circles a problem 3+ times, each fix making sense
locally but missing the larger structure. Eventually it solves an imagined
version of the system that doesn't match reality.

Cause: prompt didn't carry the WHY — the constraint, the finding, the gate.
Engineer optimized for local correctness because it had nothing else.

Counter: every non-trivial Claude Code prompt carries the WHY inline. If
the engineer needs to know a constraint exists, state the constraint, not
just the task. Reference FINDINGS-as-rules in CLAUDE.md by name.

### Failure 2 — Advisor working from stale assumptions

Symptom: Claude.ai writes a confident spec that assumes the code is shaped
one way; engineer reports back and the assumptions are wrong in three places.

Cause: advisor wrote from project docs (design intent) rather than recon
of the actual code.

Counter: before any meaningful build, run a recon round. Engineer reads
and reports what's actually there. Advisor builds the next prompt against
the report, not the docs.

---

## The standard cycle

For any non-trivial change, run this sequence. Do not skip steps because
they feel slow — skipping them is what causes the failure modes above.

### 1. Advisor proposes a direction

- Frames the problem
- States the decision being made
- Surfaces tradeoffs the human should weigh in on

### 2. Human decides direction

- Picks among options the advisor laid out
- Or proposes a different direction
- Advisor adjusts to the human's call (does not relitigate)

### 3. Recon round (if the change is non-trivial)

- Advisor writes a recon prompt — READ ONLY, do not modify
- Human pastes to Claude Code
- Engineer reads the actual code and reports back, quoting verbatim
- Human pastes engineer's report back to advisor

This step is mandatory for invasive changes. Skip it only for
straightforward edits where the file is already in context.

### 4. Build prompt grounded in the recon

- Advisor writes the actual build prompt against what engineer reported
- Locks design decisions explicitly ("decision X: Y, because Z")
- Names hard constraints inline
- Includes acceptance checks that test the right thing (not noisy quantities)
- Asks engineer to REPORT BACK, not just complete

### 5. Engineer executes and reports

- Reads relevant files first
- Makes the change
- Runs acceptance checks (executes, doesn't just reason)
- Reports back file-by-file with quoted changes
- Honestly flags assumptions that didn't match reality
- States ABSENT if something the prompt expected isn't there

### 6. Advisor verifies the report

- Checks the acceptance results landed correctly
- Spots silent-failure modes (checks that "passed" without actually testing
  the load-bearing thing)
- Flags follow-up fixes if needed
- Updates CLAUDE.md decision log if a meaningful choice was made

### 7. Human approves or sends back

- Reads the advisor's verification
- Makes final call to commit or iterate
- For decisions in their domain (research direction, scope, what to build):
  the human decides without deferring to either Claude

---

## Prompt-writing rules (for the advisor writing TO the engineer)

**Tight, not dense.** State goal, constraints, decisions, acceptance checks.
Do not encode the full mental model — the engineer has the repo, let it
choose the implementation.

**WHY inline.** Every meaningful instruction has a one-line reason. "Hash
the family, not the full config, because the objective is noisy and
final-config dedup catches nothing useful."

**Lock real decisions, leave implementation open.** If the categorical /
continuous split is a locked decision, say so. If the file layout is open,
let the engineer choose.

**Acceptance checks must test the deterministic part.** Asserting on raw
R@8 across runs will fail on embedding nondeterminism — assert on winning
knobs or classifications instead.

**Ask for plain-language reports for human-readable decisions.** If a
choice changes behavior the human will see (e.g., dedup behavior), have
the engineer describe what the user will observe in 3-4 sentences of
plain language. The human can verify behavior without verifying mechanism.

**Don't ask the engineer to make interpretive calls.** "Choose what makes
sense" is a recipe for drift. State the choice or surface it to the human.

---

## Reporting rules (for the engineer writing BACK to the advisor)

**Quote real code, do not paraphrase.** "Updated the config" without code
is not a report.

**Distinguish executed from reasoned.** "Check 1 passed: load_corpus called
1 time(s) for 3 trials" is executed. "Check 3 passes by inspection" is
reasoned. Both are valid — but say which.

**Flag assumption mismatches explicitly.** If the prompt assumed something
the code doesn't match, name it. "Pre-existing mismatch found: ..." is the
right shape.

**State what was removed AND what was kept.** Especially for surgical edits
to existing functions. The kept-as-is parts are as important as the changes.

**Stop and surface if you circle 3+ times.** Do not write more code hoping
it sticks. Stop and tell the human what you don't know.

---

## When to update which file

**SCOPE.md** — when today's focus shifts. Update at the start of a session
if the work has moved.

**ARCHITECTURE.md** — when the actual architecture changes (a new phase
added, a measurement tier reshaped). Rare.

**CLAUDE.md decision log** — every meaningful decision, dated. The engineer
updates this for technical decisions; the advisor updates this for design
decisions the human approved. Format: date, decision, why, precludes.

**This file (WORKFLOW.md)** — when a workflow pattern proves itself or
fails. The current rules came from observed failures; new rules should
come from the same.

---

## The discipline that makes this work

The dual-Claude workflow is asymmetric on purpose. The advisor has more
context but less verification power. The engineer has more verification
power but less context. The human is the only one who has both, briefly,
when relaying.

The temptations:
- Advisor: write longer prompts to compensate for not seeing the code.
  Resist. Tighter is better — the engineer has the repo.
- Engineer: infer beyond what was asked because the prompt seems incomplete.
  Resist. Surface what's missing instead.
- Human: trust either Claude blindly because the work feels right. Resist.
  The structure works because you verify the relay, not because the relay
  is automatic.

The system fails when any of those temptations wins. It works when each
role stays in its lane and the handoffs are explicit.
