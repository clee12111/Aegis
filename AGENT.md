# AGENT.md — Aegis Agent / Scaffold Pillar

The agent-orchestration pillar, synthesized for a reader. Companion to VERIFIER.md
(Part I) and INFRA.md (Part III). Throughline, shared across all three pillars:
**don't trust a result — verify it deterministically, and don't claim more than the
delta shows.** The running decision trail is in DECISION.md; this doc is the closing
synthesis.

---

## The question

Does an **inference-time scaffold** — guidance or tooling wrapped around a frozen
model — measurably improve a security agent's ability to *exploit* real
vulnerabilities, when the model is held constant? The scaffold delta, not the model,
is the claimed contribution. The model (DeepSeek V4 Flash) is treated as a commodity
baseline and never changed within a comparison.

This pillar is the honest answer to that question, on one benchmark, for one model,
across three scaffold designs.

---

## Substrate

The investigation moved from **BountyBench** (real-repo bounties) to **CVE-Bench**
(40 real-world web-application CVEs, run on UK AISI's Inspect, deterministic
`done.sh` verification). The move was forced by iteration economics — BountyBench's
heavy per-task Docker service stacks cap a single bounded node at ~4 concurrent and
make a full sweep 10–12h, while CVE-Bench's independent, pre-built, Inspect-native
tasks run ~10–14 concurrent and sweep in ~25 min. The full latency/infra story is in
INFRA.md.

The switch carried a hard domain constraint, learned the expensive way: the scaffold
thesis only makes sense in the **vulnerability-exploitation domain** (a real bug with
a real fix), so CTF-style benchmarks (InterCode-CTF: 94% non-vuln puzzles) were ruled
out. CVE-Bench is 100% in-domain. Detect was dropped — CVE-Bench is solve-the-exploit;
exploit is the single focus, consistent with the offense-primary decision.

A correction worth recording: DeepSeek V4 Flash is **not a weak model here**. Its
bare zero-day rate (~13%) sits at the published frontier-LLM SOTA for CVE-Bench
zero-day; the benchmark is simply hard for every current model, and the higher
published numbers (AXE ~25–30%) come from multi-agent architecture plus grey-box
metadata, not a stronger base model. So the held-constant cheap model is a legitimate,
frontier-level baseline, not a floored one.

---

## The measurement protocol (the actual contribution)

Every comparison is **bare vs. scaffold on the identical substrate**, differing only
in the scaffold:

- **Identical-config toggle.** The scaffold is switched by a single env var
  (`AEGIS_SCAFFOLD` / `AEGIS_TOOL_SCAFFOLD`); model, budget, prompts, tasks, and
  sandboxes are byte-identical across arms. The bare arm provably receives nothing.
- **Environment fingerprint.** Image digests, Inspect version, model string, and
  flags are recorded so a scaffold run is provably on the same substrate as its
  baseline; the bare baseline is reusable across scaffold versions only while the
  fingerprint matches.
- **Deterministic verification.** Exploit success is scored by CVE-Bench's `done.sh`
  evaluator (objective evidence — file read, DB modified, RCE), not a model judge.
- **Pre-registered in-band subset.** The 13 tasks where an effect could plausibly
  live (partial-pass or addressable-failure tasks) were committed *from the bare
  baseline*, before any scaffold run, to concentrate statistical power honestly.
- **Power analysis.** At an ~12–17% base rate, detecting a 5pp effect needs ~400
  samples/arm; the final run used n=200/arm/variant (5 epochs), powered for ≥10pp.
- **Pre-committed significance bar** (FRONTIER.md Part II): a delta counts only at
  ≥+5pp **and** ≥+2 net fail→pass task-flips **and** consistent sign across epochs.
- **Mechanism attribution.** Every flip is traced to a cause, so a delta is never
  reported without knowing *why* it happened.

The integrity rule throughout: a scaffold must help the agent *communicate or execute
a real finding*, never do the task for it. A delta from an answer-leaking or
auto-correcting intervention does not count.

---

## What was tested, and the results

Three scaffolds, escalating from prompt-level to tool-level:

| Scaffold | Mechanism | zero-day Δ | one-day Δ | Verdict |
|---|---|---|---|---|
| v1 (prompt) | "Patch-discriminating exploit" reasoning checklist | +2.5pp | −1.7pp | Sub-noise (n=2/3, under-powered) |
| v2 (prompt) | Execution-methodology checklist | +2.5pp (fading +2/+1/+0) | −1.7pp (regression) | Sub-noise at n=3 |
| Tool (Family B) | HTTP request linter + response surfacer (diagnostic) | **+0.5pp** | **−1.5pp** (regression) | **Null at powered n=200** |

The tool scaffold was the right *layer* (a frontier-audit correctly identified that
the failures are tool-use, not reasoning) delivered in the wrong *mode*. On the
in-band subset it was +3.1pp zero-day / −4.6pp one-day; **0 net flips** on zero-day,
**−2** on one-day (two regressions, zero new passes). Only one task (CVE-2024-2624)
improved consistently (1/5 → 3/5). No arm met any of the three significance criteria
on an adequately-powered run.

---

## Why it nulled

The diagnosis is consistent across all three scaffolds and is the substantive finding:
**the agent sees its errors and repeats them.** It reads the API spec and still sends
`curl -X GET -d` (a body with GET); the tool surfaces "body with GET → consider POST"
and the agent ignores it and sends the same malformed request again. Passive feedback
— making the error visible — does not change behavior for this model tier. The
execution gap is real, but it is not addressable by methodology or by observation.

This sharpens into the central design tension of the pillar: the integrity-clean
interventions (hint, observe, demonstrate) are the ones the model can ignore, and the
interventions that would *force* the fix (auto-correct the request) are the ones that
cross into doing the task for the agent. The space between "warning light" and
"seatbelt" is exactly the space between "doesn't help" and "gaming."

---

## The binding constraint isn't request hygiene

A final active-scaffold probe — a guardrail that *blocks* a malformed request and
forces a retry (the SWE-agent "seatbelt," not "warning light") — was built to test
whether enforcement, rather than advice, would convert the failure. It produced the
sharpest finding of the pillar, almost by accident. On the test task the guardrail
blocked the malformed `curl`; the agent routed around it via a second tool (raw Python
sockets) and sent a **working** request (`{"status":true}` — request construction was
solved); **and the agent still failed**, burning its remaining turn budget exploring
the wrong exploit path instead of completing the attack chain.

That isolates the bottleneck. Request construction was never the binding constraint —
v1, v2, the diagnostic tool, and the guardrail all targeted it, and here it is fixed
with no resulting pass. The binding constraint is **strategy and chain-completion under
a tight turn budget**: which exploit path to pursue, and finishing it before the budget
runs out. That is a planning problem — the multi-agent / AXE-style architecture that
holds the published one-day SOTA — not a request-hygiene problem. The whole arc is
consistent with it: v2's only measurable benefit was faster failure-abandonment (budget
efficiency), the diagnostic tool nulled, and the guardrail delivered a working request
and the agent still lost. A secondary lesson came free: an active guardrail on one tool
(bash) does not bind — the agent escaped it via another egress path, so
enforcement-based scaffolds must be *complete* to mean anything.

---

## The honest, scoped conclusion

**Passive inference-time scaffolds — prompt-level methodology and diagnostic
tool-level feedback — do not produce above-noise exploit lifts for DeepSeek V4 Flash
on CVE-Bench.** The claim is scoped deliberately. It is *not* "scaffolds don't help."
Whole families remain untested or only probed, and are where published systems get
their lift:

- **Guardrail + retry** (SWE-agent's model: block the malformed request, force a
  retry). *Probed* — and the probe is what isolated the binding constraint: enforcement
  drove a working request, yet the agent still failed downstream (above), so request
  hygiene is not the lever.
- **Multi-agent planning** (AXE's architecture — the source of the published ~30%
  one-day number). The lever that addresses the binding constraint this pillar
  *isolated* — strategy and chain-completion under budget — rather than request
  hygiene. The most-motivated next step, and an architectural change beyond a
  single-agent scaffold.
- **Few-shot demonstration** — one generic worked example of correct HTTP
  construction. The cheapest unexplored falsifier (~$5); targets the "reads spec,
  guesses wrong" pattern by showing rather than telling.
- **Domain tools** (sqlmap, nuclei). Reframes exploitation as a tool-use task rather
  than a request-construction task.
- **Model ladder** — the same scaffolds across DeepSeek → Claude tiers, to separate
  "scaffold doesn't work" from "this model can't act on feedback."

These were left untested by deliberate budget and integrity choices, recorded as
such — not as gaps discovered after the fact.

---

## What stands

The contribution is not a scaffold that works; it is a **measurement apparatus
rigorous enough to reject its own scaffolds, and the honest finding that resulted.**
Concretely:

- A benchmark-agnostic, fingerprinted, parallel harness on Inspect (reusable for any
  future scaffold, model, or benchmark — see INFRA.md), with an env-var toggle that
  makes bare-vs-scaffold comparability trivial.
- Deterministic exploit verification (Part I / VERIFIER.md) so a "pass" is real
  behavior, not a claimed one.
- A disciplined result: pre-registered subset, power analysis, pre-committed bar,
  mechanism attribution, and a null that three scaffolds could not talk their way
  past. The discipline caught what an under-powered or best-of-n report would have
  headlined as a +2.5pp "win."

This is the Meridian thesis in the security domain: build the measurement layer first,
trust the numbers it produces, and don't claim more than the delta — and the limits —
show.

---

## Limits, stated plainly

Single model (DeepSeek V4 Flash); single benchmark (CVE-Bench, 40 web CVEs); passive
scaffolds only; a self-set significance bar (no one publishes within-model scaffold
deltas on CVE-Bench, so the ≥5pp bar is internal, `bar confidence: thin`); and
budget-capped — no model ladder and no active-family interventions were run. The null
may be specific to passive interventions on this model tier; the cheapest experiments
that would test that (a one-shot demonstration, or the same tool scaffold on Claude
Sonnet) are named above and were not run by choice, not by oversight.
