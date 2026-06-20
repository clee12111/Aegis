# OSS Security-Verification Landscape — where Aegis sits

*Source-verified survey, 2026-06-19. Purpose: model what an open-source "frontier"
security-verification system looks like, position Aegis's verifier against it, and
choose a second vulnerability class to prove transferability.*

---

## 1. The reference architecture is commoditized and public

All seven AIxCC (DARPA) finalist Cyber Reasoning Systems were open-sourced. They
converge on one shape:

1. **Ensemble bug discovery** — fuzzing (libFuzzer/AFL on OSS-Fuzz harnesses) +
   LLM-driven seed/input generation + sometimes symbolic/static analysis, in parallel.
2. **PoV (Proof-of-Vulnerability) as the discovery oracle** — a bug counts only when
   an input triggers an observable crash / sanitizer abort (ASan/MSan/UBSan/Jazzer).
   Dynamic, deterministic.
3. **Multi-agent patcher** — several repair strategies propose candidate patches.
4. **Patch acceptance gate** — a patch is accepted iff **(a) the original PoV no longer
   triggers** AND **(b) the project's functional test suite still passes.**

**The universal verification primitive is "PoV re-run + functional tests pass."**
Deterministic and real — but shallow. It answers "does this one crashing input stop
crashing without obviously breaking the build," not "is the vulnerability class
genuinely closed."

Takeaway: do **not** compete with the CRSs on capability — that race is over and held
by Atlantis / Buttercup / RoboDuck. Compete on the verification layer.

## 2. The gap — what nobody in OSS does

| Verifier capability | Any OSS system? | Evidence |
|---|---|---|
| PoV re-run after patch | Yes — universal | all AIxCC CRSs, BountyBench, ARVO, VulnRepairEval |
| Functional / regression gating | Yes — common | AIxCC CRSs, AutoPatchBench |
| Held-out exploit variants + fuzzing the patch | Partial / rare | AutoPatchBench does white-box differential testing; no OSS *agent* fuzzes its own patch with held-out variants |
| **Per-instance ABSTENTION on objective coverage checks** | **No — unoccupied** | no surveyed system emits a calibrated "un-gradeable" |
| **Verifier's own precision/recall on a labeled gold set** | **No — unoccupied** | nobody checks the checker |
| **Coverage-aware / oracle-stratified grading** | **No — unoccupied** | — |

**The field just independently validated Aegis's thesis (March 2026):**
**PVBench** (arXiv 2603.06858) built a 209-case validator benchmark and found **>40%
of patches validated as "correct" by basic tests (functional + PoC) FAIL under deeper
`PoC+` tests** — quote: *"none of the recent AVR systems verify that the auto-generated
patches additionally pass these new tests."* **VulnRepairEval** (arXiv 2509.03331)
makes the same accusation: *"existing datasets predominantly rely on superficial
validation methods... leading to overestimated performance."*

Both diagnose the problem; both "fix" it with **more ground-truth tests** — not with
abstention, coverage-stratification, or a verifier whose own error rate is measured.

**Aegis's unoccupied position:** a verifier with (i) measured precision/recall,
(ii) calibrated abstention ("un-gradeable" instead of a false verdict), and
(iii) coverage/oracle-stratified grading. None of this exists in OSS.

**Caution / how to frame it:** AutoPatchBench's white-box differential testing
partially overlaps the *behavioral oracle* component. The moat is **not** the oracle
alone — it is the **integrity discipline** (measured FP/FN + abstention + coverage).
Lead every claim with the verifier's own precision/recall number; that is what no one
else has.

## 3. Second vulnerability class — recommendation

**OS Command Injection (CWE-78).**

- **Sound mechanizable oracle (criterion i):** structurally analogous to the
  path-traversal `resolve()+prefix-containment` oracle. Instead of "did the resolved
  path escape the root," check **"did a sentinel side-effect that only attacker-
  controlled command execution could produce actually occur"** — a benign canary
  (write a unique token to a temp file / spawn a recognizable process). The side-effect
  is causally downstream of the injection only → no false-signal path → sound and
  binary. Abstention maps cleanly: if the harness can't instrument the sink, emit
  "un-gradeable."
- **Benchmark mapping (criterion ii):** CWE-78 is in **BountyBench** (covers 9/10 OWASP
  Top 10), a first-class class in **PatchEval** (65 CWEs, 230 Dockerized PoC-validated
  cases), and present in **VulnRepairEval**. Results stay baseline-comparable.
- **Calibration anchor:** Shellshock (**CVE-2014-6271**) — canonical CWE-78, trivially
  observable side-effect oracle, ubiquitous PoC.

Queue **SSRF (CWE-918)** third (oracle = outbound-callback to an attacker-designated
internal target; sound but adds a network-observability + internal/external edge case).
Defer SQLi (murkier oracle), deserialization (gadget-chain fragility). Keep
**prompt-injection a stub** — no sound deterministic oracle, doesn't map to the
patch-genuineness benchmarks.

---

## Evidence

**OSS Cyber Reasoning Systems**
- Buttercup (Trail of Bits, AIxCC 2nd) — https://github.com/trailofbits/buttercup — AGPL-3.0. Verify: PoV-no-longer-triggers + build/tests. No measured verifier precision; no abstention.
- Atlantis (Team Atlanta, AIxCC 1st) — https://github.com/Team-Atlanta/aixcc-afc-atlantis — MIT. Verify: PoV re-run + functional gate. No abstention.
- RoboDuck (Theori, AIxCC 3rd) — https://github.com/theori-io/aixcc-afc-archive — AGPL-3.0. Verify: PoV re-run + tests. No abstention.
- Architecture of record: SoK: DARPA's AIxCC — https://arxiv.org/abs/2602.07666

**Reproduction / patch-verification infrastructure**
- ARVO (atlas of reproducible vulns) — https://github.com/n132/ARVO — paper https://arxiv.org/abs/2408.02153. Differential PoC re-run; *already caught 300+ falsely-"fixed" still-active CVEs.* Grades vs canonical patch; no measured precision, no abstention.
- OSS-Fuzz — https://github.com/google/oss-fuzz ; oss-fuzz-gen — https://github.com/google/oss-fuzz-gen

**Benchmarks**
- BountyBench — https://bountybench.github.io — arXiv 2505.15216 — has per-vuln "verifiers" but no measured verifier precision / abstention.
- AutoPatchBench (Meta, CyberSecEval 4) — https://github.com/meta-llama/PurpleLlama — PoV + fuzzing + white-box **differential** testing (closest to Aegis's oracle); does not measure its own FP/FN.
- VulnRepairEval — https://arxiv.org/abs/2509.03331 — exploit-based; critiques superficial validation.
- PatchEval — https://github.com/bytedance/PatchEval — 1,000 CVEs / 65 CWEs; 230 Dockerized.
- PVBench / "Patch Validation in AVR" — https://arxiv.org/abs/2603.06858 — finds >40% of "correct" patches fail deeper validation; fixes with more tests, not abstention.
- ZeroDayBench — https://arxiv.org/abs/2603.02297 — 22 novel critical vulns; frontier models can't yet solve.

*Unverified flags: exact CWE mapping of CVE-2021-22204 to confirm at gold-set build; 4 of 7 AIxCC finalist repos public per the SoK paper but not individually fetched.*
