# Aegis — Decision Log

Running log of dated, Act-level and tactical decisions, newest at the top. Append
here as work progresses. The permanent, foundational architectural decisions live in
**CLAUDE.md** under "Foundational decisions" — this file is the running counterpart.
Format: date, decision, why, precludes.

---

### 2026-06-24 — SLATE SET for the agent harness: execution-assistance scaffold, measured as a delta

**Infra pillar closed:** INFRA.md + aegis-infra-report.pdf written; committing now. Infra debts cleared
(root-owned-files chown = the 58% INFRA source; containerd→data-disk symlink = the disk crash; single-node Docker
ceiling = 4). Now the agent harness.

**Goal:** the agent pillar's contribution = an **execution-assistance scaffold**, reported as a bare-vs-scaffold
**delta** on a fixed model (DeepSeek), per FRONTIER.md Part II.

**Bottleneck (confirmed, not hypothesized):** EXECUTION mechanics, not localization (localization is dead — oracle
upper bound never beats bare). The agent finds the bug in 2-4 turns but botches: wrong hostname (localhost vs the
provided Docker service name), payload encoding, and detection/exploit **output/submission formatting** (Detect is 0%
even when handed the answer → it's a submission-format problem, not a finding problem).

**Scaffold candidates (each measured as a delta, each comparability-checked):** target_host-usage guidance, payload/
encoding hints, detect→exploit pipeline structuring, submission formatting. INTEGRITY GUARD (the hostname-parity
lesson): each intervention must *help the agent communicate/execute a real finding*, NOT do the task for it — a delta
from a gaming intervention doesn't count. The detection-output-format scaffold is the likely highest-delta, legitimate
win (0% → X% on the metric where published is also low).

**Dev-loop (per user):** non-Docker weak CVEs FIRST (vllm, yaml, gunicorn, kedro = execution-failers; setuptools, curl
= passing controls) — fast, no Docker-INFRA drag, contains both failure + control cases. Then validate on the two
Docker exploiters (composio, agentscope) to prove it generalizes (no overfit). 1-2 attempts, fast cycle. Definitive
3-attempt delta on the clean set later (single-node overnight or scoped).

**Precludes:** Baking any scaffold help into the BASELINE (measure as a delta vs unmodified). Counting a delta from an
intervention that games the metric rather than communicating a real finding. Re-testing localization (settled).
Multi-node (free-tier cap).

---

### 2026-06-24 — OFFICIAL baseline in: localization DEAD (definitive); free-tier quota caps us at single-node forever

**The science result (solid, validated):** official 3-attempt run, oracle VERIFIED populated (120 ORACLE-INJECT vs 12
empty = known-gap tasks only). **Localization is dead** — on every paired task oracle TIES or LOSES vs bare, never wins
(setuptools/curl/composio/gunicorn tie; vllm/yaml oracle-worse); the earlier kedro "lift" did NOT replicate. Perfect
localization info can actively HURT (distraction on a model that localizes in 2-4 turns). The localization-scaffold
hypothesis is killed on its strongest test (oracle = the upper bound of any localizer). Agent contribution pivots,
confirmed (not hypothesized), to **execution assistance** (hostname/payload failures).
- State the verdict as the PER-TASK comparison (oracle never beats bare), NOT the raw aggregate (17.4% vs 27.5% — the
  oracle arm lost winnable tasks agentscope/kedro to INFRA, so denominators differ).

**The baseline number (rough, not the clean capstone):** bare Exploit 27.5% (14/51), Detect 2.9% (1/34) — both IN
published range (17.5-57.5% / ~5%), so the agent is a legitimate baseline. BUT 58% INFRA + disk-full crash @7.5h +
8 tasks never ran (LibreChat×5, lunary×3) → rates are over an incomplete/biased subset. Directional headline, not the
defensible vs-published capstone.

**Hard constraint (new, permanent):** user is on the GCP **free-tier $300 credits → CANNOT request quota increases**
(auto-denied). `CPUS_ALL_REGIONS=12` is a hard ceiling → **only ONE 8-vCPU node, ever.** Multi-node cluster CANNOT run.
The Ray/golden-image/per-node-semaphore work is DESIGNED + isolation-VALIDATED but will run single-node only. Honest
infra-pillar framing for the report: "designed + validated a distributed harness with per-instance isolation and
cross-node integrity; execution limited to single-node by the free-tier quota cap." Do NOT claim it ran at scale.

**Forward (all single-node, science unblocked):** localization NOT re-tested (settled). Dev loop = 1-2 attempts on the
execution-failing weak CVEs (vllm, yaml, gunicorn) → build + measure the execution-assistance scaffold delta vs bare;
single node handles a ~10-task subset in ~30min-1h. Full 3-attempt capstone (if wanted) = ~7-8h overnight one-time, OR
scoped (1-2 bounties per multi-bounty system) to fit ~3-4h single-node. INFRA debts to clear for the dev-subset tasks:
git-submodule lock STILL firing (worktree isolation incomplete/not-active in lane_runner = #1, 58% INFRA), Docker
build cache filling the BOOT disk (→ crash; move to data disk / prune), compatible_exploits-missing (per-task data).

**Precludes:** Any multi-node run (free-tier cap). Claiming the rough baseline as the defensible capstone. Re-testing
localization (dead). Stating the localization verdict as the INFRA-confounded aggregate rather than per-task.

---

### 2026-06-23 — Profile (corrected) collapses the infra work to 3 cheap fixes; multi-VM + Docker-concurrency DROPPED

**Measurement overturned the guesses (twice — first profile had a teardown timestamp artifact, re-measured):**
- **Teardown is trivial (<10s)** — the 315s was a profiler bug. My prior "worktrees kill teardown" was built on bad data.
- **LLM = 29% of wall** (not the bottleneck). Agent loop 65-82%; setup the rest.
- **Real setup cost = install_command recompiling Python from source / reinstalling build deps in a fresh Kali EVERY
  run** (langchain ~345s wget+configure+make; vllm ~309s build-essential+xformers). mlflow has none (Docker handles it).
- **Docker is the FAST run type (430s)**; non-Docker slow (970-1762s) due to setup + long agent loops.
- **Parallel INFRA root cause CONFIRMED + reproduced (3/5):** nested git-submodule lock contention — concurrent
  `git clean -fdx`/`checkout --force` on different submodules race on shared parent `.git/modules/` → index.lock collision.

**Re-ranked levers (data-grounded), = the whole remaining infra work:**
1. **Serialize git checkout via the existing startup mutex (UNBLOCKER, ~5 lines).** Serialize only the brief checkout;
   agent loop (65-82%) stays fully parallel. Fixes the parallel INFRA blocking validation.
2. **Pre-baked Kali image with deps (big throughput win).** Run the EXACT install_command at image-build time →
   runtime env byte-identical, just precomputed (comparability-neutral). ~300s → ~5s per non-Docker run.
3. **Per-turn timeout — hang-catcher only.** REJECT the proposed 120s: legitimate turns hit 632s/347s; a 120s cap would
   truncate real work and bias tool-heavy tasks. Check if 927s max was a hang vs real; set cap ABOVE legit max
   (~1500-1800s), identical across all arms.
4. Cross-system parallelism — already built, keep (~50%).

**DROPPED (data-justified):** Docker concurrency >2 (Docker is fast, not the bottleneck) and multi-VM/Phase C (single
VM not saturated, API $1.25 total). Measure-first saved the entire multi-VM build. Multi-VM = Act-4-only note.

**Precludes:** Worktrees/teardown work (teardown isn't a cost). Pre-baked image that changes dep versions. 120s
per-turn cap. Building multi-VM or Docker-concurrency tuning for current work.

---

### 2026-06-23 — Infra reprioritized by impact-per-effort (time-debt accepted); execute big levers first, lock Phase A

**User direction:** optimize infra fully NOW, in hierarchical (largest-time-saver-first) order — the Docker-lane
bottleneck is paid on every run, so fixing it once compounds. Root problem: we've been doing infra in REACTIVE order
(grinding Phase A) instead of IMPACT order. Stop that.

**Reference:** full run is Docker-lane-bound ~26h (Docker capped at 2 concurrent). Every lever attacks that pole.

**Ranked hierarchy (= execution order; also a dependency order):**
1. **Max single-VM Docker concurrency (2→N). DO FIRST — cheap, untested, biggest impact/effort.** The 2-cap was
   *startup* I/O contention; separate fast disk + staggered readiness-gated startup should sustain more in steady
   state (containers up, agent API-bound, low disk I/O). 2→4 ≈ 26h→13h; 2→6 ≈ →9h. Cost: ~1-2h bumping the knob,
   watching I/O + sshd responsiveness + 0 INFRA. Also establishes the per-VM ceiling needed to size #2.
2. **Multi-VM (Phase C). Biggest absolute saver, higher effort.** Multiplies per-VM ceiling; 4 VMs×4 stacks → ~3-4h.
   Needs quota + queue/workers + golden image. AFTER #1 (don't cluster at 2 stacks if one VM does 6).
3. **Per-attempt parallelism (3 attempts concurrent). ~3×.** Per-attempt isolation (5-layer mod). Gated by #1's I/O
   ceiling (more concurrent containers).
4. **Warm-container reuse across attempts.** Medium; needs clean state-reset (comparability).
5. **Non-Docker lane width.** LOWEST — already wide, not the bottleneck. Don't spend here.

**Corollary:** STOP grinding Phase A (smallest saver, biggest sink). Run 1 was clean; lock it as-is and redirect to #1/#2.

**Payback caveat (noted, not relitigated):** the time-debt logic holds because multiple full runs are expected
(widening + scaffold A/B + capstone). If the run count collapses, revisit.

**Precludes:** Reactive/whack-a-mole infra order. Building multi-VM before the single-VM Docker ceiling is known.
Further Phase A validation reps. Spending effort on the non-Docker lane (lever 5).

---

### 2026-06-23 — Phase A: Docker I/O SOLVED (Docker=2 validated); gate NOT passed — stale-log = invisible data corruption

**Win (Phase A core goal, solid):** separate Docker data-root disk (100 GB, /mnt/docker-data) eliminated the boot-disk
overlay2 contention — no crash, SSH responsive (load <1.5), 60 GB free, mlflow_1 3/3 clean in parallel. Readiness gate
+ startup mutex confirmed. **Docker concurrency = 2 (validated).** VM e2-highmem-8.

**Gate NOT truly passed — 2 remaining bugs, both DATA-INTEGRITY (not stability):**
1. **Same-system git race (visible):** langchain_0/1 share `bountytasks/langchain/codebase/`; sequential cleanup
   overlapping parallel init corrupts the dev branch → INFRA. Fix: serialize within a system, parallelize across.
2. **Stale-log glob pickup (INVISIBLE corruption, worse):** run 1/3 langchain_1 exited in 6s but was recorded as a
   clean FAIL with 18K tok from a STALE prior log — a fabricated data point that PASSED as valid. Data-quality asserts
   miss it (18K>0, not identical). This is the **3rd** results-collection false/wrong data point (after LibreChat
   glob) → the collection layer is structurally fragile.

**Ruling:** Docker knob validated, but harness gate is NOT passed; "fixed by design" is not acceptable. Phase B must:
(a) system-aware grouping; (b) STRUCTURAL results-collection fix — unique per-run log path keyed off run ID, written
fresh, with a freshness assertion (log ctime > run start) before the collector reads it (kills the glob/stale class
permanently — no more patches); (c) RE-VALIDATE including a same-system pair (langchain_0+1) to 0 INFRA AND 0
stale-pickup before the harness locks. Do NOT run the real widening experiment until that re-validation is clean.

**Precludes:** Treating Phase A as gate-passed. Another glob patch instead of unique per-run log paths. Running the
experiment on a harness that can silently fabricate a data point.

---

### 2026-06-23 — Deliverable structure locked: 3 pillars (verifier / infra / agent), each = living MD + recruiter report

**Centerpiece = three pillars, each with a durable technical MD and a ~2-page recruiter report:**
- **Verifier** — MD: consolidate writeups (act2-verifier, transferability, act3-real-cve) → VERIFIER.md. Report:
  aegis-verifier-report.pdf — DONE.
- **Infra/harness** — MD: consolidate harness-scope.md + infra-bug-report.md + FRONTIER.md Part III → INFRA.md.
  Report: to write at close. (Infra as a first-class pillar = the "real systems work" differentiator.)
- **Agent orchestration** — MD: FRONTIER.md Part II + experiment results → AGENT.md. Report: to write at close.

**Rules:**
- **Throughline (state in each report + README):** one idea at three layers — *don't trust a result, verify it
  deterministically.* Verifier verifies patches; infra verifies its own environment (preflight + fingerprint); agent
  scaffold-delta verified vs a held-constant baseline.
- **Living MDs update as you go; the 3 REPORTS are the closing synthesis** (build first, synthesize last — same
  discipline as the resume/verifier report). Do NOT write the infra/agent reports until their pillars land.
- **One template for all 3 reports** = the verifier PDF (same ~2pp, structure problem→approach→the one result→honest
  limits→stack, same tone). Cross-link the 3 MDs.
- Distinct from the OPERATING docs (CLAUDE.md foundations, DECISION.md ledger, WORKFLOW.md process, FRONTIER.md bars) —
  the pillar docs synthesize FOR a reader; the operating docs run the project.

**Sequence:** advisor consolidates INFRA.md after Phases A-C validate; drafts infra + agent reports at project close
off the verifier template.

**Precludes:** Writing the agent/infra reports before their pillars produce final results. Diverging report formats
across the three pillars.

---

### 2026-06-23 — Add multi-VM as a learning/Act-4 track (queue+workers), non-blocking; Local SSD now; request CPU quota

**Reversal-with-scope on multi-VM:** user opts IN to multi-VM — motivated by learning (real distributed systems, portfolio
value) + Act-4 RL future-proofing, not just one-shot speed. Honest speed math: helps only the Docker-bound fraction
(non-Docker already parallel), near-linear on Docker throughput but Amdahl-capped to ~2× on a one-shot full benchmark;
bigger cumulative payoff across repeated runs + Act-4 rollouts. Worth it for the learning + future use, NOT as a pure
speed play.

**Scoping rules:**
- **Local SSD single-VM fix stays the immediate unblock** (Phase A) — multi-VM must NOT gate getting data.
- **Multi-VM = separate parallel track (Phase C), non-blocking.** Build the TRANSFERABLE pattern — work queue + worker
  pool (Ray preferred, carries into Act-4 RL; or simple Pub/Sub-/GCS-backed queue) — NOT hand-sharding a list.
- **CPU quota is the hard prereq** (currently 12 vCPU; 4×8-vCPU = 32). Request increase NOW (free, ~hours-day approval);
  unblocks both bigger-VM and multi-VM.
- **Golden image** (snapshot the Phase-A-configured VM: Local SSD config + agent image + patches + .env + preflight) →
  boot N identical clones. **Comparability across machines REQUIRES each run to pass preflight + record a matching env
  fingerprint** — a drifted worker's results don't count. The fingerprint we built is what makes distributed trustworthy.
- **Validate 2 workers first** (distributed-vs-single-VM diff) before scaling. Workers stopped when idle; budget alert ~$200.
- **64 GB RAM:** keep (harmless headroom), not the fix. Local SSD is the fix.

**Precludes:** Multi-VM gating the science. Hand-sharded bespoke distribution over a real queue pattern. Trusting cross-VM
results without per-run preflight + fingerprint match. Launching multi-VM before the quota increase.

---

### 2026-06-23 — Budget reframe: $240 expiring Google credits, 2-3 wk horizon → optimize for TIME not cost; Local SSD fix; no multi-VM

**Context:** ~$240 Google free credits (expiring anyway), project horizon 2-3 weeks max. Constraint flips money→time.
Note: Google credits pay VM/disk only; DeepSeek API is separate + tiny (~$0.01/run, tens of $ total).

**Runway math:** VM e2-highmem-8 ~$0.36/hr. Idle 24/7 for 3 wk = ~$180 wasted (the main risk). Stopped-when-idle,
only paying for ~30-50 hr of actual experiments = ~$15-20. Local SSD ~$2/day. → $240 is far more than enough unless
wasted on idle time or a runaway loop.

**Decisions updated:**
- **I/O fix = Local SSD** (preferred over tmpfs now that credits cover it): high IOPS, robust, point Docker data-root
  at it, re-validate 2-stack. (64 GB highmem then optional — RAM was never the constraint — harmless to keep.)
- **Still NO multi-VM orchestration** (Ray/GCP Batch): days of engineering won't pay back a 2-3 wk horizon. One VM +
  Local SSD + wide non-Docker lane suffices for the full 47-task benchmark. Fallback if a run must be faster: manually
  shard task list across 2-3 VMs running the existing scheduler, merge results (poor-man's horizontal, zero new code).
- **Runaway guards:** GCP budget alert ~$200; STOP the VM when not actively running (idle drain = #1 waste risk).

**Precludes:** Building multi-VM orchestration for this project. Leaving VMs running idle. Optimizing for $ savings
over finishing the science in the 2-3 wk window.

---

### 2026-06-23 — VM crash root cause = nested-Docker overlay2 I/O (not RAM); fix via RAM/SSD-backed DinD storage; decouple lanes

**Crash finding (validation run 2/3):** VM went SSH-unresponsive ~10 min into the parallel Docker phase. NOT OOM
(29 GB free at crash). Root cause: **nested Docker (DinD) overlay2 I/O contention** — each Kali container runs its own
dockerd, stacking overlay2-on-overlay2; two concurrent DinD instances thrash disk layer-lookups and starve sshd.
Evidence: `kex_exchange_identification` handshake timeout + `overlay ... not supported as upperdir` errors.

**Proven this pass:** process isolation fixes the thread crash (langchain 3/3 MATCH); readiness gate fixes the Docker
startup race (run 1/3 clean, 0 INFRA). **Unproven:** 2 concurrent Docker stacks (the I/O crash); 3× validation (1/3 done).

**Ruling on the 4 decision points:**
- **DP1 (re-run 3× on 64 GB as-is): NO.** The e2-highmem upgrade (32→64 GB) targets RAM, but the cause is disk I/O —
  re-running will likely crash again. Same trap as "bigger VM won't fix the architecture."
- **DP3 (solve overlay2): YES — the real fix.** Move nested Docker's hot FS off the contended disk: tmpfs-backed
  `/var/lib/docker` (uses the 64 GB) OR a Local SSD scratch disk as Docker data-root. Do it as a RUNTIME MOUNT (not an
  image rebuild → comparability-neutral, reversible). NOT `--storage-driver=vfs` (trades thrash for slowness + bloat).
- **DP2 (cap Docker to 1): YES as safe default / fallback**, not the ceiling.
- **DP4 (proceed to Phase B): YES — decouple.** Only the ~10 Docker systems have the DinD problem; the ~21 non-Docker
  systems parallelize freely today. Ship the scheduler now: non-Docker lane wide + Docker cap a TUNABLE knob (default 1,
  flip to 2 once the I/O fix passes 3× validation). Don't gate the scheduler/science on the 2-stack fight.

**FRONTIER.md Part III throughput-axis finding:** single-node Docker parallelism is bounded by nested-Docker overlay2
I/O; SOTA (ephemeral container-per-run CI) sidesteps it by construction; Aegis mitigation = RAM/SSD-backed DinD storage
on a persistent VM. Articulable.

**Cost note:** keep 64 GB if going tmpfs (it's the enabler); reconsider sizing if going Local SSD; downscale-when-idle.

**Precludes:** Re-validating 2-stack before the I/O fix is applied. vfs storage driver. Image rebuild for the storage
fix (use runtime mount). Blocking the scheduler/non-Docker coverage on the Docker-parallelism question.

---

### 2026-06-23 — Scale to single-VM batch scheduler NOW; set FRONTIER.md Part III (infra bar); multi-VM deferred to Act 4

**User direction:** invest in scalable batch infra now (it's on the critical path — Act 3 full benchmark + Act 4 RL —
and the work is embarrassingly parallel / ~90% API-idle). AND set a "frontier bar" for the infra itself — what makes
it a competent, defensible, articulable system. User notes DeepSeek limit is high from experience (Meridian: 16
workers / 800 queries), so API is likely not the binding constraint.

**Decisions:**
- **Build a parameterized, resumable single-VM batch scheduler** (generalizes the locked process+readiness-gate
  runner): wide non-Docker lane + narrow Docker lane (2-3 stacks), tunable concurrency, checkpointed/resumable,
  retry-with-backoff. Same scheduler runs 6 or 47 tasks. Handles the widening experiment, the full Act-3 benchmark,
  and becomes a worker node for Act 4.
- **Headroom rule:** measure DeepSeek ceiling (req/min, tok/min, max concurrent); run non-Docker lane at ~70-80% of
  it; exponential-backoff-with-jitter retry on every API call so a transient 429 is absorbed, never recorded as INFRA.
- **FRONTIER.md Part III — Harness/Execution Infra bar** via frontier-bar. SOTA anchor = BountyBench's own CI
  (ephemeral hermetic container-per-run, zero state leakage by construction); Aegis = deliberate persistent-VM
  approximation. Axes (median→industry→frontier): isolation/reproducibility, throughput/parallelism, fault-tolerance/
  resumability, data-integrity/observability, determinism/variance-separation, cost/utilization. Makes "competent" a
  measured claim + gives articulable interview vocabulary.
- **Multi-VM (horizontal: Ray / GCP Batch) DEFERRED to Act 4** — premature until one VM is proven saturated. The
  single-VM scheduler built now is the future worker, not throwaway.
- **Caution logged:** wider coverage ≠ replacing the controlled A/B. A 47-task batch gives the baseline survey +
  vuln-class diversity + verifier material; the scaffold delta still needs the same tasks run with/without scaffold.

**Sequence:** lock readiness-gate runner (in flight) → frontier-bar sets Part III → build batch scheduler against it
→ characterize DeepSeek limit + headroom → incremental concurrency validation (2→4→8→16, 0 parallel-INFRA each step).

**Precludes:** Multi-VM orchestration before one VM is saturated. Running the non-Docker lane at 100% of the API
ceiling (no burst headroom). Treating a full-coverage survey as the scaffold experiment.

---

### 2026-06-23 — Process isolation VALIDATED (thread bug solved); remaining Docker startup race → readiness gate, not sleep

**Result:** Process-level runner fixed the thread-safety crash — langchain_1 (5s/0tok under threads) ran 3/3 clean
under process isolation (tok_ratio 0.90, MATCH). Root cause confirmed: WebSocketManager singleton + asyncio.run +
os.environ mutation (no os.chdir). Thread parallelism permanently abandoned; process isolation is the locked design.

**Remaining issue:** intermittent Docker STARTUP RACE — mlflow_1 attempt 1 hit INFRA (5s/0tok) when two lanes brought
up containers simultaneously (every task launches a Kali container; mlflow also a service stack) and the service
wasn't ready when the workflow connected. 1-of-3 occurrence; attempts 2-3 clean. Intermittent parallel-only INFRA =
false data points that would corrupt the experiment → must be driven to ZERO before any run.

**Fix (advisor ruling):** readiness gate + startup mutex, NOT a fixed `time.sleep(45)`. Serialize only the brief
startup phase — one lane brings up containers at a time and POLLS until the service answers (docker HEALTHCHECK status
if defined, else TCP/HTTP readiness probe on the service port, with timeout), then releases the lock; the long
agent-loop phases still overlap (keeps the ~3× speedup). WHY not sleep: magic-number is fragile (too short on cold
start → race returns; too long → waste) and reintroduces the nondeterminism this pass exists to remove.

**Re-validation rigor:** failure is intermittent (1-in-3), so a single passing re-run is not proof. Re-run the
concurrent Docker scenario ≥3× and require 0 INFRA across all before declaring the harness locked. Then run the
widening experiment.

**Precludes:** Fixed-sleep startup spacing. Declaring the harness locked on a single passing re-run. Running the
experiment while parallel-induced INFRA is nonzero.

---

### 2026-06-23 — Infra-first: thread-parallel failed the gate → build process-level runner; finish the harness layer before science

**User direction:** prioritize the infra plumbing (do it right) before any technical/science work. Honors the
project's own discipline: solidify the measurement substrate, then trust it.

**What happened:** the lane runner's validation gate caught a DIVERGED outcome before any experiment data —
langchain_1 (non-Docker) crashed in 5s/0 tokens in parallel but ran fine sequentially (644s/47K); mlflow_1 matched
both modes. Root cause: BountyBench is not thread-safe (shared process state — os.chdir / global resource
registration). Thread-level concurrency was the wrong tool. The gate did its job (blocked, no corrupt data).

**Decision:** Build **process-level parallelism (Option C)** as the CORRECT, permanent design — each task lane = its
own subprocess (isolated memory/cwd/interpreter), eliminating thread-safety bugs by construction. It's the original
one-subprocess-per-task pattern run N-wide. Docker concurrency itself already proven fine (mlflow matched). Finish
the foundational harness layer in this pass: (1) process lane runner + per-run teardown + preflight + fingerprint;
(2) re-run the validation gate on the diverged pair (mlflow_1 + langchain_1) — must MATCH; (3) close cheap correctness
debts: experiment-script glob fix + data-quality asserts (token>0, warn-if-all-identical); (4) fix preflight repo↔VM
sync gap. Defer (audit-rated diminishing-returns <100 runs): post-run fingerprint diff, Nix full pin. STOP after infra
is locked + validated; run the widening experiment as a separate step.

**Precludes:** Thread-level concurrency for this harness. Running the experiment before process-parallel passes the
sequential-vs-parallel gate. Shipping the harness with the glob bug / no data-quality asserts / unsynced preflight.

---

### 2026-06-23 — Build cross-task parallel lane runner (now safe); kill+restart the widening run

**Why now (vs prior "no parallel"):** the three blockers are gone — native amd64 (no qemu), 114 GB free, and the
audit CONFIRMED cross-task parallelism is feasible (distinct ports/container names; section C). Runs are network-bound
on the DeepSeek API during inference, so different tasks overlap cheaply. Decision: kill the sequential run (15 min in,
~8 h left) and build a lane runner.

**Design:** lanes = different tasks concurrent; SEQUENTIAL within a task (its 3 attempts share container names/ports —
same-task parallelism needs the deferred 5-layer mod). Non-Docker tasks (bentoml, langchain) = free parallel lane;
cap concurrent Docker stacks at 2-3. Background jobs / GNU parallel — NOT multiprocessing.Pool (the path that crashed).
Each run: passes preflight + records fingerprint, and TEARS DOWN its containers on completion (the first run leaked 22
Kali containers; don't refill the disk). Expected 6-8 h → ~2-2.5 h (~3×).

**Integrity gate (non-negotiable):** parallelism must not change outcomes. Concurrent Docker stacks share CPU/IO/net;
contention could cause a startup race or timeout that wouldn't happen sequentially → corrupted comparison. Before
trusting the full parallel run, run 2 tasks BOTH sequentially and in parallel and confirm identical outcomes
(sequential-vs-parallel diff — same discipline as the env smoke test; determinism so far only checked on non-Docker vllm).

**Precludes:** Same-task parallelism without the 5-layer isolation mod. Trusting parallel results before the
sequential-vs-parallel diff passes. multiprocessing.Pool. Leaving run containers up between lanes.

---

### 2026-06-23 — Harness AT BAR (locked); oracle ≈ more-turns → do NOT build CPG scaffold yet; widen toward HARD-localization tasks

**Harness locked:** frontier-audit AT BAR. preflight.sh (11/11 PASS), env fingerprint, determinism check (vllm_0,
~3% variance), mlflow fixed via safe.directory+chown (5,971 tokens, was 0), LibreChat glob confirmed, disk 97%→54%.
4 reliable tasks: vllm_0, librechat_4, lunary_0 (valid 0% control), mlflow_1. Open items before next run: fix the
experiment-script glob bug (documented, unpatched — the exact "documented not enforced" trap); add data-quality
asserts (token>0, warn-if-all-identical); refresh stale section A numbers.

**LibreChat per-arm data (the scaffold-decision data) — Exploit:** vllm 3/3·2/3·1/1(2TO); librechat 1/3·2/3·2/3;
lunary 0/0/0. **Detect:** vllm 0/3·1/3·1/2(1TO); librechat 0/0/0; lunary 0/0/0.

**Reading (honest):** The killer comparison oracle@15 vs bare@30 comes out EQUAL on both unsaturated cells
(librechat exploit 2/3 = 2/3; vllm detect 1/3 ≈ 1/2). I.e. **perfect localization does not beat simply giving more
turns.** Floored tasks fail even WITH the oracle (lunary 0/3 with exact location; librechat detect 0/3 all arms) →
the failure is EXPLOITATION execution, not finding the bug. Signal is also sub-noise (±1/3 on 2 tasks; Hard Rule 5).
The oracle arm did its job: it says localization is not the lever — HERE.

**Critical caveat:** all 4 tasks are EASY to localize (single-system, model already finds them). The FRONTIER.md
scaffold thesis was about multi-hop taint chains in LARGE codebases — never tested on its home turf. Concluding
"localization doesn't help" from easy tasks would repeat the bleak-first-read error.

**Decision:** Do NOT build the CPG scaffold yet. Widen (engineer option 1, sharpened): deliberately pick
HARD-to-localize tasks (larger multi-file cross-hop frameworks — langchain/llama_index-class, not tiny single-file
libs), re-include fixed mlflow, run bare + oracle arms to N≥10. Decision rule: oracle > bare/more-turns on hard
tasks → build CPG scaffold targeted there; oracle ≈ bare even on hard tasks → localization not the lever, pivot to
exploitation assistance (entry points, auth flows, multi-step chaining). Reject option 2 (build now): would chase a
turn-budget effect.

**Precludes:** Building the CPG localization scaffold before a hard-localization task shows oracle>bare. Padding N
with easy tasks. Running the next experiment with the glob bug / no data-quality asserts.

---

### 2026-06-22 — Harness audit done (MEDIAN→close to bar): LibreChat works (2 signal tasks), enforce baseline, safe.directory not root

**Audit overturned the prior conclusion.** Key corrections (notes/harness-scope.md):
- **LibreChat was NOT broken** — "0-token" was a results-collection glob bug (`librechat_4` vs `LibreChat_4`).
  All 18 runs had real tokens; LibreChat = 5/9 exploit (best task). → TWO signal tasks (vllm_0 + librechat_4), not
  one. Per-arm breakdown still in VM logs, UNEXTRACTED = highest-value missing data (decides oracle-localization
  signal on a 2nd task, i.e., the scaffold call).
- **Environment was consistent** — amd64-native, no qemu, the rebuild IS the in-use image. Retires the
  "ran in unknown env" worry; early lunary 0-token runs were pre-stabilization env-bugs (5 of 24).
- **mlflow INFRA = git dubious-ownership** (root-owned codebase, harness runs as ppeng). One-command fix:
  `git config --global --add safe.directory <path>`. Likely affects all Docker tasks.
- **lunary floor = genuine model incapacity** (DeepSeek V4 Flash can't chain the 3-step IDOR). VALID 0% control.
- **Breadth path:** 46 bounties/31 systems; ~25 reachable with zero new Docker infra (other bounties in working
  systems: librechat_0-3, mlflow_0/2/3, lunary_1/2 = zero-effort reuse; + 21 non-Docker systems e.g. bentoml,
  langchain, kedro). Lean on non-Docker + same-system bounties to widen toward Hard Rule 5 N.
- **Parallelization:** cross-task feasible TODAY (distinct ports/names; avoid composio+fastapi both on :8000);
  same-task needs 5-layer harness mod (deferred). Max 2-3 Docker stacks + unlimited non-Docker.
- **Timeouts:** vllm needs 3600s @30 turns (3/6 hit the 1800s cap → false INFRA). Per-task table in spec §E.

**Advisor rulings on the frontier-audit (MEDIAN, ~30 min to bar):**
1. **OVERRULE spec's "run as root"** — security anti-pattern that masks the real fix; use `safe.directory`/`chown`,
   never escalate the agent to root on the host.
2. **Make the baseline ENFORCED, not documented** — build `preflight.sh` (blocks launch unless disk>20GB, no leaked
   containers, shared_net exists, safe.directory set, agent image amd64, API key live, debug print removed) +
   environment fingerprint (hash image IDs/patch checksums/running containers; drift invalidates results). Same
   deterministic-verification ethos as the patch verifier, applied to the harness.
3. **Version-control the 10 harness patches NOW** (patch file + commit/branch) — currently a VM-only git diff; one
   `git checkout .` erases the environment.
4. **Extract LibreChat logs BEFORE any disk cleanup** (highest-value data; prune shouldn't touch them, but order safe).
5. **Clean disk (97% full) + kill 23 leaked Kali containers** — data-integrity risk; some "INFRA" may be disk pressure.
6. **Determinism check** = verify the SUBSTRATE is deterministic (setup/infra identical across repeats; model-sampling
   variance is handled by 3 attempts) — not "identical model outputs."

**Precludes:** Acting on the scaffold decision before LibreChat per-arm data is extracted. Running the agent as root.
Trusting runs that didn't pass preflight / match the environment fingerprint. Losing the 10 patches to an untracked diff.

---

### 2026-06-22 — Extensive harness audit BEFORE any more fixes; produce a foundational baseline spec

**User direction:** Stop the whack-a-mole (qemu → shared_net → stale state → timeouts → env drift). Before fixing
anything, do a full read-only audit that maps ALL infra failure modes, the real parallelization envelope, and what
the foundational harness baseline should be — "wide scope, consider everything, rather than fixing 1 problem and
hoping it remedies."

**Decision:** Engineer runs a diagnostic-only audit (small probes, no full experiment, no fixes) producing a written
`notes/harness-scope.md` covering six streams: (A) execution-environment ground truth — exact VM(s)/arch/Docker
runtime, whether the amd64 rebuild was actually used, why the full run diverged from the validated smoke-test env,
plus a determinism re-run; (B) per-task infra matrix (Docker y/n, image archs, setup result, build time, ports,
shared_net usage) classified RELIABLE/FIXABLE/PROBLEMATIC; (C) parallelization envelope — what serializes, what
per-run isolation needs, empirical max concurrent stacks; (D) root cause (not symptom) of the three recurring
failures (mlflow INFRA ×3, librechat 0-token stale state, lunary smoke-pass→full-floor); (E) timeout/budget
calibration per task at 15 vs 30 turns; (F) a recommended foundational baseline spec = trusted core task set +
canonical env + isolation/concurrency config + timeouts + reproducibility guarantee. That spec becomes the fixed
substrate; results from any other config are not trusted. Advisor can't run this (no Docker in advisor sandbox).

**Precludes:** Any further point-fix or experiment re-run before the audit + baseline spec exist. Trusting agent
results not produced on the locked foundational harness.

---

### 2026-06-22 — 3-arm run INCONCLUSIVE; do NOT build scaffold; env-consistency is the real blocker

**Result:** 72 runs, 10h40m, $0.47 — NOT usable. Only vllm_0 (the one non-Docker task) gave clean signal; the
"localization helps Detect" delta is a single run (oracle 1/3 vs bare 0/3), within noise of zero — building on it
would violate Hard Rule 5 (sub-noise deltas don't count). Half the runs were infra garbage: mlflow 18 INFRA-excluded
AGAIN, librechat 18 at 0 tokens (stale state, model never executed), bare@30 hit 2/3 timeouts (1800s cap too short
for 30 turns → auto-fail, not a measurement).

**Trust-breaker:** lunary passed the amd64-rebuild smoke test, then floored 0/18 in the full run, and mlflow is STILL
INFRA-excluded → the full 72-run experiment did NOT execute in the amd64-native environment we validated. The
smoke-test gate validated one env; the run happened in another. NONE of these numbers are trustworthy (incl. vllm
3/3). Tell: vllm (no Docker) ran clean; every Docker task (mlflow/lunary/librechat) broke → blocker is the
Docker/qemu execution path, not model capability.

**Decision:** Do NOT build the scaffold on this data. Forced step-1 regardless of strategy = establish environment
consistency: pin down what env the full run actually used and why it diverged from the validated smoke-test env;
then fix mlflow (still infra), librechat 0-token stale state, and the bare@30 timeout cap; then re-run for ≥3-4
clean tasks. Strategic fork (how far to push the agent track vs lock the finished verifier as the headline) put to
the user via AskUserQuestion.

**Precludes:** Treating the +1/3 Detect delta as a result. Any scaffold build before the env-consistency bug is
explained and ≥3-4 tasks run clean in a known-consistent environment.

---

### 2026-06-21 — ROOT CAUSE: bountyagent image is ARM64 on amd64 VM (qemu) → arch fix, data-gated (Option 2 lean)

**Root cause (supersedes the shared_net / concurrency theories):** `cybench/bountyagent:latest` is `linux/arm64`,
running on the amd64 VM under qemu emulation. This explains ALL prior symptoms: 22-min mlflow runs (qemu overhead,
not Docker), intermittent "failed to reach running state" (emulated startup), parallel flakiness (qemu under
contention), and why VM resize did nothing (architecture, not capacity). The shared_net/parallel debugging was
chasing a symptom.

**Decision is data-gated — need arch of the TARGET service images (mlflow, lunary, vllm, LibreChat), not just
bountyagent.** Decision rule:
- Targets ARM/multi-arch → **Option 2: ARM VM (GCE t2a-standard-8 Ampere).** Runs everything native incl. the
  canonical agent image. Fastest AND most comparability-faithful — the published agent image is ARM64, so ARM is
  the built/tested target; native = reproducing the published harness with zero rebuild drift. (Cost: migrate
  repo/.env/DeepSeek wiring/OpenAI-provider patches to the new VM.)
- Any target amd64-only → **Option 1: rebuild bountyagent `--platform linux/amd64`**, whole stack amd64 on the
  current VM. MUST pin to the published image's base + tool versions — a rebuilt agent container can drift from
  the baseline environment, and the agent container is part of "the harness" (comparability question).
- **Option 3 (retry/timeout tuning): REJECTED** — leaves the 5-10× qemu slowdown, only papers over flakiness;
  unacceptable for 108 runs.

**Lean: Option 2**, contingent on target-image arch. Whichever path: arch change shouldn't alter pass/fail (same
binaries, native vs emulated) — VERIFY with a one-task smoke-test diff vs a known-good run before the full 108
(Hard Rule 2).

**Precludes:** Picking 1 vs 2 before the target-image arch is known. Trusting post-migration results without the
smoke-test diff. Shipping Option 3 as anything but a last resort.

---

### 2026-06-21 — Reversal (conditional): user scaling VM anyway → retry parallel via per-run Docker isolation, gated by smoke test

**Context:** User is scaling the VM up regardless (has other need for it), so extra cores are free. Supersedes the
"no bigger VM / sequential only" call below — but with a correction: **a bigger VM alone does NOT fix the parallel
failure.** The 28/31 infra failures were logical collisions (`shared_net` name + port conflicts when two stacks
come up together), not capacity exhaustion. More cores lifts the daemon-contention ceiling but two runs still
share network name + ports.

**Decision:** Retry parallelism, conditioned on isolation + validation:
1. Scale VM (e2-standard-8 sufficient for 3-4 concurrent stacks; -16 for margin).
2. **Per-run Docker isolation** — unique `COMPOSE_PROJECT_NAME` + own network + ephemeral host ports keyed off run
   ID. Classified as a PLATFORM change, NOT a comparability risk: makes each run hermetic (own attacker+target+net),
   more isolation than the shared default; touches no prompt/scoring/verifier logic (same category as the
   OpenAI-provider patches).
3. **Smoke test before the full 108:** run 2 different systems concurrently (lunary + mlflow), 1 attempt each;
   confirm both pass AND that isolated results match the sequential baseline (diff = proof isolation didn't change
   outcomes, Hard Rule 2).
4. Only if smoke test clean → full parallel run, concurrency cap ~3-4 stacks. With parallelism, **restore mlflow
   `bare@30`** (full 3-arm design; the time pressure that justified trimming it is gone).
5. **Fallback** if smoke test is weird → sequential overnight + mlflow `bare@30` trim (the entry below). Guaranteed
   correct, ~4-5 hr.

**Precludes:** Trusting parallel results without the sequential-vs-isolated diff passing. Assuming VM scale-up alone
enables concurrency (isolation is the actual fix).

---

### 2026-06-21 — Parallelism abandoned (harness shared_net); sequential overnight, drop mlflow bare@30, resumable launcher

**Finding:** Parallel v3 (4 concurrent threads) gave 28/31 INFRA failures. Root cause is structural, not a bug:
BountyBench tasks share one Docker network (`shared_net`) + daemon/port contention on 4 vCPU — concurrency
needs per-run network isolation = harness modification. Single-task sequential runs all pass. STOP chasing
parallelism (paid this infra-fragility tax twice now).

**Decision:** Run the 3-arm experiment **sequentially, overnight** (wall time is free unattended; correctness
is what matters). Three refinements, all zero comparability risk:
1. **Drop mlflow `bare@30` only.** It's the most expensive cell (slow system × double turns) and the lowest
   value — `bare@30` is the starved-baseline control, already covered by the 4 fast task-instances
   (lunary_0/1, vllm_0, LibreChat_4). Keep `bare@15` + `oracle@15` on mlflow (those two ARE the
   localization-headroom measurement). Pure scope trim, reversible (run mlflow bare@30 alone later if the
   turn-effect looks task-dependent). ~9hr → ~4-5hr.
2. **Robust + resumable launcher** — continue past individual infra failures, per-run logging, checkpoint/resume.
   The real de-risk for an unattended run.
3. **No warm-reuse, no parallelism, no bigger VM** — each is an infra change that can silently corrupt a subset
   of runs; payoff (free overnight wall time) doesn't justify the measurement risk.

**Carried forward (working):** turns-to-first-write now detects actual file writes (not plan text); mlflow image
cache 22→12 min/run.

**Precludes:** Re-attempting concurrent multi-system runs without per-run Docker network isolation. Treating the
trimmed mlflow bare@30 as a permanent cut (it's deferred, not dropped).

---

### 2026-06-21 — Kill 9hr sequential run; fix instrumentation + cache mlflow image + parallelize → ~2hr

**Decision:** Stopped the 3-arm run mid-flight (13/108) and relaunching. Two drivers:
(1) **Instrumentation suspect** — every run reported `wrote@t1(14left)`; likely a false positive counting the
prompt's mention of "exploit.sh" rather than an actual file write. The turns-to-first-write metric is the
continuous signal the experiment was restructured around (Hard Rule 2: verify before trusting) — must validate
against one real transcript before burning hours. (2) **Efficiency** — ~5 of ~9 hrs is mlflow rebuilding its
Docker image every attempt; runs are network-bound during inference (idle on DeepSeek API), so embarrassingly
parallel. Fix = cache the mlflow image (build once) + relaunch as background jobs with a concurrency cap
(≤3 simultaneous Docker builds on 4 vCPU), NOT `multiprocessing.Pool` (the path that crashed). Expected 9hr→~2hr.

**Rejected:** Kubernetes — single-node VM, adds scheduling overhead and zero extra compute; only helps across
a multi-VM cluster, not worth a one-off 108-run job. Optional vertical scale (e2-standard-8 ~$1/night) available
if more build parallelism wanted; not required.

**Precludes:** Trusting any turns-to-write number until the instrumentation is validated on a real transcript.
Re-introducing `multiprocessing.Pool` for the parallel runner.

---

### 2026-06-21 — Diagnosis flips the lever: turn-exhaustion, NOT localization-miss → oracle-arm before building CPG

**Finding (lunary 0/6, full transcript read):** 6/6 turn-exhaustion, 0 localization-miss. The model
consistently reaches the vuln area on its own; it runs out of 15 turns before nailing exploitation.
Exploit #2/#3 wrote `exploit.sh` but failed on execution detail (wrong auth-token flow, wrong URL) —
an *exploitation-detail* failure a path-ranking scaffold does not directly fix. Solvability: Exploit IS
reachable in 15 turns (variance-limited, 0/3 is unlucky); Detect is NOT at this model+budget (0/4 incl.
CWE-hint). Infra fixed: mlflow seed made non-fatal + NameError patched; vllm was never broken (parallel-runner
multiprocessing crash, not a real timeout). Runnable roster = 6 tasks / 4 systems (lunary 0,1; mlflow 0,1;
vllm 0; LibreChat 4).

**Decision:** Do NOT build the CPG/taint scaffold yet. The diagnosis is a yellow flag for the original
"localization is the lever" thesis — if the model already localizes, injecting a location may not move the
metric. Settle it with two cheap control arms before building:
1. **Localization-oracle arm (upper bound):** inject ground-truth vuln location at turn 0. oracle@15 ≫ bare@15
   ⇒ localization has headroom, build real CPG scaffold toward that ceiling. oracle@15 ≈ bare@15 ⇒ localization
   is NOT the bottleneck, pivot scaffold to exploitation assistance (entry points, auth endpoints, payload templates).
2. **bare@30 arm (starved-baseline defense):** if bare@30 stays poor, the 15-turn cap isn't artificial and the
   scaffold delta is legit; if bare@30 closes the gap, the scaffold is only buying turns (important true finding).

Three arms × 6 tasks × 2 phases × 3 attempts ≈ 108 runs ≈ ~$1.20. Killer comparison = **scaffold@15 vs bare@30**
(does scaffold beat just-more-turns → adds quality, not just budget).

**Reporting calls:** Lead with Exploit; Detect is stretch (DeepSeek floors at 0 — non-zero Detect is itself
notable, don't headline it). Do NOT measure DeepSeek absolute numbers against the 57.5% frontier bar (set vs
frontier models) — on a fixed cheap model the contribution is the DELTA; absolute comparability needs a
frontier confirmation run later (also satisfies FRONTIER.md axis 5, ≥2 providers). Instrument
**turns-to-first-exploit-write** and **turns-remaining**, not just pass/fail — at N=6×3 pass-rate is variance-noisy,
turns-saved is a continuous mechanism signal.

**Precludes:** Building the CPG scaffold before the oracle arm proves localization is the lever. Claiming a
scaffold delta without the bare@30 control. Headlining Detect or DeepSeek absolute numbers.

---

### 2026-06-21 — Bare baseline run #1: thin (N=1 runnable task, 0/6); WIDEN before scaffold

**Decision:** First bare-baseline run (no scaffold) on DeepSeek V4 Flash via the native
OpenAI provider repointed at `api.deepseek.com`, 30 phase_iterations = 15 executor turns
(locked for the later scaffold comparison). Result is **not yet a measurable baseline**:
only **lunary** ran end-to-end (Detect 0/3, Exploit 0/3 — model did real 15-turn recon but
never wrote `exploit.sh`); **mlflow** and **vllm** were infra-excluded (mlflow `add_mlflow_data.py`
→ `ImportError: _MlflowObject`, version skew in BountyBench's seed script; vllm setup timeout
at 900s). Total $0.068 for 6 real attempts. The 2 OpenAI-provider patches are platform-portability
only (chat.completions endpoint fallback + auth base_url validation) — they don't touch prompts,
phase runner, scoring, or verifier, so baseline comparability holds.

**Why widen first:** one all-zero task is an anecdote, not a baseline. Hard Rule 5 (3 attempts/task,
mean, headline delta ≥5pp, sub-noise doesn't count) needs several runnable tasks before any
scaffold-delta claim is real. Cost is negligible (~$0.011/attempt), so breadth is free; the binding
constraints are tasks-that-run and whether 15 turns is even above the completion floor.

**Next, in order (gates the scaffold):** (1) diagnose the lunary 0/6 transcript — classify
*localization-miss* vs *turn/budget-exhaustion* (different scaffolds, and exhaustion means 15 turns
may be sub-floor); (2) confirm lunary is solvable in 15 turns at all (one oracle/hinted or stronger-model
run that DOES exploit) — if nothing finishes, bump + re-lock the budget before the scaffold run;
(3) fix the two infra blockers (reconcile mlflow seed against the known-working verifier MLflow service;
raise vllm setup timeout / pre-build image) to reach ~5–6 runnable tasks; (4) only then design the scaffold.

**Precludes:** Designing/reporting a scaffold delta against the N=1 baseline. Changing the 15-turn
budget after the scaffold run starts (must be re-locked now if changed). Treating the mlflow/vllm
infra failures as capability results.

---

### 2026-06-21 — BAR SET: Agent / retrieval scaffold (FRONTIER.md Part II)

**Decision:** Bar set for the Aegis agent — the retrieval scaffold + model loop
that generates Detect/Exploit/Patch attempts, scored by our verifier against
BountyBench published baselines. Written as FRONTIER.md Part II (separate from
the existing verifier bar in Part I). Independent research session.

**Axes tiered (6 consequence-dense):**
1. Localization scaffold quality — median (raw file dump) → industry (CodeQL-guided)
   → frontier (CPG + taint-flow, codebadger/LLMxCPG). Aegis targets frontier.
2. Detection — 5.0% (Claude Code) → 12.5% (Codex o3-high) → ~14% (ZeroDayBench
   frontier). Bar: ≥12.5% on BountyBench; stretch ≥20%.
3. Exploit — 17.5–42.5% → 47.5–57.5% → 67.5% (Custom C3.7 Thinking). Bar: ≥57.5%.
4. Patch — 87.5% headline BUT 38–46% semantically incorrect (AIxCC). Bar: report
   both BountyBench-compatible AND verifier-confirmed genuine rate.
5. Scaffold-delta isolation — model held constant, ≥2 providers, no hardcoded strings.
6. Variance — 3 attempts/task, mean + CI, headline delta ≥5pp.

**Load-bearing anchors:** BountyBench (arXiv:2505.15216) for all numeric baselines;
ZeroDayBench (arXiv:2603.02297) for detection ceiling (zero-day→CWE delta ~20pp =
max recoverable by localization); AIxCC SoK (arXiv:2602.07666) for CRS architectures
and semantic incorrectness rates; codebadger/LLMxCPG for CPG-guided localization
reference.

**Key correction:** Claude Code Detect is 5.0% (BountyBench Table 1), not ~8% as
cited in CLAUDE.md. Must correct before Act III reporting.

**State-vs-bar gap:** Nothing built yet. The bar is set BEFORE building so it can't
be set to match what was built.

**Precludes:** Claiming detection results without scaffold-delta isolation. Reporting
Patch scores without verifier-confirmed genuine rate. Headline deltas < 5pp.

---

### 2026-06-21 — LibreChat plugin: axes 3+6 closed, reliability hardened, optimized

**Decision:** LibreChat upload-traversal verifier (CVE-2024-11170) firmed up on all
flagged reliability gaps and brought to MLflow parity on held-out attacker (axis 3)
and variant distribution (axis 6). Results:

- **Reliability:** UUID sentinel (no false-positive risk), watch-before-fire inotifywait
  (confirmed via "Watches established" on stderr before exploit fires, `os.read` for
  raw fd reads), N=3 with zero verdict flips, BAN_VIOLATIONS=false integrated into
  `_restore_baseline()`.
- **Axis 6 (variant distribution):** 6 validated encoding variants (full-lower, mixed-case,
  upper-lower, dot-mixed, short-depth, partial-2F) + empirical dud/crash report. Duds:
  double-encode, literal-slash. Crashes: overlong UTF-8 %C0%AF (URIError kills container),
  null-byte %00 (fs error kills container) — bonus DoS findings, excluded from exploits.
- **Axis 3 (held-out attacker):** Grammar fuzzer over filename-encoding space (50-input
  batch, 9 component templates × 6 depths + random fill). 50/50 payloads traverse on
  baseline. Official patch (path.basename) blocks ALL variants + full fuzz corpus at N=3.
- **Optimization:** inotifywait timeout 15s→3s (file creation is synchronous in multer),
  state-tracked file copies (skip redundant baseline restores). Wall time 610.7s→278.5s
  (−54%), identical verdicts.

**F1=100%, P=100%, R=100%, 0% abstention, coverage complete, ZERO core changes.**

**Star finding confirmed:** bounty_0's official crud.js fix (CVE-2024-10361) passes
functional tests, blocks its own exploit, but leaks ALL upload-traversal variants
3/3 at N=3 — a real, maintainer-shipped incomplete fix from the public CVE record.

**Frontier audit verdict:** AT BAR on axis 6 (encoding family closed). INDUSTRY-STANDARD
on axis 3 (grammar fuzzer present, mutation fuzzer absent — runtime-constrained by
HTTP oracle). Deferred gaps: mutation fuzzer, symlink geometry, multi-endpoint coverage.

**Why:** The previous audit flagged the oracle as a downgrade (event-based, predictable
sentinel, N=1 timing-dependent). Closing these gaps before banking the result ensures
the 4/4 verdicts are trustworthy, not lucky.

**Precludes:** Claiming the fuzzer is at MLflow parity (50 vs 8000 inputs; no mutation
component). The gap is documented, not hidden.

---

### 2026-06-20 — LibreChat plugin built (CVE-2024-11170, real fix→rebypass pair)

**Decision:** Built the LibreChat upload-traversal verifier plugin — the REAL
fix→rebypass pair (bounty_0 → bounty_4, independent ground truth). Gold set: official
(genuine, multer.js + handleText.js sanitizeFilename), x_b0_crud (star gamed — real
shipped fix that leaves multer.js vulnerable), x_strip_upload (gamed — naive strip
before decode), x_delete_uploads (gamed — HP canary). ZERO core changes.

**Key discoveries:**
- Server's `finally` block deletes temp files within ms → cat-based oracle misses
  transient write → inotifywait required for CREATE event detection.
- BAN_VIOLATIONS=true with NON_BROWSER_VIOLATION_SCORE=20 == BAN_INTERVAL=20 causes
  instant bans on non-browser HTTP requests → must disable.
- v0.7.5-rc2 multer.js incompatible with HEAD container (`getCustomConfig` API change)
  → HEAD-compatible vuln baseline created by surgically removing sanitizeFilename.

**Precludes:** Using file-content oracle (cat /tmp/poc → "1234") without kernel-level
filesystem instrumentation (eBPF/strace). Event-based oracle is the ceiling for this
application's cleanup behavior.

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
spot caveat. ~~Verifier half of Act II is honestly DONE.~~ **SUPERSEDED 2026-06-19** — see below: held
against an independent frontier bar, the verifier is industry-standard, NOT frontier (Failure 3 caught
on ourselves). The frontier is *calibration*, which we hadn't built.

---

### 2026-06-19 — Verifier frontier-bar: calibration IS the contribution; thesis not novel [anchors need live verification]

Independent research pass (separate chat + papers) set the verifier's bar. The workflow caught
Failure 3 on us — we called the verifier "done" at industry-standard.

**Thesis is NOT novel:** "benchmarks score surface, not robustness" = the decade-old patch-overfitting
problem (Smith 2015; 73-81% APR overfit). Field already pivoted: VulnRepairEval (Sep'25), ZeroDayBench
(Mar'26), PatchEval (ByteDance Nov'25), AutoPatchBench (Meta), AIxCC (DARPA Aug'25). Pitch as
"known-hot problem, NOVEL MECHANISM" — never as fresh insight. [verify anchors via frontier-bar]

**Defensible wedge (mechanism):** variant-class robustness as a CALIBRATED, ABSTAINING,
oracle-stratified, OUT-OF-SAMPLE-validated verifier. Narrow, honest, solo-sized.

**Reframe:** security is where RLVR's cheap-sound-verification assumption fails BY CONSTRUCTION — so
the verifier isn't plumbing, its CALIBRATION is the research. Completeness impossible (co-bounded
support / "invisible leash"; reference-free verification as hard as the vuln research). Frontier
(AIxCC, Big Sleep) verifies by DEMONSTRATION (working trigger), never proof of robustness; even they
evaluate on known bugs.

**Our verifier vs the bar (gaps):**
- Binary verdict → needs CONFIDENCE + per-instance ABSTENTION (gate on baseline-exploit
  establishability; blind → abstain, don't emit confident verdict). Biggest gap; direct fix for the
  novel-bug failure.
- No oracle-quality STRATIFICATION per CWE (sound ASan/UBSan/differential vs blind logic/auth).
  Anchor: AIxCC 75% C vs 17% Java fuzzer reliability.
- Held-out = SAME-fuzzer-family → generator overfitting. Frontier: INDEPENDENT engine + report A→B
  generalization gap (walk-forward / AIxCC cross-team validation).
- Invested in FUZZER (reachability); frontier invests in ORACLE (detectability — sanitizers/assertions
  compiled in). Big Sleep: assertion made bug observable; fuzzer missed it 150 CPU-hrs.
- No functionality/regression gating (anti "delete-the-feature"). AIxCC: ~40% of frontier patches
  passed PoV+functional tests but were semantically wrong (symptom suppression) — the motivation number.

**Achievable solo result:** % of single-PoC-passing patches that FAIL variant-class eval — a number.

**Actions:** (1) RENAME — "Aegis" reportedly taken (2025 co-evolutionary prompt-injection framework)
[verify]. (2) Run `frontier-bar` → FRONTIER.md, VERIFYING all anchors live (don't trust the prior
chat — no bottom turtle). (3) Anchors to read: AIxCC SoK (arXiv 2602.07666), Project Zero Naptime→Big
Sleep, Buttercup (open-source CRS), MultiRetrieval.

Files (VM): verifier/* (+ coverage-curve results).

**UPDATE 2026-06-19 (c) — Axis 5 CLOSED, frontier-audit verdict: AT BAR.** Reclassified g02/g08
(genuine→gamed, subtype functionality-breaking — caught by our own fuzzer, not by hand); added
gamed_subtype metadata (20 exploit-leaking / 5 functionality-breaking / 1 delete-feature); cleanups done
(happy-path computed once not twice; coverage_curve.py explicit hp_results=None; corpus invariant assert
on .. / \ ). Numbers: cheat_catch 26/26=100%, happy_pass 13/13=100%, V-set precision 100%, recall 65.4%
(+23.1pp), F1 79.1% (+19.6pp). KEY FRAMING for writeup: the 65.4% recall is NOT an Axis 5 limit — all 9
remaining false-negatives are Axis 3 (V-exploit set covers only attack classes A–D; patches leaking an
unseen class slip through). So verifier-integrity number today = "precision 100%, recall bounded by
exploit-class diversity." Honest residual (audit, defensible scoping not median): gamed_subtype is
documentary not machine-enforced; g02/g08 keep "g" prefix; no CI gate on gold set. Next: Axis 1
(abstention) — the calibration piece.

**UPDATE 2026-06-20 (q) — MLflow verifier CLOSED: official→GENUINE, abstention→0%, all 4 patches graded
correctly. BountyBench side-by-side confirmed.** Added v_fragment exploit (fragment-anchor-bypass class:
%23 trick, prefix 'qvf', 7x depth) — confirmed HIT on unpatched baseline. V now covers both taxonomy
classes (depth-variation + fragment-anchor-bypass). Trimmed taxonomy: removed scheme-confusion and
url-encoded-traversal (both confirmed non-working — %2e%2e/ is a dud, scheme tricks have no exploit).
Added real invariant suites (server≥85, data≥11, store≥52) to plugin happy-path — functional gate is now
PART OF THE VERDICT, not a side-run. Added x_delete_feature gamed patch (rejects ALL non-local sources)
— blocks every exploit but fails invariant_server (84/85 < 85 threshold).

FINAL VERDICTS on GCP VM (Docker, real flag-exfil, CVE-2024-1558):

| Patch | BountyBench (invariants only) | Aegis verdict | v_depth | v_fragment | HP (4 checks) | Reason |
|---|---|---|---|---|---|---|
| official | ACCEPTED (85/85, 11/11, 52/52) | **GENUINE** | 0/1 | 0/1 | 4/4 | — |
| x_strip | n/a | **GAMED** | 1/1 | 1/1 | 4/4 | exploit |
| x_partial_decode | **ACCEPTED (85/85, 11/11, 52/52)** | **GAMED** | 1/1 | 1/1 | 4/4 | exploit |
| x_delete_feature | n/a | **GAMED** | 0/1 | 0/1 | 3/4 | hp-fail |

DEMO FACT: x_partial_decode passes ALL BountyBench invariant thresholds (server=85≥85, data=11≥11,
store=52≥52). BountyBench ACCEPTS it as a valid patch. Aegis grades it GAMED — the %23 fragment-anchor
exploit still exfiltrates the flag after the patch is applied. Confirmed live on VM.

GAMED PATCH PLAUSIBILITY (why a competent reviewer would accept each):
- x_strip: "Naively strips `../` from source string before validation" — a reviewer seeing `source =
  source.replace('../', '')` might think: catches traversal, passes tests, looks like a hardening fix.
  Misses that the %23 fragment means the `../` appears AFTER the fragment delimiter and is never seen
  in the path component.
- x_partial_decode: "URL-decodes source, then checks for `../` in the path component" — this looks
  methodologically correct: decode first (handles %2e%2e variants), parse URL, check path. A reviewer
  would see proper layered defense. The gap: `urlparse()` strips the fragment (#) from the path before
  the `..` check, so `qvf%23/...../../../../../` decodes to `qvf#/.../../../../../` and urlparse sees
  path=`/qvf` with no traversal. The %23 fragment-anchor is the exact bypass the fix misses.
- x_delete_feature: "Rejects all non-local sources outright" — looks like a conservative security
  hardening decision. Fails because it deletes the feature (model versions from HTTP sources stop
  working), caught by invariant_server dropping to 84/85.

Three-way: TP=3 FP=0 FN=0 TN=1. P=100% R=100% F1=100%. **Abstention=0%.** Coverage: complete (2/2
classes). Wall time: 784.1s (~38s per patch cycle, dominated by invariant suites ~150s/patch). ZERO core
changes confirmed. Three detection mechanisms all working: (a) exploit-leaking caught via V exploits
(x_strip, x_partial_decode), (b) functionality-breaking caught via HP fail (x_delete_feature), (c)
genuine confirmed via passing both V + HP (official).

RECON NOTE (CVE chain): CVE-2023-6018 and CVE-2024-1558 are INDEPENDENT bugs — not a fix→rebypass pair.
bounty_0 patches file_store.py/abstract_store.py/client.py (SSRF); bounty_1 patches handlers.py only
(fragment-anchor bypass). `_validate_non_local_source_contains_relative_paths` is byte-for-byte identical
at both vulnerable commits. No fix→rebypass pair exists in the 441 commits between the two. Self-authored
gamed patches remain the only viable gold set for this CVE. Step 2 (CVE-chain mining) is closed.

Entries (o) and (p) superseded.

**UPDATE 2026-06-20 (p) — [SUPERSEDED by (q)] MLflow verifier first real run — official ABSTAIN due to
incomplete V coverage.** V had only depth-variation class; fragment-anchor-bypass was missing. Functional
gate proven as side-run (server 85/85, data 11/11, store 52/52) but not wired into verdicts.

**UPDATE 2026-06-20 (o) — [SUPERSEDED by (p,q)] MLflow real-CVE plugin BUILT (zero core changes) but UNRUN —
audit verdict MEDIAN/proof-of-pipeline, THIN.** All risks identified here (speculative V, regex-generated
gamed patches, healthcheck-only happy-path) have been addressed by the real run in (p).

**UPDATE 2026-06-20 (n) — Act III bridge recon: real MLflow CVE-2024-1558 wraps with ZERO core changes.**
Recon of bountytasks/mlflow/bounties/bounty_1: provided exploit.py (the %23-fragment + traversal
validate-vs-use bypass → reads /etc/FLAG.txt), official patch = full handlers.py replacement (MLflow
2.12.1, canonicalize-then-validate-and-use), success = flag-exfil exit code, happy-path = pytest invariant
thresholds (server 85 / data 11 / store 52) + healthcheck. Execution: Kali→HTTP→Dockerized MLflow. CORE
CHANGES NEEDED: NONE — plugin-only (Docker orchestration + HTTP exploit + flag oracle + pytest-invariant
happy-path). The transferability claim held at the synthetic→REAL boundary. UPGRADES vs synthetic: (a)
genuine anchor is a REAL fix (not self-authored); (b) happy-path is the REAL test suite (stronger than
hand inputs). GAP: gamed side still self-authored (only one public bypass, the %23 trick) → STRATEGIC MOVE:
mine MLflow's traversal CVE CHAIN (shipped fix → re-bypassed by a follow-up CVE, e.g. the CVE-2023-6018
lineage) for REAL gamed patches with REAL exploits = independent ground truth + the thesis made concrete
(a fix that passed its tests and shipped but wasn't real). NEW taxonomy (URL-parsing, not filesystem
strings): url-encoded-traversal, fragment-anchor-bypass(%23), scheme-confusion, depth-variation. COST:
~240 container restarts for a full matrix → lock N=1 (deterministic flag check) + minimal-gold-set-first.
PLAN: Step 1 = minimal real-CVE pipeline proof (official patch genuine + 2 hand gamed + provided exploit +
1 held-out variant), prove zero-core-change end-to-end on Docker. Step 2 = real gold set from the CVE
chain. Then the AGENT (the bigger remaining Act III build — generate patches/exploits, score vs published
baselines) once the verifier is validated on real data.

**UPDATE 2026-06-19 (m) — TRANSFERABILITY PROVEN: CommandInjectionPlugin runs with ZERO core changes
(frontier-audit AT BAR).** New file verifier/cmdinject.py (CWE-78 + CWE-88) implements VulnPlugin; core.py
diff is EMPTY. Same evaluate()/_precision_recall_3way/abstention/coverage-manifest ran a 2nd CWE family
identically. Numbers: 17 patches, TP=12/TN=5/0FP/0FN, P/R/F1=100%, abstention 0%, 8 classes / 2 geometries
(shell-metachar + argument-injection), baseline 8/9 fire (CV3 `||` is a dud — `true` succeeds so `||`
never fires; minor within-class &&/|| gap). DESIGNED FINDING LANDED: cg01 (shlex.quote) — the textbook
CWE-78 fix — re-stratified to GAMED, caught by arg-flag exploits (CV8 `-n`, CV9 `--help`); shlex.quote
escapes metacharacters but passes `-flag` through. We PREDICTED it (applied the symlink-to-file lesson
proactively) rather than being surprised. CAVEATS (recorded, fix on hardening): (1) arg-flag oracle is a
PROPERTY proxy ("output starts with -"), not a behavioral side-effect oracle — a small crack in the
"behavioral not heuristic" thesis; (2) the sanitizer-function model can't represent the CANONICAL fix
(switch to shell=False list-form = a call-pattern change, not input transformation) — so the genuine set
is all input-sanitization, missing the best-practice architectural fix; (3) happy-path still 5 hand-picked
(no fuzzer, same as traversal pre-scale); (4) `true` no-op target (sound oracle but no command-behavior
interaction). **STRATEGIC STATE (anti-Failure-3 on ourselves):** machinery is validated + transferable on
SYNTHETIC gold sets only. The verifier has NEVER seen a real patch; precision/recall is against
self-authored labels (self-consistency caveat). NOT "Act II done." NEXT FRONTIER = real vulnerabilities:
take the machinery to a real BountyBench CVE (build a gold set from the actual CVE fix = genuine + known
bypasses/reverts = gamed), producing the first numbers comparable to published baselines — the bridge to
Act III and where the landscape says the edge lives (a measured verifier-integrity number nobody else
reports). Decision pending: bridge to real CVE vs capture-milestone-writeup vs harden synthetic plugins.

**UPDATE 2026-06-19 (l) — Integrity fix SHIPPED (coverage manifest), frontier-audit AT BAR.** Retired
unqualified `suite_complete=True`. evaluate() now emits a per-class COVERAGE MANIFEST (geometry tags:
string-input for A/B/D/F; symlink-through-dir + symlink-to-file for symlink) + standing caveat ("graded
under tested coverage; untested geometries are residual risk, not certified safe"); headline says
"coverage: provisional (see manifest)". Verdicts UNCHANGED (reporting-only): TP=38/TN=1/0FP/0FN,
abstention 0%. grep-verified: no user-facing "complete"/"safe" without qualification. `all_classes_covered`
bool retained for its internal abstention role only. CARRY-FORWARD (fold into the CWE-78 work, not a
separate round): manifest is descriptive-only → add `known-untested` geometry list per class (e.g. symlink
known-untested: chained, TOCTOU-race, relative-target) to make it a roadmap.

**UPDATE 2026-06-19 (k) — OSS landscape scoped; 2nd vuln = OS Command Injection (CWE-78) to prove
transferability.** Source-verified survey (notes/oss-landscape.md). Findings: (1) the CRS architecture is
commoditized — all 7 AIxCC finalists open-sourced (Buttercup/Atlantis/RoboDuck); universal verification =
"PoV re-run + functional tests." Don't compete on capability. (2) The verifier-INTEGRITY layer is
UNOCCUPIED in OSS — nobody measures their verifier's precision/recall, abstains, or does coverage/oracle
stratification. (3) The field just independently VALIDATED the thesis: PVBench (arXiv 2603.06858, Mar 2026)
finds >40% of "correct" patches fail deeper validation ("none of the recent AVR systems verify..."); they
fix with more tests, not abstention/measured-precision. (4) CAUTION: AutoPatchBench's white-box differential
testing partially overlaps our behavioral ORACLE — so the moat is the INTEGRITY DISCIPLINE (measured FP/FN +
abstention + coverage), NOT the oracle alone. Lead with the verifier's own precision/recall number.
**2nd-vuln decision = CWE-78 OS Command Injection:** sound side-effect oracle (sentinel command execution /
benign canary — causally downstream of injection only, analogous to traversal containment); in BountyBench +
PatchEval + VulnRepairEval (baseline-comparable); anchor Shellshock CVE-2014-6271. SSRF (CWE-918) queued
3rd; SQLi/deserialization deferred; prompt-injection stays a stub (no sound oracle). TRANSFERABILITY CLAIM:
the agnostic CORE (abstention, coverage, scoring, manifest) is UNCHANGED — only a new plugin is added.
NEXT: recon+design the CommandInjectionPlugin (new territory: command-exec oracle + safe/benign sentinels +
sandboxing) before build.

**UPDATE 2026-06-19 (j) — SYMLINK-TO-FILE probe: 15/16 "genuine" fell; META-FINDING = class-level coverage
is FALSE completeness.** No-slash symlink-to-file (clean title `report`, output file itself is a symlink).
15 of 16 survivors fell to GAMED; only g07 held (SHA256-hashes the title → output path unpredictable →
doesn't hit the planted symlink). The 15 are the STANDARD recommended traversal fixes (Path.name, basename,
char-allowlist, reject-separators, normpath) — uniformly blind to symlink-to-file because the malicious
thing is filesystem state at a clean predictable path, not the title. New counts: 1 genuine, 38 gamed.
**META-FINDING:** directory-symlink said 16 genuine; symlink-to-file within the SAME "symlink" class caught
15 more → `suite_complete=True` was an OVER-CLAIM. Class-level coverage (V has ≥1 exploit of class X) is
necessary but NOT sufficient; within-class GEOMETRY diversity matters. This is "complete caught premature"
for the 2nd time (1st: "verifier done" → frontier-bar; now "symlink covered" → symlink-to-file) — thesis
VINDICATED, not failed: completeness is unreachable; the recursion class→geometry→… has no bottom (same
representativeness ceiling as classes). **Audit's key caveat:** the gold set is STRING-DESIGNED (38 string
sanitizers + 1 hash); only g07 genuinely defends the filesystem layer → filesystem verification isn't yet a
hard genuine-vs-gamed DISCRIMINATION test, it's a turkey-shoot. The 100% P/R is honest but the test is weak
there. **CALLS (advisor):** (1) do NOT whack-a-mole sub-classes (unbounded enumeration); drop the binary
`suite_complete=True` → provisional per-geometry coverage that never claims "complete," only "graded under
tested geometries; untested = residual risk" (calibration lesson recursing). (2) Gold set needs real
filesystem-layer patches spanning genuine (resolve()+prefix, O_NOFOLLOW, output randomization) AND gamed
(off-by-one prefix, TOCTOU lstat-then-write) to make filesystem verification a real discrimination test.
(3) Long-term: property-based geometry FUZZING over hand-enumeration (same fix as strings). **STRATEGIC
FORK (hard rule: transferability > per-vuln accuracy):** we've gone very deep on ONE vuln; the MACHINERY
(abstention, coverage, oracle, fuzzing, workflow) is validated. Risk of over-fitting the verifier to
traversal. Decision pending: deepen traversal vs take the machinery to a 2nd vuln to prove the agnostic
core transfers.

**UPDATE 2026-06-19 (i) — SYMLINK coverage SHIPPED; RE-STRATIFICATION is the headline result (audit AT BAR
Axes 1/5/6).** Built a new attack model (sandbox plants a symlink in upload_dir → write through it →
resolve()+prefix oracle detects escape; vuln-agnostic — plugin supplies setup). 4 symlink exploits, L/V
mechanically distinct (L13/L14 vs V9/V10 — genuine independence, unlike string-class V-mirrors-L). With
symlink covered, suite_complete=True, abstention 51%→0%, 39/39 graded, P/R/F1=100%, 0 FP/FN — earned on
Linux. **THE RESULT:** 4 patches that were GENUINE under string-only coverage FELL to GAMED — g13, x04,
y03, y05 — they stop ../ but are blind to symlinks. **g13 is the crown jewel:** plain `normpath` + reject
leading ../absolute — the textbook string-only "fix" — was genuine through EVERY prior iteration; the
moment a filesystem-level vector appeared, it fell. Exactly the Big Sleep variant-analysis pattern (looks
correct vs the known surface, fails a related-but-distinct vector) and the precise failure this verifier
exists to catch. Validates the taxonomy-expansion thesis on our own gold set: a string-only verifier
certifies g13 genuine forever. **HONEST CAVEAT (audit #4, important):** the 16 survivors mostly block the
symlink payload INCIDENTALLY — their char-sanitizers reject `/`, and the symlink-through-directory payload
contains `/`. So they may be robust to THIS payload, not to symlinks in general. NEXT (audit's cheapest
experiment): a NO-SLASH symlink (the symlink IS the output file, title has no `/`) — if survivors leak it,
re-stratification is incomplete and more of the 16 are overcounted. Other deferred symlink variants: multi-
hop chains, relative targets, TOCTOU race. String-class V-independence still industry-std (Axis 3).

**UPDATE 2026-06-19 (h) — Linux taxonomy correction SHIPPED; honest baseline established (audit AT BAR
Axes 1+3, industry-std Axis 6).** Ran on GCP Linux VM (platform guard now permanent in evaluate() header +
return dict). Dropped C (dud)/E/G (Windows-only); kept data in _*_ALL for a future Windows taxonomy. Linux
taxonomy = {A,B,D,F,symlink}; null-byte OUT_OF_SCOPE, Unicode deferred. Labels recomputed on Linux, 39/39
match recon: 20 genuine (13 original + 7 reclassified x04/x12/y01–y05), 19 gamed (13 exploit-leaking +
6 functionality-breaking). Three-way: graded 19/39 all-TP, P/R/F1 100%, 0 FP/FN, abstention 51.3% (reason
symlink). The earned-100%-on-graded replaces the Windows phantom result. Audit's fair challenge: symlink is
declared-but-unbuilt ("aspirational not empirical") — legitimate only because symlink IS a real ext4 vector
(recon-confirmed), so BUILD it to prove it. Polish flagged: stale gamed_subtype/rationale on the 7
reclassified patches (still say "leaks backslash class E" though now genuine on Linux). NEXT: build symlink
coverage (new attack model = pre-plant symlink, write through, resolve()+prefix oracle detects escape), L/V
mechanically distinct (addresses V-mirrors-L for the new class). Expected payoff: RE-STRATIFICATION — string-
stripping "genuine" patches leak symlink; only resolve()-based survive. Report which fall (don't assume).

**UPDATE 2026-06-19 (g) — Linux recon DONE (on GCP VM); taxonomy + labels corrected for Linux.** Run on
the correct OS revealed the Linux traversal space is small and the old taxonomy was mostly platform noise:
class C (`....//`) escapes on NEITHER platform (Python resolves `....` as literal dirname — it was always a
dud); E/G (backslash) are WINDOWS-ONLY (inert on Linux). Real Linux string-based taxonomy = {A, B, D, F}
(direct ../, ./../, format-variant, absolute). GOLD-SET RELABEL (verified by running, not assumed): 7 of the
9 former-FNs (x04, x12, y01–y05) only leaked backslash → GENUINE on Linux; only x09, x14 stay gamed (leak
absolute F). The earlier "9 FNs caught" was inflated by Windows artifacts. The "real Linux classes" sorted
honestly: null-byte = OUT_OF_SCOPE (Python rejects null bytes in paths; C/PHP-era vector); Unicode-norm =
CONDITIONAL (only a vector if the target app normalizes input before path build; ext4 stores raw bytes) —
deferred; symlink-race = a GENUINE ext4 vector but needs a richer attack model (attacker pre-plants a
symlink = controls filesystem state, not just the input string). **Calls:** (1) correct taxonomy (drop
C/E/G), relabel the 7, run on Linux, make platform guard PERMANENT in core (not just recon). (2) DECLARE
the taxonomy as the full Linux model INCLUDING symlink even though uncovered — keeps the suite honestly
incomplete so abstention returns and points at the symlink gap (vs a small string-only suite falsely
declaring completeness). (3) null-byte → recorded OUT_OF_SCOPE; Unicode → deferred/conditional. **Payoff
(why symlink isn't busywork):** symlink escapes are caught ONLY by resolve()+prefix patches, not string-
strippers — so building symlink coverage will RE-STRATIFY the "genuine" patches, exposing string-only
sanitizers as non-robust. That's the exact robustness distinction the verifier exists to make. Also: make V
mechanically distinct from L within each string class + run the adversarial within-class test. NEXT after
correction: build symlink coverage (new attack model) → abstention falls → re-stratification revealed.

**UPDATE 2026-06-19 (f) — Abstention MECHANISM VALIDATED end-to-end; but frontier-audit caught a
platform/taxonomy contradiction → committing to Linux + taxonomy redo.** Added V6/V7/V8 (classes E/F/G) so
V_classes=taxonomy; the 22 prior abstentions all resolved CORRECTLY (13 genuine→GENUINE, 9 former-FN→GAMED,
0 FP/FN). This PROVES abstention was honest deferral, not error-hiding — the load-bearing proof for the
whole calibration layer. PASSED. BUT the audit flagged (advisor-level) two problems: (1) PLATFORM
CONTRADICTION — declared threat model is LINUX (2026-06-18) but the run executed on WINDOWS; classes E/G
are BACKSLASH traversal, which only escapes on Windows (on Linux `..\esc` is a literal filename, no escape).
So the suite is (a) on the wrong OS again [the exact 2026-06-18 mistake recurred], (b) Windows-POLLUTED
(E/G aren't Linux vectors), (c) Linux-INCOMPLETE (missing the real Linux classes our own FRONTIER.md Axis 6
names: symlink race, null-byte, Unicode normalization). So 100%/0% = "complete vs a wrong taxonomy on the
wrong OS," NOT honest Linux. Honest Linux → abstention should RETURN (real classes uncovered). HYPOTHESIS to
verify on Linux (not assert): backslash-only "gamed" patches (x12, y01–y04) may be GENUINE on Linux;
absolute-path leakers (x04/x09/x14/y05) stay gamed — gold-set labels are platform-dependent. (2) V MIRRORS
L — V6=`..\esc_v6` ≈ L8=`..\esc_l8`; "held-out" is ID-disjoint but mechanic-identical, so coverage is
checked at payload-ID level, not class-concept level; a within-class novel variant (e.g. URL-encoded) could
fool it. **OPERATOR CALL: "Commit to Linux, redo taxonomy."** Plan: move eval to GCP Linux VM; re-derive
taxonomy for Linux (drop backslash E/G, add symlink/null-byte/Unicode + absolute); relabel gold set under
Linux semantics (verify by RUNNING); make V mechanically distinct from L per class; run the adversarial
within-class test. Platform-parameterization (per-OS taxonomy/labels) noted as a later enhancement, not now.
NEXT: recon on Linux to establish true escape behavior before redesigning. ("environment is part of the
vulnerability" — recurring; bake a platform check so this can't silently regress a third time.)

**UPDATE 2026-06-19 (e) — Axis 1 (abstention) BUILT, frontier-audit verdict AT BAR (frontier tier).**
Three-way verdict shipped (GENUINE/GAMED/ABSTAIN), two objective triggers: baseline-blindness (tested:
restricted V→0% baseline hit→whole-eval abstain) + coverage-adequacy (V_classes {A,B,C,D} ⊉ taxonomy
{A..G} → survivors abstain, reason "coverage-gap {E,F,G}"). ANTI-LEAKAGE PROVEN by quoting verdict code
(_precision_recall_3way core.py:171-181): verdict reads only exploit_hit (V), hp_fail (HP), suite_complete
(static V_classes⊇taxonomy) — never per-patch L; `labels` used ONLY for the confusion matrix. The circular
trap is closed by construction. Numbers: graded 17/39, P/R/F1 = 100% on graded, abstention_rate 56.4%
(22/39 = 13 genuine + 9 former-FN survivors), 0 false-negatives on graded (was 9). Diagnostic layer
(diagnose_coverage_gaps, analysis-only, MAY use L, never feeds verdict): "adding class E→15 conversions"
etc. Audit's honest critiques (all defensible, logged for later polish): 56% is operationally expensive
(fix = expand V, not change mechanism); taxonomy is HAND-DECLARED ceiling not discovered (unknown-unknown
class H invisible — inherent limit of static taxonomy, = the representativeness ceiling); suite_complete is
all-or-nothing (per-patch precision would need L → forbidden, so correctly chose safe over-abstain);
diagnostic count doesn't split would-be-GENUINE vs would-be-GAMED conversions (polish). Cheapest validation
(audit-suggested, = start of Axis 3): add one E-class exploit to V, watch abstentions resolve to correct
verdicts. **Meta:** the calibration piece — the actual contribution — now exists: the verifier knows when
it doesn't know, and the number is trustworthy because no answer-key leaks into it.

**UPDATE 2026-06-19 (d) — Axis 1 (abstention) DESIGN LOCKED; caught a ground-truth-leakage trap.**
Recon's "Option C" (100% precision / 100% recall / 23% abstention) was CIRCULAR — it decided where to
abstain by consulting which L-classes catch each test patch. L is the answer key (it labels the gold set);
using per-patch L-results in the verdict is ground-truth leakage — it abstains on exactly the patches the
key says V gets wrong. Rejected. The verifier-integrity bug the project exists to catch, surfaced inside
the verifier's own calibration layer. **Deployable rule (LOCKED):** abstention may use ONLY judgment-time
info — V-set, fuzzer, HP, the patch, and the vuln's STATIC class taxonomy (the set of known exploit
classes; deployable) — never the per-patch L-label. Two triggers: (a) baseline-blindness — run V vs the
plugin's identity baseline; if the suite can't trigger the unpatched vuln → ABSTAIN (suite blind to this
CWE; relevant for BountyBench Java/logic per AIxCC 17% Java fuzzer reliability); (b) coverage-adequacy
(GLOBAL suite property, not per-patch) — if V's class coverage ⊉ taxonomy, every V-survivor ABSTAINS with
reason = missing classes. Consequence is honestly WORSE numbers, not better: abstains on all 22 survivors
(13 genuine + 9 FN alike — a true A–G fix and an A–D-block/E–G-leak cheat are INDISTINGUISHABLE to an A–D
suite), grades only the 17 V-caught cheats (100/100 on graded), abstention_rate ≈ 56%. That 56% is the
truth: with an A–D suite the verifier can condemn but never confidently bless. **Operator reframe:**
abstention is a THIRD METRIC / diagnostic, not a grade — abstention_rate measures suite-incompleteness;
the reason-taxonomy (which classes missing) is the to-do list; Axis 3 (expand V) drives abstention_rate→0,
tying the two axes into one measurable story. **Diagnostic layer** (calibration-only, may use L, NEVER
feeds the verdict): quantifies how many abstentions each added class would convert — the debug map.
Anti-gaming: all four numbers (P/R/F1/abstention_rate) reported together; abstention triggered only by
objective checks (baseline-fire, set-inclusion), never a tunable knob. Stays vuln-agnostic (plugin supplies
baseline_sanitizer + per-exploit class tags + taxonomy; core does set arithmetic only) and observe-don't-
steer (ABSTAIN is a verdict; the diagnostic informs the human, doesn't auto-edit V). Build next.

**UPDATE 2026-06-19 (c) — Axis 5 CLOSED, frontier-audit verdict AT BAR.** g02/g08 reclassified
genuine→gamed (subtype "functionality-breaking") — the fuzzer caught them as over-strict (reject spaces/
dots); gold set is now self-correcting from evidence, not hand-trust. Gamed taxonomy: 20 exploit-leaking,
5 functionality-breaking, 1 delete-feature. Cleanups done: single HP run (no Phase-2b recompute),
explicit `hp_results=None` at coverage_curve call sites, corpus invariant assertion (no ../, /, \ in any
of 406). Numbers: cheat_catch 26/26=100%, happy_pass 13/13=100%, V-set F1 79.1% (+19.6pp), precision
100%, recall 65.4%. Audit self-checked g11 live (looked like g02) — confirmed genuine (it STRIPS bad
chars, file still written; g02 REJECTS). **Key signal for next axis:** the remaining 9 false-negatives
(recall capped at 65%) are NOT Axis 5 — they're exploit-leaking patches whose attack class the V-set/
fuzzer don't reach. FNs = "declared a broken patch genuine" = the dangerous direction. This is the
empirical case for Axis 1 (abstention): the principled fix is the verifier saying "un-gradeable / can't
confirm baseline" instead of confidently blessing patches it can't actually test — not an endless chase
for more exploit classes. Bar's a-priori priority (1 next) now evidence-motivated.

**UPDATE 2026-06-19 (b) — Axis 5 (functionality gating) built; workflow loop proven end-to-end.**
Added `happy_path()`/`run_happy_path()` to VulnPlugin; core now labels GENUINE only if patch blocks
exploits AND passes happy-path (vuln-agnostic — core learns no vuln specifics; plugins supply legit
inputs). Closes the delete-the-feature false negative (a reject-all patch was GENUINE, now GAMED).
Numbers (run): cheat_catch 21/21 = 100%, happy_pass 15/15 = 100% — both meet FRONTIER.md Axis 5
reference numbers. `frontier-audit` verdict: **industry-standard, NOT yet at frontier** — refused to
rubber-stamp. Named gaps: happy-path = 5 hand-picked vs 8000 fuzzer exploit inputs (1600× asymmetry);
only 1 cheat variant (total rejection, no partial-delete e.g. overly-narrow allowlist); happy-path not
folded into V-set precision/recall; no weighted scoring (AIxCC 3× functionality weight). All
addressable without architectural change. **Loop proven:** frontier-bar set the bar → built against it
→ frontier-audit measured vs bar and returned a tiered verdict with gaps (Failure-3 caught
automatically). Both skills validated.

**UPDATE 2026-06-19 — FRONTIER.md landed (476 lines), bar set, anchors live-verified.** Bar was not
captured: it places the verifier at *industry-standard* (fuzzer-as-verifier) one full tier below the
frontier (oracle-stratified + abstaining), with a 6-axis divergence log. Anchors: 9/11 confirmed, with
honest corrections fed back from the prior chat — AIxCC cross-team validation is "weaker than claimed"
(future work, post-hoc expert review only, not implemented); Naptime has NO arXiv ID (blog only);
"co-bounded support" is unconfirmed as an exact phrase (Scrivens says "overlapping distributions"); the
150-CPU-hr miss is a *reachability* failure (harness didn't compile `generate_series`), not fuzzer-quality.
~40% figure CONFIRMED (CC 37.7%, MR 45.6%); 75% C vs 17% Java CONFIRMED; Big Sleep assertion-as-oracle
CONFIRMED. Name collision CONFIRMED (≥6 security tools named Aegis, incl. a Dec-2025 exploit agent).
**Build priority (from FRONTIER.md):** 5 functionality gating (CRITICAL — none today) → 1 abstention
(HIGH) → 2 oracle stratification (HIGH for BountyBench C/C++) → 6 variant coverage → 3 independent engine
→ 4 knob decomposition. README status corrected from "built & validated" → "substrate built, industry-
standard, calibration layer in progress." Next: build Axis 5, commit → `frontier-audit` fires against
this bar (tests the audit gate).

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
