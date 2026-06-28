# VERIFIER.md — Aegis Verifier Pillar

The verifier pillar, synthesized for a reader. Companion to INFRA.md (Part III) and
AGENT.md (Part II). Throughline, shared across all three pillars: **don't trust a
result — verify it deterministically, and don't claim more than the delta, and the
limits, show.** Consolidated from the act2/act3 writeups and the fuzz report; the
running trail is in DECISION.md.

---

## The problem

Security-agent benchmarks score exploits and patches with naive pass/fail: did a test
go green, did the known exploit stop working. Nobody checks whether a "fix" actually
*closed* the vulnerability or merely learned to defeat the one test it was shown. And
as the agent being judged gets stronger, a static pass/fail check gets gamed. **The
measurement layer — not the model — is the weak point.** This pillar builds that layer:
a deterministic verifier that judges whether a patch is *real*, and — crucially —
quantifies its own reliability, including where it fails.

---

## "Verify the verifier"

The reliability number the field doesn't report comes from a gold set built on systems
where ground truth is known: some **genuine** fixes, some **gamed** (blocklist the
known exploit, fix one site but not its sibling, partial defenses). The verifier's job
is to sort them, and its **precision/recall on that gold set is its reliability
number.** This is *mutation testing applied to a security oracle* — inject known-flawed
patches, measure how many the verifier kills.

The verifier evolved in four steps, each forced by a *measured* failure, not a guess:

1. **Single held-out exploit** — judge a patch with a *different* exploit of the same
   vuln than the one it was shown. Catches "blocked the known attack, didn't fix the
   bug." Gameable: a patch that blocklists the held-out exploit's tokens passes.
2. **A diverse held-out family** — many varied exploits; no single token-blocklist
   survives ten payloads.
3. **Effectiveness labels, not code review** — a patch's label is set by whether it
   *actually* blocks attacks, not by whether its code *looks* like a defense (several
   defense-shaped patches were ineffective; the labels were too generous).
4. **Property oracle + fuzzing, not enumeration** — enumerating attack classes is a
   blocklist that bloats and is blind to novel attacks. Instead, check an **invariant**
   ("does the resolved path stay inside the allowed folder?") and **generate** thousands
   of inputs by fuzzing. This catches bypasses it was never shown.

---

## Transferable by construction

A vulnerability-agnostic **core** scores patches, abstains when it can't judge, and
reports its own coverage. A vulnerability enters only as a **plugin** supplying four
things: a behavioral oracle (did the attack actually succeed?), a battery of exploits,
a registry of candidate patches, and a class taxonomy. Vuln-specific knowledge lives
in the plugin; verifier *logic* never does — which is what makes it generalize instead
of overfitting per bug.

That separation was proven, not asserted, across **four vulnerability types with an
empty core diff** (`git diff core.py` empty each time):

- **Synthetic path traversal** — oracle: path containment.
- **Synthetic command injection** — oracle: a benign injected sentinel actually
  executes. Completely different mechanism, same scoring/abstention/coverage core.
- **MLflow CVE-2024-1558 (real, Dockerized)** — HTTP exploit against a live server,
  patch applied into a running container, flag read via `docker exec`.
- **LibreChat CVE-2024-11170 (real, shipped fix)** — a second real CVE as independent
  ground truth.

Transfer is a property of the architecture, including across the synthetic→real jump.

---

## Calibrated abstention — honest deferral, proven

The verifier does not always answer. Before blessing a patch as genuine, it checks
whether its own attack suite actually covers the vuln's known attack classes; if not,
it returns **ABSTAIN with a reason** rather than a confident-but-hollow "genuine."
Abstention is gated on an objective coverage check, never a tunable confidence knob (a
knob would let it dodge hard cases to flatter its own accuracy).

This is honest deferral, not error-hiding, and that was demonstrated: on path traversal
the verifier abstained on patches it couldn't yet judge, and when the missing attack
coverage was added, *every* deferred patch resolved to the correct verdict, zero false
positives or negatives. On the real MLflow CVE it initially **abstained on the official
patch** — its held-out set covered a traversal variant but not the actual `%23`
fragment-anchor mechanism — flagging that *our own test set was inadequate to judge it*
rather than rubber-stamping. Adding one held-out exploit in the real attack class
resolved it to genuine, abstention to zero.

---

## Key results

- **Property + fuzzing beats enumeration, with a number.** Against a gamed set where
  bypass classes were hidden from the enumerated suite, the hand-listed verifier scored
  **55% recall (11/20)**; the fuzzing verifier (7,947 generated inputs, ~0.06s to
  generate) recovered **100% (20/20)** — **+45pp** — by composing bypasses from
  primitives it was never told existed (the backslash bypass emerges at input #7 from
  the separator vocabulary; absolute-path and reconstruction attacks from grammar
  composition). The blind spot moved from "an attack class I forgot to list" (grows
  forever) to "a primitive not in the fuzzer's vocabulary" (small, stable, *named*).
- **It out-thoroughs its own ground truth.** Every time the fuzzer disagreed with the
  hand-crafted answer key, the fuzzer was right — it found **3 real bugs the labels
  missed.** For deterministic vulns, the property+fuzzing engine is the most reliable
  ground truth available.
- **The environment is part of the vulnerability.** The same patch is genuine on Linux
  and broken on Windows (forward-slash-only defenses; a root-relative `\tmp\esc` is not
  "absolute" on Windows). "Is this patch real?" has no answer without the deployment OS
  — a defense-portability bug class the OS-native check surfaces automatically.
- **It catches the textbook fixes.** `normpath` (the canonical traversal fix) falls to
  a symlink whose filename is innocent; `shlex.quote` and `subprocess` list-form (the
  textbook command-injection fixes) pass `--output=/etc/cron.d/evil` straight through as
  a *flag* — quoting a flag doesn't stop it being a flag. Each is a defense correct
  against the obvious shape of an attack, blind to a sibling shape a pass/fail benchmark
  never tests.
- **It catches a real, test-passing fix.** On MLflow, `x_partial_decode` (URL-decode,
  then reject `..`) is a fix a competent engineer would write and a reviewer would
  accept — it passes **all 148 of MLflow's functional tests** — yet is still exploitable
  (`urlparse()` strips the `#`-fragment, so a `%23`-hidden traversal is invisible). The
  verifier rejects it because it checks behavior, not the test result. Across four MLflow
  patches: precision/recall/F1 100%, zero abstention.
- **Independent ground truth — a real shipped fix, caught.** LibreChat's maintainer
  patch for a delete-endpoint traversal CVE is a genuine improvement that passes the
  functional tests, yet the verifier labels it **GAMED** — the held-out upload exploit
  still fires, and a *separately disclosed CVE on the sibling endpoint* is the
  independent proof it was incomplete. Stable across N=3 (P/R/F1 100%), on a sound
  oracle (per-run UUID sentinel watched via a kernel filesystem event, watch established
  before the exploit fires).

---

## Honest limits — the contribution is knowing them

The clean precision/recall numbers (100% within each family) are measured against
**synthetic, hand-authored gold sets** and small patch counts — these are validations
that the machinery judges correctly, not statistical measurements. The MLflow gamed
patches are self-authored (expert-plausible, but ours); the LibreChat result exists
specifically to remove that objection with a real maintainer-shipped incomplete fix.
Narrower residuals, on the record: the argument-injection oracle is currently a
string-property proxy rather than truly behavioral; the sanitizer model can't yet
represent fixes that change the *call pattern* (e.g. switching to a no-shell API);
MLflow-scale mutation fuzzing (~8k inputs) is impractical against a live HTTP oracle
(a throughput tradeoff of live-target verification, not a missing capability); and the
oracle confirms a traversal *created a file*, not its contents. The fuzzer's residual
blind spot is its primitive vocabulary, named explicitly: null-byte injection, Unicode
normalization (NFKC), encoding mismatches, symlink/junction races, resource-fork paths.

The bar itself is thin: no published system does exploit-based patch verification with
measured precision and calibrated abstention, so "at bar" means the bar this work
defines. The point was never a verifier that is always right — it is a verifier whose
reliability, and whose blind spots, come with numbers.

---

## Grounding

Combines established gold standards — **mutation testing** (measuring an oracle by
injected faults), **property/metamorphic testing** (check an invariant, not a pattern),
and **verifiable rewards** (RLVR; executable, deterministic checks resist
reward-hacking) — and points them at security-agent verification, where current
benchmarks still use naive pass/fail. The same deterministic-verification ethos runs
through the harness (INFRA.md) and the scaffold measurement (AGENT.md).
