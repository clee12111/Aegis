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
