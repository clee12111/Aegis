# Aegis — Project Context & Timeline

## What this is, in one sentence

A security agent that finds and exploits vulnerabilities in real codebases, backed by a
deterministic verifier that scores whether the result is real — and an evaluation framework
that runs frontier models as baselines to isolate the scaffold's contribution.

---

## How it relates to Meridian

Meridian asked: does the retrieval metric mean what you think it means? It built a
deterministic measurement layer rigorous enough to catch its own bugs, calibrated against
an external published baseline (ZeroEntropy), and isolated the retrieval scaffold's
contribution by holding the model constant.

Aegis applies the same discipline to a harder problem: security agents. Same methodology —
deterministic verifier, external baseline, scaffold delta as the contribution — different
domain. The through-line is: build the measurement layer first, trust the numbers it
produces, don't claim more than the delta shows.

---

## Key decisions

**Inference-time, not RL.**
Every current security agent (BountyBench agents, Claude Code, SWE-agent, EnIGMA) is
inference-time. The reasoning loop between actions is identical in both — the difference
is whether weights update between episodes. RL would require thousands of training runs
and significant compute. Inference-time is what the field benchmarks against, what
companies deploy, and what the published numbers describe. RL (if ever) is Act IV —
optional, after the core system is complete and validated.

**Offense-primary, defense-secondary.**
Offensive results (Detect, Exploit) are the market hook. A CISO immediately understands
"our agent found this vulnerability before an attacker did." Defensive results (Patch +
verifier integrity) are the depth and the moat. Both get reported. The verifier scores
both sides anyway — it checks whether an exploit actually works and whether a patch
actually closes the vector. Building for offense while instrumenting defense is the
strongest positioning.

**The verifier is the contribution, not the agent.**
The underlying models (Claude, GPT-4.1, Gemini) already exist and are very capable.
What doesn't exist is a rigorous, tamper-resistant measurement layer that tells you
whether an exploit is real or the agent got lucky, and whether a patch closes the
vulnerability or just passes the test suite. BountyBench's 90% Patch scores are
measured with simple pass/fail — nobody knows how many of those patches are gamed.
The verifier gap is the research contribution.

**Three-stage progression.**
1. Test on own systems (Meridian, Aether) — calibration, no domain ramp required
2. Test on benchmark (BountyBench, ZeroDayBench) — external comparability
3. Test on open-source repos — generalization, real-world demonstration

**Build then specialize.**
No CWE niche picked upfront. The system gets built end-to-end first; the domain shows
where it's weak; specialization follows from evidence.

---

## The benchmark landscape

### BountyBench (Stanford / NeurIPS 2025) — the primary external reference

The first framework covering both offense and defense. 25 real-world systems, 40 bug
bounties, 9 of the OWASP Top 10. Three task types mapping the full vulnerability
lifecycle:

- **Detect** — find an unknown zero-day with no hints (hardest)
- **Exploit** — exploit a given vulnerability (offense)
- **Patch** — patch a given vulnerability (defense)

**Published metrics (10 agents, 3 attempts each):**

| Agent | Detect | Exploit | Patch |
|---|---|---|---|
| Codex CLI o3-high | 12.5% | 47.5% | 90% |
| Codex CLI o4-mini | ~12% | 32.5% | 90% |
| Claude Code | ~8% | 57.5% | 87.5% |
| Custom: Claude 3.7 Sonnet Thinking | ~8% | **67.5%** | 60% |
| Custom: GPT-4.1 / Gemini / others | ~5% | 17.5–50% | 25–55% |

Key observations:
- CLI coding agents (Claude Code, Codex) dominate defense, weak on offense
- Custom agents are more balanced
- Detection tops out at 12.5% across all agents — genuinely unsolved
- Patch scores use naive pass/fail — nobody has verified whether patches are real

### ZeroDayBench (2026) — the defensive ceiling

22 novel critical vulnerabilities, anti-memorization design (CVEs ported into different
repos). Tested GPT-5.2, Claude Sonnet 4.5, Grok 4.1. Finding: frontier LLMs are not
yet capable of autonomously solving these tasks. This is the hard open problem on the
defensive side.

### CVE-Bench — offensive baseline

LLM agents can exploit up to 10% of web vulnerabilities under zero-day conditions,
12.5% one-day. Agents use an action-observation loop against sandboxed environments.

---

## Why detection is hard (the frontier problem)

Detection is structurally a retrieval problem — find the relevant code across files,
synthesize the vulnerability pattern, surface it without bloating context. But it's
harder than RAG in compounding ways:

**No explicit retrieval signal.** In RAG, a relevant chunk has semantic similarity to
the query. A vulnerable function looks normal — it IS normal, except for one missing
check or a dangerous interaction. Standard dense retrieval fails because safe code and
vulnerable code embed nearly identically.

**Multi-hop taint chains.** User input enters at function A, passes through B
incompletely sanitized, reaches function C, hits a sink. Each hop looks benign in
isolation. Holding the full chain in context across files, without losing earlier hops
as context grows, is where frontier models fail — they drop the thread around hop 3-4
in large codebases.

**Cross-language and cross-boundary chains.** Real vulnerabilities frequently span a
Python backend calling a C library, or a JS frontend interacting with a Rust API. Models
have no unified representation across language boundaries. This is a primary reason the
12.5% Detect ceiling exists.

**No ground truth query.** In RAG you know what you're looking for. In zero-day
detection the agent has to generate its own hypotheses, rank them, investigate each,
and abandon dead ends — with no signal telling it whether it's warm or cold.

**The retrieval edge.** Symbol-aware retrieval (call graphs, data flow graphs, import
relationships) over code can trace a taint flow across files deterministically. This is
BM25 + dense over a code graph — same principles as Meridian, harder schema. The
12.5% Detect ceiling is beatable through better retrieval, not a better model.

---

## How the baseline methodology works

Same pattern as Meridian vs. ZeroEntropy:

1. **Published baseline:** take the BountyBench numbers as-is — Claude Code (57.5%
   Exploit, 87.5% Patch, ~8% Detect). No need to reproduce; it's in the paper.

2. **Your system:** same underlying model via API, with the retrieval scaffold on top —
   code-graph-aware localization, taint-flow-aware chunking, multi-hop chain retrieval.
   Run against the same BountyBench tasks.

3. **The delta:** if your scaffold + Claude Sonnet hits 70% Exploit and 20% Detect,
   the scaffold beats the bare model on the same underlying intelligence. The claim is
   precise: same model, better retrieval and localization, here's the delta.

Claude Code and Codex CLI become your strongest baselines, not competitors. You're
isolating the contribution of the infrastructure around the model — the model is held
constant.

**Honest caveat:** BountyBench has 40 tasks — small enough that variance matters.
Run 3 attempts per task (the benchmark allows it), extend to ZeroDayBench or
CyberSecEval for breadth. Sub-noise deltas don't count. Same discipline as Meridian's
variance floor.

---

## Architecture

```
Vulnerable repo
      ↓
Retrieval layer
(call graph, taint flow,
 entry point detection,
 multi-hop chain ranking)
      ↓
Ranked suspicious paths
      ↓
Model API call
(Claude / GPT-4.1 / Gemini — swappable)
(reason over paths, generate exploit or patch)
      ↓
Deterministic verifier
(did the exploit actually work?
 did the patch close the vector the exploit used?
 or did it just pass the test suite?)
      ↓
Two-track evaluation
  ├── Capability: Detect / Exploit / Patch scores vs. BountyBench baseline
  └── Verifier integrity: precision/recall on labeled gold set
                          (genuine fixes vs. gamed solutions)
```

The model in the middle is swappable. Swap it out and re-run to show the scaffold
helps across model tiers, not just one. If the scaffold + a smaller model beats Claude
Code bare on detection, that's the headline result.

---

## What inference-time means vs. RL

Every current security agent is inference-time. The reasoning loop looks the same:

```
Inference:   run → reason → act → observe → reason → act → done
             (weights unchanged, context accumulates within the run)

RL:          run → reason → act → observe → reward  → weights update
             run → reason → act → observe → reward  → weights update
             ... × 10,000 episodes
```

The reasoning step between actions is identical. The difference is whether the model
that finishes episode 10,000 is different from the one that started episode 1. For
inference-time, it isn't. The agent gets smarter within a single run through context
accumulation, not through learning.

RL would make the verifier a training reward signal, shaping policy weights across
thousands of episodes. That's what nobody has published cleanly for defensive cyber —
and it's Act IV, optional, after the inference-time system is validated.

---

## Offense / defense transferability

Partially, but asymmetric:

**Shared skills (transfer well):** code reading, program flow understanding, localizing
the relevant section, reasoning about what the code does. A strong retrieval layer
helps both sides.

**Offense → Defense (partial transfer):** knowing how to exploit something doesn't
mean you know how to fix it safely without breaking functionality. BountyBench shows
this: custom agents optimized for offense hit 67.5% Exploit but only 25-60% Patch.

**Defense → Offense (less transfer):** patching is constrained and well-defined. Exploitation
requires adversarial creativity — finding non-obvious paths, chaining vulnerabilities,
thinking like an attacker. CLI coding agents are lopsided: 90% Patch, weak Exploit.

**Detection (transfers to neither):** finding an unknown vulnerability requires broad
pattern recognition across an entire codebase. Different from both deep exploitation
reasoning and constrained patch generation.

---

## Timeline

### Act I — Foundations (weeks 1–3)
**Goal:** learn the domain, set up the environment, no agent yet.

- Study CWE Top 25 — understand the vulnerability classes, how they manifest, what
  a real fix looks like vs. a superficial one
- Read BountyBench paper end to end; understand the Detect/Exploit/Patch task setup
- Set up a Kali Linux container (BountyBench runs agents in one)
- Pick 3–5 BountyBench systems to start with; read their codebases
- Read 5–10 CVEs in those systems; understand the exploit and the patch
- No code written yet — this is domain ramp

**Exit gate:** can explain, from memory, how 3 real vulnerabilities work and what a
genuine patch requires.

### Act II — Self-test seam (weeks 4–7)
**Goal:** attack your own systems (Meridian, Aether), build the verifier on known code.

- Write exploit tests for Meridian and Aether — indirect injection vectors, privilege
  issues, prompt manipulation
- Build a simple verifier: given a claimed exploit, does it actually produce the
  expected behavior? Given a claimed patch, does the exploit still work?
- Run Claude and GPT-4.1 bare against your own systems; record what they find and miss
- Add the retrieval layer (code-graph-aware, function-boundary chunking) and re-run
- Measure the delta: does the scaffold find more than the bare model?

**Exit gate:** verifier has a number — precision/recall on a small labeled set of real
vs. gamed patches on your own code. Scaffold shows measurable delta vs. bare model.

**Why start here:** you know these codebases cold. You'll know immediately if an
"exploit" is real or theater. This is verifier calibration before running on unfamiliar
repos. Requires zero new domain knowledge — just your existing systems.

### Act III — Benchmark evaluation (weeks 8–14)
**Goal:** run on BountyBench, report Detect/Exploit/Patch vs. published baselines.

- Extend retrieval layer to unfamiliar repos: call graph construction, taint flow
  tracing, entry point detection across unknown codebases
- Run Claude Code bare against BountyBench → record baseline numbers
- Run your scaffold + Claude Sonnet against the same tasks → record your numbers
- Swap models (GPT-4.1, Gemini) to show scaffold helps across tiers
- Run verifier integrity evaluation: labeled gold set of genuine fixes vs. gamed ones,
  score as classifier
- Extend to ZeroDayBench for defensive depth (the truly novel vulnerability setting)

**Exit gate:** published-comparable Detect/Exploit/Patch numbers on BountyBench that
beat Claude Code bare on at least one metric. Verifier integrity has precision/recall
numbers on a labeled gold set.

**This is the capstone.** A complete inference-time security agent with a rigorous
verifier, benchmarked against the field.

### Act IV — Generalization (weeks 15+, optional)
- Run on arbitrary open-source Python repos with known CVEs
- Demonstrate the agent localizes without knowing the codebase upfront
- RL training loop (if ever): verifier becomes the reward signal, run RLVR episodes,
  measure whether reward hacking rises and verifier catches it

---

## Planned stack

```
Python
Docker / Kali Linux container (BountyBench-compatible sandboxing)
pytest-style harness (exploit and patch verification)
CodeQL / Semgrep (static analysis signal for retrieval layer)
Tree-sitter (AST parsing, function-boundary chunking)
NetworkX (call graph construction)
Anthropic / OpenAI / Google APIs (swappable model tier)
BountyBench (primary benchmark)
ZeroDayBench (defensive ceiling benchmark)
CyberSecEval (breadth)
PyRIT / Garak (attack tooling, Act II self-test)
```

---

## What this is not

- Not a general coding agent competing with Devin, Cursor, or GitHub Copilot Workspace
- Not an RL training project (Act I–III are entirely inference-time)
- Not a jailbreak agent (jailbreaking bypasses model safety guardrails; this is
  vulnerability research on real codebases)
- Not a pen testing firm replacement (the agent is a research system; the verifier
  is the novel contribution, not the agent's raw capability)
- Not benchmark-chasing — numbers are reported conservatively against the same
  pass/fail methodology BountyBench uses, with verifier integrity as the honest layer
  on top

---

## Open questions (as of project start)

- Which BountyBench systems to target first (language, complexity, vulnerability class)
- Whether Tree-sitter + NetworkX call graph construction is sufficient for taint
  tracing or whether CodeQL is needed from the start
- How large a labeled gold set is needed for verifier integrity to be a meaningful
  classifier score (target: 50+ genuine/gamed pairs minimum)
- Whether the retrieval delta is measurable on Detect specifically, or only on Exploit
  (Detect at 12.5% may require more architectural work than a single scaffold pass)
