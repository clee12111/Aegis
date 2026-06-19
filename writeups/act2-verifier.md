# Building a verifier you can trust — Aegis, Act II

> A deterministic verifier that judges whether a security agent's patch is *real* — and measures
> its own reliability, including where it fails.

## The problem

Security-agent benchmarks score exploits and patches with simple pass/fail: did a test go green,
did the known exploit stop working. Nobody checks whether a "fix" actually *closed* the
vulnerability or just learned to defeat the one test it was shown. And as the agent being judged
gets stronger, a static pass/fail check gets gamed. **The measurement layer — not the model — is
the weak point.** Aegis Act II builds that layer: a verifier that judges whether a patch is real,
and — crucially — quantifies its *own* reliability.

## "Verify the verifier"

I built a gold set of patches on my own systems, where I know ground truth: some **genuine** fixes,
some **gamed** (blocklist the known exploit, fix one site but not its sibling, partial defenses).
The verifier's job is to sort them; its **precision and recall on that gold set is its reliability
number** — the thing the field doesn't measure. This is *mutation testing applied to a security
oracle*: inject known-flawed patches and measure how many the verifier kills.

## How the verifier evolved — each step forced by a *measured* failure

1. **Single held-out exploit.** Judge a patch with a *different* exploit of the same vuln than the
   one it was shown — catches "blocked the known attack but didn't fix the bug." → Gameable: a patch
   that blocklists the held-out exploit's specific tokens passes.
2. **A diverse held-out family.** Many varied exploits; no single token-blocklist survives ten
   payloads. → Caught the cheats the single exploit missed.
3. **Effectiveness labels, not code review.** A patch's label is set by whether it *actually* blocks
   attacks, not by whether its code *looks* like a defense. (Several defense-shaped patches turned
   out ineffective; the labels were too generous.)
4. **Property oracle + fuzzing, not enumeration.** Enumerating attack classes is a blocklist — it
   bloats and is blind to novel attacks. Instead: check an **invariant** ("does the resolved path
   stay inside the allowed folder?") and **generate** thousands of inputs by fuzzing. This catches
   bypasses it was never shown — including ones no human listed.

## Key results

- **Transferable by construction.** One vuln-agnostic core ran a *probabilistic* LLM prompt-injection
  vuln and a *deterministic* file-path-traversal vuln with **zero core changes**. Vuln-specific
  knowledge enters only as a plugin (exploits + a success-property), never as verifier logic — so it
  generalizes instead of overfitting per bug.
- **Property + fuzzing generalizes to unseen attacks.** The fuzzer recovered *every* cheat an
  enumerated test missed, by composing attacks from primitives — without those attacks being
  hand-listed. The blind spot moved from "an attack class I forgot to list" (grows forever) to "a
  primitive not in the fuzzer's vocabulary" (small, stable).
- **The verifier out-thoroughs its own ground truth.** Across two operating systems, *every time* the
  fuzzer disagreed with my hand-crafted answer key, the fuzzer was right — it found **3 real bugs the
  labels missed**. Even the ground truth is approximate; for deterministic vulns, the property+fuzzing
  engine is the most reliable ground truth available.
- **The environment is part of the vulnerability.** The same patch is a genuine fix on Linux and a
  broken one on Windows (forward-slash-only defenses). "Is this patch real?" has no answer without
  fixing the deployment OS — a **defense-portability** bug class the verifier's OS-native check
  surfaces automatically.

## Honest limits — the point, not a footnote

A verifier is never absolute ground truth; it's a *characterized approximation*, and the contribution
is knowing **where it breaks, with numbers**. I measured it: recall is bounded by the diversity of the
attack set (a recall-vs-coverage curve), and the residual blind spot is the fuzzer's input vocabulary
(named: null-byte, unicode normalization, encoding mismatches, symlink races…). As the agent scales,
those blind spots *are* the reward-hacking attack surface — so the verifier must **co-evolve**, prefer
**executable/deterministic** checks, and **abstain** (flag low confidence) on inputs outside its tested
coverage rather than emit a verdict it can't back.

## Grounding

The approach combines established gold standards — **mutation testing** (measuring an oracle by injected
faults), **property/metamorphic testing** (check an invariant, not a pattern), and **verifiable rewards**
(RLVR; executable checks resist reward-hacking) — and points them at security-agent verification, where
current benchmarks still use naive pass/fail.

---

*Methodology mirrors a prior project (Meridian): build the measurement layer first, trust the numbers it
produces, and don't claim more than the delta — and the limits — show.*
