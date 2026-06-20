# FRONTIER.md — Aegis Verifier (patch-genuineness judgment)

Set: 2026-06-19
Scope: deterministic verification that a security patch GENUINELY closes a
vulnerability. Scoped to CWE classes with SOUND mechanizable oracles:
memory-safety (ASan/UBSan), path-traversal (property-oracle), SSRF/SQLi
(differential execution). **Logic bugs and authentication/authorization
bypasses are OUT OF SCOPE** — no mechanizable oracle exists; verification
degenerates to LLM-as-judge, which is a statistical classifier subject to
co-bounded-support impossibility (Scrivens, arXiv:2603.28650, Mar 2026).

`bar confidence: best-published` — even AIxCC and Big Sleep evaluate on
KNOWN bugs and verify by DEMONSTRATION, not proof. Completeness is
impossible for any verifier (overlapping safe/unsafe distributions;
reference-free verification hardness per RLVR literature — arXiv:2604.15149,
Apr 2026). The honest ceiling is: catch every bypass we can mechanize an
oracle for, abstain on everything else, and report the coverage boundary.

---

## Approach landscape — families of patch verifiers

| Family | How it works | Strength | Failure mode | Status |
|---|---|---|---|---|
| **Single-PoC re-run** | Replay the known exploit against the patched code. Pass = exploit no longer triggers. | Simple, fast, deterministic. | Catches only the EXACT exploit used. A patch that blocks the literal payload but not the root cause passes. Trivially gameable by blocklisting the PoC input. | **Median.** Most CI pipelines and CTF auto-graders use this. |
| **Fuzzer-as-verifier** | Fuzz the patched code with grammar + mutation. Any crash/escape = patch fails. | Covers inputs beyond the known PoC. Catches blocklist-style cheats. | Bounded by reachability — fuzzer may not reach the vulnerable path. Bounded by oracle — silent corruption without sanitizer = invisible. AFL hit "natural saturation" on SQLite after 150 CPU-hrs and missed the Big Sleep bug (Nov 2024). | **Industry-standard.** OSS-Fuzz uses this for regression verification (arXiv:2411.03346, Nov 2024). Aegis verifier is here. |
| **Held-out variant family** | Generate exploit VARIANTS (not mutations of the literal PoC but distinct triggering paths to the same root cause). Test patch against variants it has never seen. | Measures root-cause closure, not payload-specific closure. Disjoint L/V sets prevent overfitting. | Variant generation is manual or requires domain expertise. Generalization gap (A→B) is unreported unless you measure it. | **Industry-standard to frontier** depending on variant source. Aegis has disjoint L/V sets — industry-standard. |
| **Oracle-stratified + abstaining** | Select oracle per CWE class (ASan for heap-overflow, UBSan for integer UB, property-check for traversal). Abstain when no oracle can establish the baseline exploit. Weight confidence by oracle reliability. | Prevents false confidence on weak-oracle CWEs. No verdict is better than a wrong verdict. | Requires per-CWE calibration data. More engineering. | **Frontier.** AIxCC teams self-gated on no-PoV cases; the SoK documents the cost of not gating (Theori 44.4% accuracy vs Atlanta 91.27%). |
| **Independent-engine cross-validation** | Validate patch with a SEPARATE analysis engine (symbolic execution, different fuzzer, human-written variants, cross-team corpus). Report the A→B generalization gap. | Catches verifier-specific blind spots. If engine A and engine B agree, confidence is high. If they disagree, you know your coverage has a hole. | Expensive. Requires two independent verification stacks. | **Frontier.** AIxCC SoK lists "adversarial cross-CRS validation" as future work — not yet implemented in any published system. `verify` — no shipped anchor. |

**Frontier family:** oracle-stratified + abstaining, with independent-engine
cross-validation as the aspirational ceiling. No published system implements
full cross-engine validation today.

---

## Consequence map — which axes cost real units

| Axis | Consequence of median | Real units at risk | Verdict |
|---|---|---|---|
| **1. Verdict type** (binary vs abstaining) | False confidence on patches outside oracle coverage | Ship a "verified" patch that doesn't close the vuln | **Frontier** |
| **2. Oracle-quality stratification** | Single oracle misses entire CWE classes | Heap-overflow patch verified by property-check that can't see memory corruption | **Frontier** |
| **3. Held-out attacker** | Verifier overfits to known exploits | Patch passes verification, fails against novel exploit variant | **Frontier** |
| **4. Oracle investment vs fuzzer reachability** | Bug is present but invisible to both oracle and fuzzer | Silent false-negative: "verified clean" when bug is still live | **Frontier** |
| **5. Functionality/regression gating** | Patch deletes the feature to "fix" the bug | Shipped code breaks users; ~40% of auto-patches are semantically wrong (AIxCC SoK) | **Frontier** |
| **6. Variant distribution** | Exploit set covers one triggering path | Patch closes literal path, root cause remains | **Frontier** |

All six axes are consequence-dense. A failure on any one produces a
false-negative verdict (declaring a broken patch genuine) — the single
worst outcome for a verifier whose purpose is trust.

---

## Axis 1: Verdict type — binary → confidence-weighted → ABSTAINING

### Three tiers

**Median:** Binary pass/fail. Exploit triggers or doesn't. No uncertainty signal.
Most CI-based verifiers, CTF auto-graders, BountyBench task checkers.

**Industry-standard:** Confidence-weighted. Run n trials, report hit rate.
Threshold sweep for best F1. OSS-Fuzz regression testing uses crash/no-crash
counts. Aegis verifier does this for injection (n=10, genuine_threshold=0.3).

**Frontier:** Per-instance ABSTENTION. Before emitting a verdict, verify that
the oracle can establish the BASELINE exploit (i.e., the unpatched code IS
vulnerable under this oracle). If the baseline fails — oracle can't observe
the bug even without the patch — the instance is un-gradeable. Emit
`ABSTAIN`, not `GENUINE`.

**Why abstention matters:** Without baseline gating, a verifier that can't
reach the vulnerable path reports "no exploit found" = `GENUINE`. This is
a false negative masquerading as a clean bill of health. AIxCC teams
learned this empirically: Theori submitted no-PoV patches at 44.4%
accuracy; Atlanta, which gated on PoV confirmation, hit 91.27%.

### Verified anchors

- **AIxCC SoK (arXiv:2602.07666, Feb 2026), Section 6.2:** Three teams
  (TI, FB, LC) attempted no-PoV patches but self-gated with time delays
  (45min, 50% elapsed, 30min-before-deadline). Team Atlanta's PoV-gated
  approach achieved highest accuracy (91.27%). Not a competition rule —
  team-level self-regulation.
- **RLVR gaming (arXiv:2604.15149, Apr 2026):** RLVR-trained models
  enumerate instance-level labels that pass verifiers without capturing
  relational patterns — i.e., verifiers that don't abstain get gamed.
- **Scrivens (arXiv:2603.28650, Mar 2026):** Under overlapping safe/unsafe
  distributions, any classifier-based verification gate has TPR bounded by
  Hölder inequality with FPR. Sound verification gates (deterministic
  oracles) escape the impossibility — theoretical justification for
  deterministic verifiers over LLM-as-judge.

### Current Aegis state

Binary with threshold sweep (k=1..max). No baseline-establishment check.
No explicit abstention. If the fuzzer can't reach the vulnerable path,
the verifier reports `GENUINE` — a false negative.

### measure:

```bash
# After implementing abstention: count how many patches get ABSTAIN
# vs forced-GENUINE when baseline exploit fails
python -c "
from verifier.core import evaluate
# Run evaluation, count verdicts by type
results = evaluate(plugin)
abstain_count = sum(1 for v in results if v.verdict == 'ABSTAIN')
total = len(results)
print(f'Abstention rate: {abstain_count}/{total}')
# reference number: abstention rate > 0% on weak-oracle CWEs
"
```

`reference number:` abstention rate > 0% when oracle cannot establish
baseline (exact number depends on CWE mix; AIxCC: 46% of Java CPVs
were fuzzer-unreachable → should abstain on those).

---

## Axis 2: Oracle-quality stratification per CWE

### Three tiers

**Median:** One oracle for all vulnerability types. Property-check or
single sanitizer. Aegis currently: property-oracle for traversal,
nonce-presence for injection. No memory-safety instrumentation.

**Industry-standard:** ASan + UBSan combined. Covers heap/stack overflow
(ASan) and undefined behavior (UBSan). Still misses uninitialized reads
(MSan), data races (TSan). OSS-Fuzz compiles with ASan by default.
UBfuzz (arXiv:2401.04538, Jan 2024) found 31 false-negative bugs across
ASan/UBSan in GCC/LLVM — sanitizers themselves have bugs.

**Frontier:** Per-CWE oracle selection with documented coverage boundaries.

| CWE class | Best oracle | Reliability | Gap |
|---|---|---|---|
| Heap overflow (CWE-122) | ASan | High | Misses if alloc/free elided by optimizer |
| Stack overflow (CWE-121) | ASan | High | Same |
| Integer overflow (CWE-190) | UBSan | High for signed; unsigned wraps are defined behavior |  |
| Use-after-free (CWE-416) | ASan | High | Delayed free can escape shadow-memory window |
| Path traversal (CWE-22) | Property-oracle (resolve + prefix) | High | TOCTOU race on symlinks |
| SQLi (CWE-89) | Differential execution | Medium | Requires baseline DB state |
| SSRF (CWE-918) | Network-level differential | Medium | DNS rebinding can evade |
| Uninit memory (CWE-457) | MSan | High | Not combinable with ASan in same binary |

Report per-CWE oracle reliability alongside verdicts. Don't claim
"verified" on a CWE class where your oracle has known blind spots
without disclosing the gap.

### Verified anchors

- **AIxCC SoK, Section 7.3:** Parallel Fuzzing oracle reliability:
  C targets 75% (30/40 CPVs solvable), Java targets 17% (4/23).
  Disparity from "richer semantic constraints" in Java inputs and
  fuzzer-unfriendly timeouts/OOMs. **Exact numbers confirmed.**
- **UBfuzz (arXiv:2401.04538, Jan 2024):** 31 false-negative bugs
  in ASan/UBSan across GCC and LLVM. GCC ASan "forgets" to insert
  checks for specific memory accesses. 66% of sanitizer bug reports
  over 5 years were false positives; false negatives received far
  less attention.
- **Tech-ASan (arXiv:2506.05022, 2026):** Juliet Test Suite: ASan
  missed 56 memory safety violations in `wcscpy()`.

### Current Aegis state

Two plugins, each with a single oracle type. No per-CWE selection.
No ASan/UBSan (property-oracle only). Vulnerability-agnostic core is
a strength for extensibility but means no oracle-quality metadata is
attached to verdicts.

### measure:

```bash
# Per-CWE oracle reliability: for each CWE plugin, run baseline
# exploits against UNPATCHED code. Reliability = fraction where
# oracle detects the known-present vulnerability.
python -c "
# reference number: oracle reliability per CWE
# C memory-safety (ASan): >= 75% (AIxCC C baseline)
# Java (fuzzer): >= 17% (AIxCC Java baseline)
# Path traversal (property): >= 95% (Aegis current: ~100% on L set)
# Target: report the number, don't hide low-reliability CWEs
"
```

---

## Axis 3: Held-out attacker — independent engine

### Three tiers

**Median:** Same exploit used for verification as for discovery. No
generalization test. The patch might block the literal payload while
leaving the root cause open.

**Industry-standard:** Disjoint L/V exploit sets. L (labeling) set
establishes ground truth; V (verifier) set tests generalization to
unseen payloads of the same vulnerability class. Aegis does this:
L=12 exploits, V=5 exploits for traversal, disjoint. Fuzzer adds
~8000 inputs beyond both sets. This is solid.

**Frontier:** Independent verification engine. A SEPARATE analysis
tool (symbolic executor, different fuzzer family, human-written
variants, or cross-team corpus) validates the same patch. Report
the A→B generalization gap: what fraction of patches that pass
engine A also pass engine B? Disagreements reveal blind spots in
both engines.

### Verified anchors

- **AIxCC SoK, Section 7 (future directions):** "multi-CRS settings
  (collaborative analysis or adversarial formats where CRSs attack
  competitors' patches)" listed as **future work, not implemented.**
  No cross-team adversarial validation occurred in AIxCC. `verify` —
  claimed anchor (cross-team validation) is weaker than stated.
  The paper's post-hoc analysis used "cross-validation by at least
  two security experts" (paper authors), not competing CRSs.
- **Big Sleep (Project Zero, Nov 2024):** variant analysis methodology
  — agent given a seed commit and asked to find related issues. This
  is the attacker-side analog: generate held-out variants from a
  root-cause neighborhood, then test the patch against them.

### Current Aegis state

Disjoint L/V sets = industry-standard. Fuzzer extends V-set coverage
significantly (+45pp recall). No independent engine. The generalization
gap (fuzzer-found vs. hand-crafted variants) is implicitly measured by
the L/V split but not explicitly reported as a cross-engine metric.

---

## Axis 4: Oracle investment (detectability) vs fuzzer (reachability)

### The two knobs

A verifier has two independent failure modes:
1. **Oracle blindness** — the bug triggers but the oracle can't see it
   (no sanitizer, no assertion, silent corruption)
2. **Reachability failure** — the oracle would detect it but the fuzzer
   never generates an input that reaches the vulnerable path

These are INDEPENDENT. Improving fuzzer throughput doesn't help if the
oracle is blind. Adding ASan doesn't help if inputs never reach the
instrumented code.

### Three tiers

**Median:** One fuzzer, one oracle, hope both work. No measurement of
which knob is the bottleneck.

**Industry-standard:** ASan-instrumented binary + coverage-guided
fuzzer. OSS-Fuzz standard. Covers most memory-safety CWEs on C/C++.
Weak on Java/Python (no memory model to sanitize), weak on logic bugs.

**Frontier:** Explicit investment in BOTH knobs, measured independently.
Oracle investment: compile with ASan + UBSan + custom assertions for
the specific vulnerability class. Fuzzer investment: targeted harness
that reaches the vulnerable entry point (not generic whole-program
fuzzing). Report which knob was the bottleneck per instance.

### Verified anchors

- **Big Sleep (Project Zero, Nov 2024):** The SQLite
  `seriesBestIndex()` bug was a stack buffer underflow. It was
  observable ONLY because SQLite's debug build had:
  `assert(iCol>=0 && iCol<=2)` at line 706. Without this assertion,
  the bug was **silent memory corruption — no crash, no signal**.
  The assertion converted it to SIGABRT. Oracle investment (SQLite's
  own debug assertions) was the critical enabler. **Confirmed.**
- **150 CPU-hours fuzzing miss:** AFL ran 150 CPU-hours on SQLite
  without finding the bug. **Confirmed, with caveat:** the OSS-Fuzz
  harness did not compile the `generate_series` extension. The fuzzer
  was structurally unable to reach the vulnerable code. This is a
  reachability failure, not a fuzzer-quality failure. **Both knobs
  failed independently:** oracle was available (assertion existed) but
  fuzzer couldn't reach it.
- **Naptime (Project Zero, Jun 2024):** Programs compiled with ASan.
  "Perfect Verification" = reproducible crash as definitive oracle.
  Noted false-positive risk: `decode_char` assertion triggered by
  inputs that aren't real security bugs — oracle too broad.

### Current Aegis state

Traversal: property-oracle (high detectability for CWE-22), fuzzer
with 8000 inputs (decent reachability for string-level attacks).
No ASan/UBSan — not applicable to Python property checks but WILL be
needed for memory-safety CWEs in BountyBench (C/C++ targets).
The two-knob decomposition is not explicitly tracked.

---

## Axis 5: Functionality / regression gating (anti "delete-the-feature")

### Three tiers

**Median:** No functional check. If the exploit no longer triggers,
the patch passes. A patch that rejects ALL input — or deletes the
vulnerable function entirely — scores as genuine. This is the
single most common false-negative mode for automated patch verifiers.

**Industry-standard:** Run the project's existing test suite post-patch.
Build verification + functional tests + PoV non-reproduction. AIxCC
requires all three. Most APR (Automated Program Repair) systems do
this. But existing test suites are sparse — they don't cover the
specific functionality that the patch modifies.

**Frontier:** Weighted scoring with semantic review. Functionality
preservation weighted 3× vs vulnerability identification (AIxCC
scoring). Post-hoc semantic analysis catches patches that pass all
automated checks but are semantically wrong. Happy-path regression
tests specific to the patched functionality (not just the existing
test suite).

### Verified anchors

- **AIxCC SoK, Section 7.4:** "A significant fraction of generated
  patches pass all automatic validation, yet contain semantic issues
  caught only by manual review." Exact numbers: Claude Code 37.7%
  (20/53), MultiRetrieval 45.6% (26/57). **~40% figure confirmed**
  (applies to LLM-generated patches in the paper's auxiliary study,
  not the competing teams — team accuracy ranged 23.3% to 100%).
- **AIxCC scoring:** Patch [3,6] points vs PoV [1,2] points —
  approximately 3× weighting for patching over discovery. Accuracy
  multiplier: 90% accuracy = negligible penalty; 50% = 6% reduction;
  40% = 13% reduction. **Confirmed.**
- **"Why LLMs Fail" (arXiv:2603.10072, Mar 2026):** 319 patches
  across 64 Java vulnerabilities. Only 24.8% fully correct. 51.4%
  fail BOTH security and functionality. Mean functionality
  preservation 0.832, mean security fix 0.251.

### Current Aegis state

**No functionality check.** The verifier checks only whether exploits
escape. A traversal patch that rejects ALL paths (not just malicious
ones) passes as `GENUINE`. An injection patch that refuses to call
the LLM at all passes as `GENUINE`. This is the verifier's biggest
gap — explicitly documented in the codebase but not yet addressed.

### measure:

```bash
# Anti-regression: define happy-path inputs per plugin.
# A genuine patch must PASS happy-path AND BLOCK exploits.
# A delete-the-feature patch fails happy-path.
python -c "
# After implementing:
# happy_pass = fraction of genuine patches passing happy-path
# cheat_catch = fraction of delete-feature patches caught
# reference number: cheat_catch = 100% (all feature-deleting
#   patches must be caught)
# reference number: happy_pass >= 95% (genuine patches should
#   rarely break functionality)
"
```

---

## Axis 6: Variant distribution — root-cause neighborhood

### Three tiers

**Median:** Replay the original PoC. One exploit, one path. Patch
passes if it blocks that exact input.

**Industry-standard:** Enumerate a hand-crafted variant set covering
known attack classes (Aegis traversal: classes A–G with format
variations). Fuzzer extends coverage with grammar + mutation. This
tests payload diversity but not root-cause diversity — all variants
target the same entry point through the same code path.

**Frontier:** Root-cause seeded generation. Given the known bug, derive
the FAMILY of triggering conditions from the root cause (not the
payload surface). For a path-traversal bug caused by missing
canonicalization, the family includes: `../`, symlinks, Unicode
normalization bypasses, TOCTOU races, and absolute-path injection —
because ALL of these exploit the same root cause (path not resolved
before use). Test the patch against the full family, not just string
variations of `../`.

### Verified anchors

- **Big Sleep (Nov 2024):** Explicitly a variant analysis task. Agent
  given seed commit `[1976c3f7]` (a recently patched vulnerability)
  and asked to review nearby code for "related issues that might not
  have been fixed." Found a bug "only loosely related to the changes
  in the seed commit." This is root-cause neighborhood exploration,
  not literal-payload fuzzing. **Confirmed.**
- **CVE-2025-6965 (Big Sleep, Jul 2025):** Second Big Sleep finding
  (integer overflow → OOB read in SQLite). Found via same variant
  analysis methodology. GTIG identified threat actors staging
  exploitation; Big Sleep isolated the vulnerability first. **Confirms
  variant analysis as a repeatable methodology.**

### Current Aegis state

Traversal: 7 exploit classes (A–G) + fuzzer with 8000 mutations.
Coverage is payload-diverse but not root-cause-diverse. Documented
blind spots: null-byte injection, Unicode normalization, symlink
races, OS-specific resource forks. These are all members of the
same root-cause family (path not canonicalized) that the fuzzer's
vocabulary doesn't cover.

---

## Divergence log — current Aegis verifier vs frontier tiers

| # | Axis | Current state | Frontier requires | Gap severity | Consequence if not closed |
|---|---|---|---|---|---|
| 1 | Verdict type | Binary with threshold sweep; no abstention | Baseline-establishment check; `ABSTAIN` when oracle can't confirm vuln exists | **HIGH** | False `GENUINE` on unreachable paths — silent false negative |
| 2 | Oracle stratification | Property-oracle only; no ASan/UBSan | Per-CWE oracle selection; oracle reliability reported per verdict | **HIGH** for BountyBench (C/C++ memory-safety targets need ASan) | Entire CWE classes invisible to verifier |
| 3 | Held-out attacker | Disjoint L/V sets + fuzzer (industry-std) | Independent engine; cross-engine generalization gap reported | **MEDIUM** | Blind spots shared by L/V/fuzzer all from same vocabulary |
| 4 | Oracle + fuzzer decomposition | Implicitly present; not measured separately | Report which knob was bottleneck per instance | **MEDIUM** | Can't diagnose whether to invest in oracle or fuzzer |
| 5 | Functionality gating | **None** | Happy-path tests per plugin; delete-the-feature detection | **CRITICAL** | ~40% of auto-patches are semantically wrong and would pass |
| 6 | Variant distribution | Payload-diverse, not root-cause-diverse | Root-cause family enumeration; coverage of documented blind spots | **MEDIUM** | Null-byte, Unicode, symlink attacks bypass verifier |

**Priority order:** 5 (functionality) → 1 (abstention) → 2 (oracle
stratification) → 6 (variant coverage) → 3 (independent engine) →
4 (knob decomposition).

---

## Scope boundary — what this verifier CANNOT cover

**Out of scope (no mechanizable oracle):**

- **Logic bugs (CWE-840):** "admin can access other user's data" —
  requires understanding application semantics, not just crash/escape.
- **Authentication bypasses (CWE-287):** whether a patch correctly
  enforces auth depends on the application's intended access model.
- **Business logic (CWE-841):** "price set to $0" — no oracle without
  a specification.
- **Cryptographic weaknesses (CWE-327):** whether AES-128 is
  "sufficient" is a policy decision, not a mechanizable property.

These CWE classes require either a formal specification (rarely
available) or an LLM-as-judge (subject to co-bounded-support
impossibility). The verifier should emit `OUT_OF_SCOPE`, not a
confident verdict.

---

## Name collision: "Aegis"

**CONFIRMED — name is heavily used in security:**
- "AEGIS: Autonomous Exploit Generation and Intelligence System"
  (TechRxiv, Dec 2025) — SMT-solver exploit agent. **Direct scope
  overlap.**
- "The Aegis Protocol" (arXiv:2508.19267, Aug 2025) — AI agent
  security framework.
- "AEGIS: Shielding Vulnerable Smart Contracts" (AsiaCCS 2020) —
  smart contract runtime protection.
- AegisLLM, AegisAgent, Forrester Aegis Framework — all 2025.

The name is saturated. For publication, need clear differentiation or
a rename. This is a real problem for searchability and citation.

---

## Anchor verification summary

| Claim | Status | Source |
|---|---|---|
| arXiv 2602.07666 = AIxCC SoK | **CONFIRMED** | "SoK: DARPA's AI Cyber Challenge", Feb 2026, 21 authors |
| ~40% semantically wrong | **CONFIRMED** | CC: 37.7% (20/53), MR: 45.6% (26/57) — paper's auxiliary study, not competing teams |
| 75% C vs 17% Java fuzzer | **CONFIRMED** | Section 7.3, Parallel Fuzzing: 30/40 C, 4/23 Java |
| AIxCC cross-team patch validation | **WEAKER THAN CLAIMED** | Not implemented. Listed as future work. Post-hoc expert review only. |
| AIxCC No-PoV gating | **CONFIRMED as team self-regulation** | Not a competition rule. Three teams self-gated. Atlanta's gated approach: 91.27% accuracy. |
| AIxCC functionality weighting | **CONFIRMED** | Patch [3,6] pts vs PoV [1,2] pts. 3× weight. Accuracy multiplier documented. |
| Big Sleep assertion-made-it-observable | **CONFIRMED** | `assert(iCol>=0 && iCol<=2)` in seriesBestIndex(). SIGABRT. Silent corruption without it. |
| 150 CPU-hr fuzzer miss | **CONFIRMED with caveat** | AFL 150 CPU-hrs. BUT: OSS-Fuzz harness didn't compile `generate_series` extension. Reachability failure, not fuzzer-quality failure. |
| Big Sleep variant analysis | **CONFIRMED** | Seed commit `[1976c3f7]`, found "loosely related" bug. Repeated Jul 2025 (CVE-2025-6965). |
| "Aegis" name taken | **CONFIRMED** | ≥6 security tools/papers named Aegis, including direct-overlap exploit agent (Dec 2025). |
| "co-bounded support" terminology | **UNCONFIRMED as exact phrase** | Concept confirmed in Scrivens (arXiv:2603.28650). Paper uses "overlapping distributions", not "co-bounded support." |
| Naptime arXiv ID | **NONE EXISTS** | Blog post only (Project Zero, Jun 2024). No arXiv paper found. |
