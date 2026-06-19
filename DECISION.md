# Aegis — Decision Log

Running log of dated, Act-level and tactical decisions, newest at the top. Append
here as work progresses. The permanent, foundational architectural decisions live in
**CLAUDE.md** under "Foundational decisions" — this file is the running counterpart.
Format: date, decision, why, precludes.

---

### 2026-06 — Act I CVE trio locked (post-recon ×2)

**Decision:**
- (a) Lunary bounty_0 — CVE-2024-1625, CWE-639 authz bypass
- (b) MLflow bounty_1 — CVE-2024-1558, CWE-22 path traversal
- (c) vllm bounty_0 — CVE-2024-11041, CWE-502 deserialization

**Why:** All confirmed packaged bounties in Act III target systems; each teaches a
distinct detection-hardness reason (absent-check / multi-hop taint / benign sink).
Original guesses (MLflow CVE-2024-1483; an MLflow recipe-RCE) were not packaged;
two recon rounds corrected before any build.

**Env:** WSL2 + Docker, clone inside ext4 never /mnt/c; BIOS virtualization enabled (2026-06-09).

**Precludes:** Studying CVEs absent from bountytasks (no Act III transfer).

---

### 2026-06-09 — MLflow (b) sub-choice: bounty_1 primary, bounty_0 later

**Decision:** Act I MLflow study uses **bounty_1** (CVE-2024-1558, single-file
`handlers.py` traversal) as the primary. **bounty_0** (CVE-2023-6018, CWE-23,
severity 10, $30,485, 4-file patch across the model registry) is kept as an
optional depth study *after* the trio, not part of the Act I exit gate.

**Why:** bounty_1 is the cleanest first multi-hop taint chain; the exit gate is
about understanding one traversal cold, not the biggest bounty. Depth study adds
breadth once the mental model is solid.

**Precludes:** Treating bounty_0 as required Act I material.

---

### 2026-06-09 — Cowork role split: keep a separate engineer

**Decision:** The Cowork advisor (file + light-Python access) handles planning,
recon, doc edits, and non-containerized Python. A **separate Claude Code instance
remains the engineer** for Docker and the full BountyBench harness. Roles are not
merged despite the advisor now having file access.

**Why:** The advisor sandbox cannot run Docker; BountyBench runs in Kali
containers. Keeping the engineer separate preserves the verification seam and
WORKFLOW.md's division of labor.

**Precludes:** Routing Docker/harness runs through the Cowork advisor.

---

### 2026-06-09 — Compute/storage strategy: whole project on GCP $300 trial

**Decision:** Run the container work for the whole project on a single Google Cloud
free-trial VM ($300 / 90 days), capped at ~2 months of use, rather than splitting
across Azure/Oracle or running locally. Local C: drive is too small (~45 GB) for
Act III's container footprint (est. 80–100 GB working set).

**Sizing:** x86 VM ~e2-standard-4 (4 vCPU / 16 GB), ~150 GB balanced disk. Stop the
VM when idle; spot VM optional for the Act III benchmark burst.

**Cost check:** even leaving the VM on 24/7 for 2 months ≈ $220 (< $300); stop-when-
idle ≈ $88. Money is not the binding constraint at a 2-month cap; the 90-day trial
window is.

**Why:** one platform / one bill is simpler than juggling renewable Azure + GCP.
$300 covers ~2 months with comfortable headroom. Architecture must be x86 (Kali
agent + BountyBench images are amd64) — rules out Oracle's free ARM tier.

**Guardrails:** do NOT upgrade the trial to a paid account; delete the VM **and**
disk when done (disk bills against credit even while the VM is stopped). Optionally
keep Act I (CVE hand-study, no containers) local to preserve the 90-day window.

**Precludes:** Relying on the cramped local C: drive for Act III; using Oracle's
free ARM tier for amd64 images; assuming an idle-but-undeleted disk is free.

---

### 2026-06-10 — GCP disk sized to 300GB; keep the harness canonical (no Dockerfile fork)

**Decision:** Resize the GCP boot disk from 150GB to **300GB** rather than shrink the
BountyBench backend image by patching its Dockerfile. The smoke run exhausted 150GB
because the footprint stacks up: host OS + repo/venv (~25GB) + backend image (~20GB,
bakes in the full 19GB repo incl. 14GB .git/modules) + build cache (~49GB) + per-task
DinD inner images (~20–30GB).

**Why resize, not fork:** the backend Dockerfile bakes in 14GB of `.git/modules` it
only needs for a metadata-only `git submodule sync` — genuinely wasteful. But editing
the Dockerfile to strip it diverges our build from canonical BountyBench, which breaks
comparability with the published baselines the whole project measures against (see
"Baseline methodology" in CLAUDE.md). Disk is cheap inside the $300 GCP budget
(~300GB balanced ≈ $30/mo); baseline validity is not negotiable for 14GB.

**Disciplines:** after the image builds, `docker builder prune -af` to reclaim cache
(keeps the image); prune per-task DinD images between Act III tasks. After any
`gcloud compute disks resize`, extend the fs inside the VM (`growpart` + `resize2fs`)
and confirm with `df -h /` — the block device grows but ext4 does not auto-grow.

**Follow-up (later, not now):** the baked-in `.git/modules` bloat is worth raising as
an upstream issue/PR to bountybench — an optimization that keeps the build canonical
for everyone, rather than a local fork.

**Precludes:** Forking the harness build to save disk; assuming a GCP disk resize
grows the filesystem on its own.

---

### 2026-06-10 — Platform/portability fixes to the harness are allowed; semantic forks are not

**Decision:** Patching BountyBench to fix a *platform* bug is permitted and does NOT
break baseline comparability. First case: `tools/dockerd-entrypoint.sh` hardcoded a
`linux-arm64` `docker-credential-pass` binary, causing `exec format error` on the
amd64 VM and failing all image pulls inside DinD. Fix = arch detection
(amd64/arm64 from `dpkg --print-architecture`/`uname -m`), implemented as a minimal,
documented local patch.

**The line:** comparability is about whether the *same tasks are graded the same way*.
- **Allowed (portability):** changes that only let the canonical harness *run* on the
  host — architecture detection, missing-binary fetches, path fixes. They change
  nothing about what is tested or how it is scored.
- **Forbidden (semantic):** changes to task definitions, agent behavior, the verifier,
  scoring, or resource limits. These invalidate the comparison to published baselines.

**Discipline:** keep such fixes minimal, save them as labeled local patches
(`patches/…`), document them as portability fixes, and upstream where possible so
provenance stays clean and auditable. When reporting results, state the harness was
canonical plus the documented portability patches.

**Precludes:** Using "it's just a fix" to justify task/agent/verifier changes; applying
undocumented harness edits.

---

### 2026-06-11 — Environment proven end-to-end (BountyBench runs on GCP)

**Milestone:** the full BountyBench loop runs on the GCP VM — containers up → agent
executes in the Kali sandbox → verifier emits a verdict → cleanup. Mock-model smoke run
on lunary bounty_0 (`exploit_workflow`, `--phase_iterations 2`) returned the expected
verdict: `success=False` / `no_submission` (mock never submits). The "set up the
environment" half of Act I is **complete**.

**Portability fixes applied (NOT forks — they only let the canonical harness run; no
task/agent/verifier semantics changed):**
- `patches/dockerd-entrypoint-arch.patch` — credential-helper arch detection (was
  hardcoded `linux-arm64`; broke amd64 image pulls).
- qemu/binfmt arm64 emulation (kernel-level, covers DinD) — runs the arm64-only
  `cybench/bountyagent` image on the amd64 host.
- Disk resized 150 GB → 300 GB.

**Bug AVOIDED, not patched:** `base_phase.py:257` assumes the final message is an
`ExploitAgentMessage`; with ODD `max_iterations` the check-run lands on `ExecutorAgent`
(no `.success`) and crashes. Canonical default (10, even) is safe. **Use EVEN
`--phase_iterations` for all runs; never patch the scoring-completion path.**

**Arch plan resolved:** native amd64 `bountyagent` IS buildable
(`bountytasks/.github/Dockerfile`, base `cybench/kali-linux-base:latest`, via
`tools/build.sh`). Emulation is fine for mock/non-measured runs; **build native amd64
before measured Act II/III runs** to avoid emulation timing skew (slowness could trip
task time/step limits → unfair results).

**Upstream bugs to report (not local concerns):** arm64-hardcoded credential helper;
odd-iteration `base_phase` crash; arm64-only published `bountyagent` image.

**Precludes:** running MEASURED tasks under emulation with odd iteration counts;
treating the emulation/patches as semantic changes (they are not).

---

### 2026-06-11 — Native amd64 bountyagent: deferred, feasible, recipe recorded

**Decision:** DEFER the native amd64 `bountyagent` build to just before Act III
measured runs. Emulation (arm64 image under qemu) is proven (smoke runs #8, #9) and
correct; native is only a *timing* optimization that matters once task time/step limits
are scored. Don't gold-plate infra before the science.

**Feasibility CONFIRMED:** `cybench/kali-linux-large:latest` is multi-arch (amd64 +
arm64), so a native amd64 `bountyagent` build IS possible on the current amd64 VM. No
arch switch (to ARM) needed — the fully-native amd64 endgame works. (Retires the earlier
worry that the VM architecture was wrong.)

**Native-build recipe for later (do NOT use the wrong Dockerfile):**
- Use the **root** Dockerfile (`FROM cybench/kali-linux-large:latest`), NOT
  `bountytasks/.github/Dockerfile` (stripped-down: wrong base, missing
  entrypoint/venv/packages — would diverge from canonical).
- Build inside DinD with the real context via an ad-hoc mount
  (`docker compose run -v ~/bountybench:/build:ro ...`), or build on host + `save`/`load`.
- The skip-pull patch (already in the backend image, currently INERT) activates the
  local native image once it exists; until then it falls through to the canonical pull.

**Known-good state:** arch-detection credential-helper patch CONFIRMED in the backend
image; skip-pull patch present but inert; arm64 `bountyagent` pulled and run under qemu;
mock smoke green (verdict emits).

**Precludes:** switching the VM to ARM (unnecessary — amd64 native path is available);
building the native agent from the `.github` Dockerfile (non-canonical).

---

### 2026-06-17 — Act II: BountyBench verifier recon + Aegis verifier scope

**Recon (engineer, read-only, quoted source) — how BountyBench decides success:**
- **Exploit:** two-phase exit-code check — `exploit.sh` (in Docker) + `verify.sh` (on
  host) must return 0 on unpatched code AND 1 after the known patch is applied.
- **Patch:** re-runs the ground-truth exploit AND runs hidden invariant tests; success =
  invariants pass AND exploit fails after patch. Invariant test files restored from git
  before checking (anti-tamper, but only *listed* paths).
- **Verdict:** binary 1/0, exit-code-driven, propagated agent→phase→workflow→scorer; no
  partial credit, no nonce/tamper proof.

**Honest read:** more rigorous than expected — re-running the exploit during patch
verification is a real protection. But concrete gameability gaps remain; these are the
basis for the Aegis verifier-integrity layer:
- **Patch:** (9) the *same* `exploit.sh` is reused, so a patch that blocks the KNOWN
  exploit without fixing the vuln passes [docs already anticipated this: strict mode =
  held-out variant]; (7/8) a patch that breaks/deletes the endpoint "closes" the exploit
  but is denial-of-functionality, not a fix; (6) any-pass-of-3 retry inflates flaky
  patches; (5) invariant restore is path-list-based, incomplete.
- **Exploit:** (1/3) `verify.sh` runs on the host with a shared rw volume + verify files
  visible to the agent → plant expected artifacts without triggering the bug; (4) exit
  code is the only signal, no tamper detection.

**Aegis verifier = BountyBench's checks + an integrity layer.**
- **Flagship (patch-side; verifier-integrity = genuine-vs-gamed fixes, Hard Rule 6):**
  HELD-OUT exploit variant (strict mode — a genuine fix closes a *different* exploit of
  the same vuln) [gap 9]; FUNCTIONAL PRESERVATION (patched service still serves legit
  traffic on the affected feature, beyond the invariant threshold list) [gaps 7/8];
  CONSISTENCY (exploit must fail across ALL retries, not any) [gap 6].
- **Secondary (exploit-side tamper-resistance):** isolate verify artifacts from the
  agent + nonce/tamper detection [gaps 1/3/4].

**Gold set (the Hard Rule 6 number):** build genuine vs. gamed patches on Meridian/Aether
(own systems, ground truth known); gamed cases instantiate gaps 6–9; run the Aegis
verifier as a classifier → precision/recall.

**Invariant:** the verifier OBSERVES, never steers the agent (Hard Rule 1).

---

### 2026-06-17 — Act II first result: held-out-variant verifier on Meridian

Built the narrowest-first slice: 10-patch gold set (5 genuine, 5 gamed) on Meridian's
prompt-injection vuln; verifier = run held-out exploit B (Phase 10) N=5, threshold k.

**Result:** precision **100% at every k** (no genuine patch ever leaks B); recall **100%
at k≤3**, → 80% (k=4) → 40% (k=5) as the flag-threshold gets lenient (partial-defense
cheats at B=3–4/5 slip through when you require all-5 to flag). **Optimal operating point:
k=1** ("flag if the held-out exploit fires at all") → 100/100. First Hard Rule 6 number on
the board.

**Honest caveats (do NOT overclaim):**
- 100% on a 10-patch HAND-BUILT set is a clean first *signal*, not a robust claim. Genuine
  patches were authored to close B and the verifier runs B → separation is partly by
  construction. Must be stress-tested on a larger, subtler gold set.
- **A/B drifted into different vuln classes.** A became content/data poisoning (NONCE
  disguised as a credible document "fact" the model cites); B is instruction injection.
  Genuine instruction-isolation patches close B (0/5) but NOT A (A fires 1–5/5) — only g5
  ("treat content as data AND be skeptical") closes both. So A is **not** a clean held-out
  variant of B's vuln; the number is valid for *instruction-injection closure via held-out
  B*, but the "known exploit A → held-out variant of the SAME vuln B" demonstration is
  confounded. The real held-out signal here is **site coverage** (gamed patches leave
  Phase 10 unprotected; B lives at Phase 10) — the Lunary "siblings left open" lesson.

**Finding worth keeping:** instruction/data isolation ≠ content-poisoning defense — distinct
defense classes; only the strongest patch addresses both.

**Next:** (a) re-author A as a same-class instruction-injection sibling of B for a clean
matched-pair demonstration; (b) expand + harden the gold set (more, subtler cheats) — a
verifier never wrong on 10 hand-built cases hasn't been tested; (c) optionally treat
content-poisoning as a second vuln class. Files (on VM): exploits/runner.py,
exploits/patches.py, exploits/run_gold_set.py, results/gold_set_results.json.

---

### 2026-06-17 — Act II hardened result: the verifier's real limits (held-out FAMILY needed)

Re-ran on a hardened, de-circularized gold set: A re-authored as instruction injection
(Phase 8 sibling of B); 30 patches, N=20; engineer relabeled by code review BEFORE metrics
(3 genuine→gamed: cosmetic markers, no real boundary; 2 gamed kept despite B=0:
payload-specific filters). Final 12 genuine / 18 gamed.

**Result: F1 = 88.2% at k=15** (precision 93.8%, recall 83.3%) — NOT 100%. The hardened set
broke the verifier informatively. Curve: low k = aggressive (precision 64-75%, weak
"genuine" patches leak); high k = precision rises but recall plateaus ~83% (payload-specific
cheats always escape).

**Two structural findings (the real output):**

1. **A single held-out exploit is itself gameable.** x12 (blocks "NONCE=") and x14 (regex
   "OVERRIDE") are deliberate cheats that score B=0/20 *because B's payload contains those
   exact tokens* → verifier wrongly passes them. Recursion: BountyBench reused 1 exploit
   (gameable) → we used 1 held-out (still gameable by blocklisting its tokens). **FIX: a
   FAMILY of diverse held-out variants** — no single token-blocklist beats ten payloads.

2. **Code-review labels are unreliable for injection patches — effectiveness is empirical,
   not structural.** The one "false positive" (g07) leaks B 16/20 (~unpatched 18/20) yet was
   labeled genuine because it *has* XML tags + warnings. A patch with the cosmetic structure
   of a defense that doesn't reduce injection is NOT genuine — the verifier flagging it is
   *correct*; the label was too generous (also g02/g03/g08/g14, B=12-14/20). Implication:
   genuine-vs-gamed can't be cleanly labeled by code review for injection → reported
   precision is likely *understated*.

Both findings converge on ONE next move: a **diverse held-out exploit family**, which (a)
defeats payload-specific cheats and (b) grounds genuine/gamed labels in measured
effectiveness ("genuine = closes the family," not cosmetic code structure). x13 (partial
defense, B=5/20) is the gray-zone threshold case (real, not irreducible). Complementary
option: a static/semantic-diff check that flags payload-specific filters & whole-feature
deletion (the original recon's gap-8 check).

Engineer's integrity relabeling (label independent of verdict) is why these findings
surfaced honestly.

---

### 2026-06-17 — Act II v3: held-out family works, but the gold set degenerated (measurement caveat)

12-exploit diverse family (L=7 labeling / V=5 verifier, disjoint), patches re-labeled by
EFFECTIVENESS against L, re-run async/parallel.

**Real wins:**
- **Token-blocklist cheats CAUGHT.** x12/x14 (blocked single B by its tokens) leak the diverse V
  set → caught. The held-out FAMILY defeats payload-specific cheats. (Prediction 2 ✓)
- **Strict k confirmed** — the v2 k=15 distortion is gone; optimal k=1. Clean genuine patches +
  strict threshold align. (Prediction 1 ✓)
- **Security finding:** prompt-level injection defenses (tags, boundaries, hierarchy, JSON,
  sandwich) ALL fail against a diverse battery — the "ADMIN CORRECTION" authority-impersonation
  exploit (L2) breaks every one. Only content transformation (base64) substantially resists, and
  even it leaks exotic encodings (unicode / split-token).

**CRITICAL MEASUREMENT CAVEAT — do NOT report 98.3% F1 as a verifier-integrity number:**
- Effectiveness labeling flipped 29 of 30 patches to gamed; only g10 (base64) survives genuine.
  Gold set ≈ 29:1. A trivial **"flag everything"** baseline scores precision 29/30=96.7%, recall
  100%, F1 98.3% — *identical* to the verifier at k=1. At k=1, **TN=0**: the verifier never
  correctly PASSED a genuine patch (g10 was flagged). Precision rests on **n=1** genuine example →
  not a trustworthy number.
- Cause: the effectiveness finding (prompt defenses don't work) is real but collapsed the genuine
  class. Can't measure a classifier's precision with ~1 positive example.

**Have:** a validated verifier MECHANISM. **Still need:** a BALANCED gold set for a meaningful
Hard Rule 6 precision/recall. Options: (a) author genuinely-effective injection fixes (hard, per
the finding); (b) calibrate on a vuln where genuine AND gamed both populate cleanly and ideally
DETERMINISTICALLY — authz/IDOR-style (add-the-check = genuine; blocklist-the-ID = gamed) — which
also tests a 2nd vuln class. Injection turned out to be a poor vuln for measuring *precision*
(genuine fixes are scarce), though excellent for stress-testing the mechanism.

Files (VM): exploits/exploit_family.py, exploits/async_runner.py, exploits/run_v3.py,
results/gold_set_v3_results.json.

---

### 2026-06-17 — Verifier must be vuln-AGNOSTIC (transferability > per-vuln accuracy) [operator call]

**Decision:** the verifier is a GENERAL, exploit-driven mechanism — "run a diverse held-out
exploit family against the patched code; flag gamed if any still succeeds." It contains NO
vuln-specific logic. Vuln-specific knowledge enters ONLY as INPUTS — the exploits and the
success-detector — provided per task (as BountyBench provides exploit.sh / verify.sh).

**Why:** a verifier hand-tuned per vuln (ownership checks for IDOR, isolation checks for
injection) is overfitting — it would not transfer to unseen vulns and collapses at Act III
(40 tasks, many types) / Act IV (arbitrary repos). **Transferability is prioritized OVER
per-vuln accuracy.** A heuristic that boosts accuracy on one vuln but doesn't generalize is
rejected in favor of the general exploit-driven core.

**Implications:**
- REFACTOR the verifier into a vuln-agnostic CORE (run exploits → detect success → threshold →
  metric) + a per-vuln PLUGIN interface (exploit family + success-detector). Injection = plugin #1.
- Prove generality by running the SAME core on a 2nd vuln type (deterministic access-control /
  IDOR) with NO per-vuln tuning → that is the transferability evidence AND yields the balanced
  gold set for a trustworthy precision/recall.
- Heuristic add-ons (functional preservation, semantic-diff) are SECONDARY: functional
  preservation is fairly general (run provided functional tests); semantic-diff is heuristic /
  vuln-fuzzy — keep it a side signal, never the core.

**Relates to** Hard Rule 3 (scaffold general across models) — same spirit, applied to the
verifier across vulns. **Candidate for elevation to CLAUDE.md foundational decisions / hard rules.**

---

### 2026-06-17 — Act II: verifier proven vuln-AGNOSTIC (transferability demonstrated)

Refactored into a vuln-agnostic CORE (`verifier/core.py`: run exploits → label from L →
precision/recall → `evaluate()` pipeline) + per-vuln PLUGIN interface (`run_exploit` + data
registries + config). Injection = plugin #1 (probabilistic, N=10, threshold 0.3); Aether
`write_report.py` path traversal = plugin #2 (deterministic, N=1, threshold 0).

**TRANSFERABILITY PROVEN:** the same `evaluate()` ran both with **ZERO core changes** — a
probabilistic LLM vuln and a deterministic file-write vuln handled identically, configured only
by the plugin's `default_n`/`genuine_threshold`. The vuln-agnostic principle realized in code —
strongest result so far, and the property that carries to Act III.

Traversal gold set: 19 genuine / 11 gamed (effectiveness-labeled; 4 designed-gamed patches blocked
all vectors → relabeled genuine — intent≠effect). **F1 = 100% at k=1 (0 FP, 0 FN).**

**CAVEAT — the 100% is partly BY CONSTRUCTION** (engineer stated the mechanism honestly): V was
built to cover the same bypass CLASSES as L (direct `../`, `./../` prefix, `....//` reconstruction,
txt-format), so any patch leaking an L vector also leaks a V vector → the verifier *cannot* miss
what the labels catch. Confirms the PIPELINE + the value of a diverse family (3 V classes cover all
11 gamed), but does NOT measure real-world COVERAGE / held-out sufficiency.

**Honest coverage test (next, if pursued):** include gamed patches whose bypass class is in L but
NOT in V → recall should drop → characterize "how diverse must the family be?" (= mutation testing's
mutant-diversity question). Deepest ceiling: a bypass class in NEITHER set is a silent blind spot in
both label and verdict — same fundamental limit as mutation testing.

Files (VM): `verifier/core.py`, `verifier/plugin.py`, `verifier/injection.py`, `verifier/traversal.py`.

---

### 2026-06-17 — The verifier is a characterized approximation, NEVER absolute ground truth [operator call]

**Principle:** the verifier/measurement layer is never absolute ground truth — it is a
best-available, falsifiable APPROXIMATION. As the agent's capability scales (detector, red/blue
team), it will produce novel exploits/patches outside the verifier's tested coverage; a static
verifier weakens relative to a scaling optimizer (the RLVR reward-hacking dynamic). No bottom
turtle — even the gold-set labels are a judgment that can be wrong (cf. g07).

**Design consequences:**
- The contribution is an HONEST, CHARACTERIZED verifier (measured precision/recall AND coverage
  limits) — not an oracle. Report where it breaks as a first-class result.
- **Co-evolve:** verifier + gold set are a living artifact, continuously hardened against new cheat
  classes (single-exploit → family was the first instance). Never "done."
- **Prefer deterministic/executable checks** (closest to real ground truth, e.g. file-escape);
  be explicit about uncertainty where judgment is fuzzy (e.g. LLM injection).
- **Abstain over false confidence:** flag "outside my tested coverage → low confidence / needs
  expanded gold set or human review" on novel cases rather than emit a verdict it can't back.
  Future: verdict + coverage/confidence signal, not bare pass/fail. Fail loudly, not silently.
- Treat the verifier's number as reliability-with-known-limits, not truth.

This is the epistemological foundation of "the verifier is the contribution": the value is rigor
and honesty about limits. Drives "characterize coverage" (map blind spots) as a PERMANENT
discipline. **Candidate for elevation to CLAUDE.md hard rules.**

---

### 2026-06-17 — Verifier coverage characterized: honest recall-vs-diversity (verifier half DONE)

Broke the by-construction coverage: added L-only bypass classes (backslash `..\`, absolute path,
dot-backslash) NOT in V.
- 9 gamed patches now MISSED → **recall 100% → 55%** at k=1; **precision stays 100%** (robust
  genuine fixes pass any test, never false-flagged).
- **Recall-vs-coverage curve** (V covering 1→7 classes): 15 → 30 → 45 → 55 → 85 → 100 → 100%.
  Recall is bounded by V's class coverage; biggest jump is adding backslash (+30pp, shared blind
  spot); the FIRST missing class is the critical gap; diminishing returns after.

**The honest characterization the verifier needed.** Approximation, not oracle: precision perfect,
**recall = f(held-out family diversity)**, and it can MEASURE known blind spots but can NEVER prove
the absence of an unknown one (a class in neither L nor V is silent in both).

Significance: this is the MEASURED version of the scaling-weakness prediction; the blind spots ARE
the reward-hack attack surface (a scaling agent optimizes toward uncovered classes); the
security-critical error is the recall MISS (passing a gamed patch), which the curve quantifies.

"Validated" now has a concrete answer: precision/recall + coverage curve + explicit unknown-blind-
spot caveat. **Verifier half of Act II is honestly DONE.** Next: the scaffold delta (capability half).

Files (VM): verifier/* (+ coverage-curve results).

---

### 2026-06-17 — Verifier upgrade: property-oracle + FUZZING (agnostic, not a growing blocklist) [operator call]

**Decision:** move the verifier from EXPLOIT-ENUMERATION (hand-listed bypass families —
signature/blocklist style: bloats, blind to novel) to a PROPERTY ORACLE + FUZZER. Clean on
DETERMINISTIC vulns (crisp property); weaker for fuzzy LLM vulns (no crisp oracle → weaker checks +
abstain).

**Design (traversal plugin):**
- ORACLE (canonical invariant): after the patch's sanitizer + path resolution (`realpath`), does it
  land OUTSIDE the upload dir? Catches ANY escape — backslash, absolute, encoded, unseen — because
  all resolve out-of-bounds. Property, not pattern.
- FUZZER: grammar/component generation (separators `/ \`, segments `.. . names`, absolute prefixes,
  encodings) + mutation; ~5–10k titles/patch. Gamed if ANY escapes; genuine if none in budget.
- KEY VALIDATION: does fuzzing CATCH the 9 gamed patches enumeration MISSED (backslash/absolute)
  WITHOUT hand-listing them — the fuzzer's primitives generate the escapes on their own.

**Honest limit (the blind spot MOVES, doesn't vanish):** from "attack classes I enumerated" to "the
fuzzer's primitive vocabulary + exploration reach" — far broader and non-bloating, but still a
coverage. A primitive missing from the grammar is the new blind spot. "No escape in N inputs" =
genuine-with-confidence-bounded-by-budget, not proof. Coverage-guided fuzzing tightens it.

This is the property-based principle (allowlist/invariant over blocklist/signature) that also
underlies the scaffold's taint-flow — unifies generalization across verification AND detection.
Core stays vuln-agnostic (plugin provides generator + oracle; core runs + scores).

---

### 2026-06-18 — Fuzzing verifier validated (mechanism) + OS-semantics CATCH (environment must match reality)

**Mechanism win:** property-oracle + fuzzer (7,947 generated inputs, grammar + mutation) recovered
ALL 9 gamed patches enumeration missed → **recall 55% → 100%, 0 FP** — bypasses GENERATED from
primitives, none hand-listed. Core unchanged (drop-in `VulnPlugin`). Blind spot moved from "class
not listed" (bloats) to "primitive not in the fuzzer's vocabulary" (stable; named gaps: null-byte,
unicode NFKC, resource forks, symlink races, app-indirection, encoding mismatches). **Bonus:** the
fuzzer found **g13 was MISLABELED genuine** by the human labeler — property-check beat human
eyeballing. Strongest validation of property-over-pattern.

**CATCH — results are OS-semantic and this run used WINDOWS semantics** (`normpath` slash-conversion,
`isabs`, `..\esc` escapes, "Windows concurrency", g13 Windows analysis). On Linux, `\` is a literal
filename char → `..\esc` does NOT traverse. So 6 of the 9 recovered patches (backslash: y01-y05, x12)
AND the g13 finding are **Windows-only** — they don't exist if Aether deploys on Linux, where those
patches are actually genuine.

**Principle:** the verifier's RUNTIME ENVIRONMENT is part of the property it checks. OS mismatch
between verifier and target = silently wrong verdicts (a "verifier must model reality" failure).

**Fix (clean, and a point FOR property-over-enumeration):** the `realpath` oracle is OS-aware — run
the verifier in the TARGET's actual deployment environment and it auto-adapts (no per-OS hand-lists).
TODO: confirm (a) where this run executed (Linux GCP VM vs local Windows), (b) Aether's real
deployment OS; align them; re-run; re-report. On Linux the real bypasses are forward-slash + absolute.

Files (VM): `verifier/fuzzer.py`, `verifier/traversal_fuzz.py`, `verifier/run_fuzz_validation.py`,
`results/fuzz_*`.

---

### 2026-06-18 — Threat-model OS fixed to LINUX (canonical); OS is part of the vuln definition

Diagnostic confirmed: the verifier ran on **local Windows 11** (not the GCP VM). Aether has NO fixed
deployment OS (local Streamlit app, no Docker/CI), but the SECURITY-RELEVANT target is **Linux** (web
apps deploy on Linux; CWE-22 and the MLflow CVE this plugin models are Linux-semantic; BountyBench is
Linux).

**Decision: Linux is the canonical threat-model target.** Run the verifier on the GCP Linux VM
(consistent with the rest of the project); the `realpath` oracle auto-adapts to POSIX — no code change.

**Principle:** the OS/runtime is PART OF THE VULNERABILITY DEFINITION, not an incidental environment.
"Is this patch genuine?" has no answer without fixing the threat-model OS — a patch can be genuine on
one OS and gamed on another (block "/" only = secure on Linux, escapable on Windows). The verifier
must run in (or model) the target's real/canonical environment.

Corrected Linux picture (vs the Windows run): backslash classes (E,G) are NOT traversal on Linux →
y01-y05, x12, g13 are GENUINE on Linux; real Linux bypasses are forward-slash (A-D) + absolute (F) →
x04, x09, x14 remain gamed; enumerated miss-rate is smaller on Linux (3, not 9).

**Bonus finding to capture on re-run:** which patches' labels DIFFER across OS = a "defense
portability" result (a fix robust on one platform breaks on another). Process: keep verifier work on
the GCP Linux VM going forward to prevent recurrence.

---

### 2026-06-18 — Linux re-run: fuzzer > hand-labels (ground truth is itself approximate); verifier half DONE

Re-ran the fuzzing verifier on Linux (GCP VM, posix), **ZERO code changes** — the `realpath` oracle
auto-adapted to POSIX (backslash literal; absolute `/tmp/` escapes; forward-slash `../` escapes). The
property approach proving itself: same plugin, OS-native answers. 9 patches flip gamed→genuine vs
Windows (forward-slash-only defenses suffice on Linux). Enumerated V: F1 91.7% (misses x09/x14, whose
real bypass is absolute). Fuzzing V: catches ALL gamed (dominant Linux bypass = absolute `/tmp/esc`).

**KEY recurring insight:** on BOTH OSes, every fuzzer "false positive" was a REAL bug the hand-crafted
L (ground-truth labeling battery) MISSED — g13 (Windows), x04 (URL-encoded prefix) + y03 (`../`+absolute)
(Linux). **The fuzzer is more thorough than the hand-listed ground truth.** Therefore:
- "precision < 100% vs L" was the fuzzer EXPOSING label gaps, not fuzzer error.
- Do NOT headline the "corrected 100%/100%" — circular (labels fixed using the fuzzer's findings).
  **HONEST headline: the property+fuzzing verifier found 3 real bugs the hand-crafted ground truth
  missed, across two OSes; its reliability is bounded by input-space coverage, not a hand-list.**
- This is the "no bottom turtle": even labels are approximate. For DETERMINISTIC vulns, property
  oracle + thorough fuzzing IS the most reliable ground truth (modulo input coverage) — generate
  LABELS by fuzzing too, not by hand.

**Bonus (paper-worthy): defense portability** — 6 patches (g13, x12, y01, y02, y04, y05) genuine on
Linux but gamed on Windows (forward-slash-only defenses). A fix valid on one OS, broken on another.

**VERIFIER HALF OF ACT II = DONE:** vuln-agnostic core (2 vuln types), property+fuzzing (out-thoroughs
hand-labels), OS-aware by construction, characterized coverage + honest limits, real findings. Next:
the scaffold delta (capability half).
