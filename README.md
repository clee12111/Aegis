# Aegis

**A security research agent that finds and exploits real software vulnerabilities — paired with a deterministic verifier that scores whether the result is *actually real*, not just whether a test passed.**

> **Status:** Act II (Self-test) — verifier built and validated (vuln-agnostic, property-oracle + fuzzing). See [writeups/act2-verifier.md](writeups/act2-verifier.md). Active research project.

---

## The idea in one paragraph

Frontier models can already find and exploit some software vulnerabilities. What's missing isn't raw capability — it's *measurement*. Public security-agent benchmarks grade with simple pass/fail (was a flag captured, did a test go green), and nobody checks whether a claimed exploit truly triggered the bug, or whether a "patch" actually closed the vector versus just satisfying the test suite. **Aegis treats the model as a swappable commodity and puts the engineering into the two things the field under-builds: a code-graph-aware retrieval scaffold that localizes vulnerabilities, and a deterministic verifier rigorous enough to catch a gamed result — and that is itself measured for precision and recall.**

## Why this is different

| | Typical security agent | Aegis |
|---|---|---|
| What's optimized | the agent (make it more capable) | the scaffold + verifier around a *fixed* model |
| Grading | pass/fail, trusted | deterministic verifier — **and the verifier's own accuracy is measured** |
| Capability claim | "our agent scores X" | "same model, better localization — here's the *isolated* delta" |

The model is held constant and swapped across providers (Claude / GPT / Gemini), so any improvement is attributable to the scaffold, not to a stronger model. Results are calibrated against published **BountyBench** baselines.

## Architecture

```
Vulnerable repo
      |
      v
Retrieval scaffold          <- the contribution
(call graph · taint flow · entry-point detection · multi-hop chain ranking)
      |
      v
Ranked suspicious paths
      |
      v
Model API (commodity, swappable)
(reasons over the paths -> exploit or patch)
      |
      v
Deterministic verifier      <- the contribution
(did the exploit truly fire? does the patch close the exact vector?)
      |
      v
Two-track evaluation
  |-- Capability:        Detect / Exploit / Patch  vs. BountyBench baselines
  |-- Verifier integrity: precision/recall on a labeled gold set
```

## Evaluation

- **Capability** — Detect / Exploit / Patch on BountyBench (25 real systems, 40 bounties), reported against the published agent baselines.
- **Verifier integrity** — precision/recall on a hand-labeled gold set of *genuine* vs. *gamed* fixes. This is the part the field doesn't measure.
- **Discipline** — multiple attempts per task, variance-aware; sub-noise deltas don't count.

## Roadmap

| Act | Focus | Status |
|---|---|---|
| **I — Foundations** | Domain ramp; environment; understand 3 real CVEs cold | Complete — environment proven end-to-end on GCP; CVE study complete |
| **II — Self-test** | Attack own systems; build + calibrate the verifier | **In progress** — verifier built & validated (property + fuzzing, vuln-agnostic); scaffold delta next |
| **III — Benchmark** | BountyBench + ZeroDayBench vs. published baselines | Planned |
| **IV — Generalization** | Arbitrary open-source repos; optional RL loop | Planned |

## Tech stack

Python · Docker / Kali (BountyBench-compatible sandboxing) · pytest-style exploit/patch harness · Tree-sitter (AST parsing) · NetworkX (call graphs) · CodeQL / Semgrep (static signal) · Anthropic / OpenAI / Google APIs (provider-swappable) · [BountyBench](https://github.com/bountybench/bountybench) (primary benchmark)

## What this is *not*

Not a general coding agent. Not an RL training project (inference-time throughout the core work). Not a jailbreak agent. Not a pentest-firm replacement. The contribution is the measurement layer, not the model's raw capability.

## Responsible disclosure

Every vulnerability studied here is a **publicly disclosed, patched CVE** with public huntr / NVD references. Any novel findings from future work on live software will follow coordinated disclosure before publication.

## Repository

```
CLAUDE.md           project brief + foundational decisions
AEGIS_CONTEXT.md    full context, methodology, timeline
DECISION.md         running decision log (dated)
WORKFLOW.md         dual-Claude operating discipline
SESSION_HANDOFF.md  live resume point
notes/              domain study + design docs (Act I CVEs, Act II verifier design)
writeups/           portfolio writeups (Act II verifier results)
```

The retrieval scaffold, verifier, and documented benchmark-harness patches are added as Acts II–III progress.

---

*Methodology mirrors a prior project (Meridian): a deterministic retrieval-metric verifier calibrated against an external baseline, with the measurement layer — not the model — as the contribution. Same discipline, harder domain.*
