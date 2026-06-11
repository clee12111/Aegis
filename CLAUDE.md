# CLAUDE.md — Aegis

The whole project, condensed. Read this first, every session.
For full context and timeline see AEGIS_CONTEXT.md.

---

## What Aegis is

A security agent that finds and exploits vulnerabilities in real codebases, backed
by a deterministic verifier that scores whether the result is real — not just
whether a test passed.

The verifier is the contribution. The underlying models (Claude, GPT-4.1, Gemini)
are called via API and treated as baselines. The scaffold around them — code-graph-
aware retrieval, taint-flow tracing, multi-hop chain ranking — is what gets measured.

**Not** a general coding agent. **Not** an RL training project (inference-time
throughout Acts I–III). **Not** a jailbreak agent. **Not** a pen testing firm
replacement.

---

## How it relates to Meridian

Same methodology, different domain:

- Meridian: retrieval scaffold + deterministic span-overlap verifier, calibrated
  against ZeroEntropy baseline, scaffold delta is the contribution
- Aegis: security scaffold + deterministic exploit/patch verifier, calibrated
  against BountyBench published baselines, scaffold delta is the contribution

The measurement discipline is identical. Build the verifier first. Trust the numbers
it produces. Don't claim more than the delta shows.

---

## Current phase

**Act I — Foundations.** Domain ramp, environment setup, no agent built yet.

See AEGIS_CONTEXT.md for the full timeline and exit gates.
See **SESSION_HANDOFF.md** for the live resume point (current CVE trio, env state,
immediate next actions) — read it at the start of each session until Act I closes.

---

## Architecture

```
Vulnerable repo
      ↓
Retrieval layer                  ← the scaffold (your contribution)
(call graph, taint flow,
 entry point detection,
 multi-hop chain ranking)
      ↓
Ranked suspicious paths
      ↓
Model API call                   ← commodity, swappable
(Claude / GPT-4.1 / Gemini)
      ↓
Deterministic verifier           ← the contribution
(exploit: did it actually work?
 patch: does the exploit still work after?)
      ↓
Two-track evaluation
  ├── Capability: Detect / Exploit / Patch vs. BountyBench baseline
  └── Verifier integrity: precision/recall on labeled gold set
```

---

## Three-stage progression

1. **Own systems** (Act II) — attack Meridian and Aether, build and calibrate
   the verifier on code you know cold
2. **Benchmark** (Act III) — BountyBench + ZeroDayBench, report against published
   baselines, this is the capstone
3. **Open-source repos** (Act IV+) — generalization to unfamiliar codebases,
   RL training loop optional here

---

## Baseline methodology

Same pattern as Meridian vs. ZeroEntropy:

- **Published baseline:** BountyBench numbers for Claude Code bare:
  ~8% Detect, 57.5% Exploit, 87.5% Patch. Don't need to reproduce — it's in the paper.
- **Your system:** same model via API + retrieval scaffold. Run same tasks.
- **The claim:** same model, better localization scaffold, here's the delta.

Model is held constant. Scaffold delta is the isolated contribution.

---

## Benchmark reference numbers

BountyBench (NeurIPS 2025), 10 agents, 3 attempts, 40 tasks:

| Agent | Detect | Exploit | Patch |
|---|---|---|---|
| Codex CLI o3-high | 12.5% | 47.5% | 90% |
| Codex CLI o4-mini | ~12% | 32.5% | 90% |
| Claude Code | ~8% | 57.5% | 87.5% |
| Custom Claude 3.7 Thinking | ~8% | 67.5% | 60% |
| Custom others | ~5% | 17.5–50% | 25–55% |

ZeroDayBench (2026): frontier models not yet capable of autonomously solving
22 novel critical vulnerabilities. Detection is the hardest open problem.

---

## Hard rules

1. **Verifier observes; it does not steer agent control flow.** The verifier scores
   results — it does not tell the agent what to do next. Coupling agent behavior to
   verifier output makes a measurement bug indistinguishable from a behavior bug.
   Same rule as Meridian's measurement layer.

2. **Verify before trusting any result.** A passing test suite is not proof a patch
   is real. An exploit claim is not proof the vulnerability was triggered. Always
   run the verifier; always check the raw behavior before concluding the system worked.

3. **Model is swappable; scaffold is not.** Every LLM call goes through a provider-
   agnostic interface. No hardcoded model strings in agent logic. The scaffold must
   work with any model tier — that's how you show the scaffold is the contribution,
   not the model.

4. **Offense-primary, defense-secondary.** The agent's primary task is exploitation.
   Patching is the secondary task. Both get verifier coverage. Both get reported
   against BountyBench. Don't let the defensive framing bleed into the agent's
   primary objective.

5. **No fabricated results.** Sub-noise deltas don't count. BountyBench has 40 tasks —
   run 3 attempts per task, report the average. If the delta is within variance, it
   doesn't go in the headline. Same discipline as Meridian's 0.50pp R@8 variance floor.

6. **Verifier integrity must have a number.** "My verifier catches reward hacking" is
   not a claim without precision/recall on a labeled gold set of genuine fixes vs.
   gamed ones. Build the gold set in Act II on your own systems. Extend it in Act III.

7. **Act I is domain ramp, not code.** No agent architecture built during Act I. The
   exit gate is understanding 3 real CVEs cold — how the vulnerability manifests, how
   the exploit works, what a genuine patch requires. Don't skip this.

---

## Inference vs. RL

Every current security agent (BountyBench agents, Claude Code, SWE-agent, EnIGMA)
is inference-time. Weights are frozen. The reasoning loop accumulates context within
a single run; nothing is learned between runs.

```
Inference:  run → reason → act → observe → reason → act → done
            (weights unchanged, context grows within the run)

RL:         run → reason → act → observe → reward → weights update
            ... × 10,000 episodes
            (model changes between runs)
```

Acts I–III are entirely inference-time. RL is Act IV — optional, after the
inference system is validated and benchmarked. Do not architect for RL during Acts I–III.

---

## Why detection is hard

Detection is a retrieval problem, but harder than RAG:

- **No retrieval signal.** Vulnerable code looks like normal code. Dense retrieval
  fails — safe and vulnerable functions embed nearly identically.
- **Multi-hop taint chains.** The vulnerability spans files: input → A → B → sink.
  Each hop is benign alone. Models drop the thread at hop 3–4 in large codebases.
- **No ground truth query.** In RAG you know what you're looking for. In zero-day
  detection the agent generates its own hypotheses without a warm/cold signal.
- **Cross-language boundaries.** Real vulnerabilities cross Python/C, JS/Rust.
  No unified representation across language boundaries for current models.

The retrieval edge: a code-graph-aware scaffold (call graph, taint flow, entry
point detection) pre-computes the multi-hop chain deterministically and hands the
model a ranked list of suspicious paths instead of raw code. Same insight as
Meridian's document routing — don't make the model do retrieval inside its context
window; do it upstream and hand it only what it needs.

---

## Available controls (engineer reference)

To be populated during Act II as the system is built. Placeholder structure:

```
AEGIS_MODEL          — model provider + name (default: claude-sonnet-4-6)
AEGIS_TARGET         — repo path or BountyBench system identifier
AEGIS_TASK           — detect | exploit | patch
AEGIS_VERIFIER_MODE  — strict | permissive (strict requires held-out exploit variant)
AEGIS_MAX_STEPS      — max agent iterations per task (default: TBD)
AEGIS_ATTEMPTS       — attempts per task for variance (default: 3, matches BountyBench)
```

---

## Stack

```
Python
Docker / Kali Linux container (BountyBench-compatible sandboxing)
pytest-style harness (exploit and patch verification)
Tree-sitter (AST parsing, function-boundary chunking)
NetworkX (call graph construction)
CodeQL / Semgrep (static analysis signal, Act III+)
Anthropic / OpenAI / Google APIs (provider-swappable)
BountyBench (primary benchmark, github.com/bountybench/bountybench)
ZeroDayBench (defensive ceiling)
CyberSecEval (breadth)
PyRIT / Garak (attack tooling, Act II self-test)
```

---

## Dual-Claude workflow

Same as Meridian. Two roles, same rules:

- **Claude.ai (advisor)** — interprets results, frames research questions, makes
  architectural calls. Has project context, NOT the live repo. Writes prompts for
  the engineer.
- **Claude Code (engineer)** — reads, writes, runs against the real repo. Has live
  ground truth, lacks accumulated project framing. Needs WHY inline on every
  non-trivial prompt.

Two failure modes to actively counter:
- **Engineer context starvation** — every non-trivial prompt carries the WHY
  (constraint / finding / gate) inline, not just the task.
- **Advisor stale assumptions** — recon round before any invasive build. Engineer
  reads and reports; advisor builds the next prompt against the report, not the docs.

### Execution environment (Cowork advisor)

When the advisor runs inside Cowork it is no longer repo-blind — it has direct
read/write access to the real files and an isolated Linux sandbox. The capability
boundary:

- **Advisor sandbox can:** read/write any file in the repo, run plain Python 3.10
  and git, parse results, inspect `bountytasks`, write scaffolding and docs.
- **Advisor sandbox cannot:** run Docker. BountyBench executes tasks inside
  Docker/Kali containers (`dockerize_run.sh`, `docker-compose.yml`), so all
  containerized harness runs stay with Claude Code in the real WSL2+Docker env.
- **Sync is the shared disk, not git.** The top-level `Aegis/` folder is not a git
  repo — advisor and engineer edit the same files on disk; changes are seen
  immediately by both. (`bountybench/` is its own git repo.)

Net: the advisor can now do recon and lightweight edits/runs itself; the engineer
still owns Docker, the full harness, and anything needing the real environment.

---

## Foundational decisions

The permanent architectural calls that define the project. These are stable — they
rarely change once set. The running, dated decision log (Act-level and tactical
decisions, appended as work progresses) lives in **DECISION.md** — check it for the
current state of play.

### 2026-06 — Inference-time, not RL for Acts I–III

**Decision:** Build an inference-time security agent evaluated against BountyBench.
RL training loop deferred to Act IV (optional).

**Why:** Every published benchmark agent is inference-time. The field measures
against inference baselines. RL requires thousands of episodes and significant
compute before useful signal emerges. The verifier — the novel contribution —
scores inference-time results just as rigorously as RL rewards.

**Precludes:** Architecting for RL during Acts I–III. Any design that assumes weight
updates between runs. Framing the project as an "RL environment" before Act IV.

---

### 2026-06 — Offense-primary, defense-secondary

**Decision:** The agent's primary task is exploitation (Detect + Exploit).
Patching (Patch) is the secondary task. Both are measured. Both are reported.

**Why:** Offensive results are the market hook. Detection and exploitation are
immediately legible to security teams and hiring managers. Defensive patching requires
domain knowledge to appreciate. The verifier covers both sides regardless — it checks
whether exploits are real and whether patches close the actual vector.

**Precludes:** Building a pure defensive patch agent. Reporting only Patch scores.
Optimizing the scaffold exclusively for Patch at the cost of Detect/Exploit.

---

### 2026-06 — Verifier is the contribution, not the agent

**Decision:** The underlying model is treated as a commodity baseline. The retrieval
scaffold and deterministic verifier are the isolated contribution.

**Why:** Frontier models are already capable. BountyBench's 90% Patch scores exist
without a verifier checking whether patches are real. The gap is measurement rigor,
not model capability. Same finding as Meridian: the measurement layer is what's
defensible and transferable.

**Precludes:** Claiming the agent's raw capability is the contribution. Competing
with Claude Code or Codex CLI on general coding tasks. Framing results without
holding the model constant.