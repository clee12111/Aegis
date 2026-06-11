# Aegis — Session Handoff

Drop this in the project root so every Cowork chat reads it alongside CLAUDE.md,
AEGIS_CONTEXT.md, and WORKFLOW.md. Delete or fold into the decision log once
Act I is complete.

Last updated: 2026-06-11 (environment proven end-to-end on GCP; mock smoke run green).

---

## Where we are

**Act I — Foundations. Domain ramp, no agent built.** The CVE trio is locked
(below). The environment is now **stood up and proven end-to-end on a GCP VM** —
the BountyBench harness runs a full mock smoke run (containers → Kali agent →
verifier verdict → cleanup) on lunary bounty_0. Remaining Act I work: (1) the
three-CVE hand study, and (2) the exit gate (explain all three from memory).
The CVE study needs only public sources, not the environment.

**Act I exit gate:** explain all three CVEs from memory — how each manifests,
how the exploit triggers it, and what a genuine patch requires vs. a superficial
one that only passes the obvious test.

---

## The locked CVE trio

Each was chosen to teach a *different* reason detection is hard (the three
failure modes in CLAUDE.md), and all three live in Act III BountyBench target
systems so the domain knowledge transfers directly.

| Pick | System / task | CVE | CWE | Teaches |
|---|---|---|---|---|
| (a) | `bountytasks/lunary` bounty_0 | CVE-2024-1625 | CWE-639 authz bypass | The bug is an **absent check**; the code looks normal |
| (b) | `bountytasks/mlflow` bounty_1 | CVE-2024-1558 | CWE-22 path traversal | **Multi-hop taint chain** + patch-integrity |
| (c) | `bountytasks/vllm` bounty_0 | CVE-2024-11041 | CWE-502 deserialization | **Benign-looking sink**, severe class |

Specifics confirmed from the submodule metadata (read via `git ls-tree`):

- **(a) Lunary** — commit `fc959987f3b2cfba25c847ffdba6ac820af154b4`, severity 7.5.
  IDOR project deletion: user B deletes user A's project because no ownership
  check runs. Patch touches `packages/backend/src/api/v1/projects/index.ts` and
  `.../utils/authorization.ts`. huntr `cf6dd625-e6c9-44df-a072-13686816de21`.
- **(b) MLflow** — commit `fc515cd25072248fb3328b16ae1bd621dbffa50a`, severity 7.5.
  Single-file patch: `mlflow/server/handlers.py`. huntr
  `7f4dbcc5-b6b3-43dd-b310-e2d0556a8081`.
- **(c) vLLM** — severity 9.8. `pickle.loads` on socket data in the shared-memory
  broadcast path (`shm_broadcast.py`). huntr link is in the
  `vllm/bounties/bounty_0` metadata — surface it once the submodule is checked out.

**Open sub-choice on (b):** default is `bounty_1` (single file, cleanest first
taint chain). `bounty_0` (CVE-2023-6018, CWE-23, severity 10, **$30,485 — the
largest bounty in the benchmark**, 4-file patch across the model registry,
commit `f2baa689472d0dc4c73b1c2f97ac296253ab4454`) is kept as an optional depth
study, not the primary. Human to confirm or override.

---

## Corrections already made (do not repeat)

Two of the original picks were wrong and were caught by recon before any build —
this is the discipline working, not a failure:

1. **MLflow CVE-2024-1483 was a guess and is NOT a packaged bounty.** The real
   MLflow path-traversal bounties are `bounty_0` (CVE-2023-6018), `bounty_1`
   (CVE-2024-1558), `bounty_2` (CVE-2024-0520). We use `bounty_1`.
2. **There is NO MLflow deserialization/recipe-RCE bounty.** MLflow's four
   bounties are three path-traversals + one GraphQL DoS. Pick (c) was relocated
   to vLLM, which has a real CWE-502 deserialization bounty.

**Principle, now load-bearing:** select only from confirmed packaged bounties by
reading the submodule — never name a CVE from memory. Guessing failed twice.

---

## Environment state

- **PROVEN END-TO-END on a GCP VM (2026-06-11).** The BountyBench harness runs a
  full mock smoke run on lunary bounty_0: containers → Kali agent (arm64 via qemu)
  → verifier verdict (`success=False`/`no_submission`, expected) → cleanup. Full
  details + fixes in DECISION.md.
- **VM:** GCP `e2-standard-4` (amd64), Ubuntu 22.04, 300 GB balanced disk.
  Docker-ce + buildx + compose (official repo). Python 3.11 (deadsnakes),
  bountybench venv, all 31 submodule codebases checked out.
- **Portability fixes (not forks):** (1) `patches/dockerd-entrypoint-arch.patch`
  — credential-helper arch detection; (2) qemu/binfmt arm64 emulation
  (kernel-level, covers DinD) for the arm64-only `cybench/bountyagent`;
  (3) disk 150 → 300 GB.
- **Arch plan:** native amd64 `bountyagent` IS buildable
  (`bountytasks/.github/Dockerfile`, base `cybench/kali-linux-base:latest`, via
  `tools/build.sh`). Emulation is fine for mock/non-measured runs; build native
  before measured Act II/III runs to avoid timing skew.
- **Harness gotcha:** use EVEN `--phase_iterations` (canonical default 10) — odd
  values crash the no-submission scoring path (`base_phase.py:257`). Avoid, don't patch.
- **Cost guardrails:** stop the VM when idle; don't upgrade the trial to paid;
  delete the VM **and** disk when done.
- **Meridian / Aether are NOT in BountyBench.** They're the Act II self-test
  targets, mounted into the container separately.

---

## Benchmark structure (confirmed)

- Tasks live in the `bountytasks` submodule (33 dirs: the 25 systems plus
  `.github`, `tests`, etc.).
- Workflows: `detect_workflow` / `exploit_workflow` / `patch_workflow`, run via
  `python -m workflows.runner --workflow-type <type> --task_dir bountytasks/<system>
  --bounty_number N [--model ... | --use_mock_model]`. `--use_mock_model` costs no
  API spend.
- Everything executes in a Kali Linux container; Docker is required for any run.

---

## Immediate next actions

1. Environment standup — **DONE** (proven end-to-end on GCP, 2026-06-11; see DECISION.md).
2. (Before MEASURED runs) Build the native amd64 `bountyagent` to drop qemu —
   FEASIBLE (kali-linux-large has amd64). Use the **root** Dockerfile (NOT
   `bountytasks/.github/Dockerfile`), build inside DinD via an ad-hoc mount; full
   recipe in DECISION.md. Always use EVEN `--phase_iterations`.
3. Do the Act I CVE hand-study, order **A → B → C** (drafted in
   `notes/act1-cve-study.md`): per CVE — huntr → NVD/GHSA → trace input-to-sink in the
   vulnerable commit → diff the fix → build a superficial patch that passes the test but
   leaves the vector open → three-bullet cold explanation. Then the exit gate: explain
   all three from memory.
4. Begin Act II: build the verifier + self-test seam on Meridian/Aether.

Per-CVE exit-gate exercises:

- **(a) Lunary** — superficial patch guards the delete endpoint but leaves
  sibling endpoints (read/update) open; that residual is the real IDOR.
- **(b) MLflow** — MLflow's real serial-bypass history (one traversal fix
  defeated by switching the URI component) is the superficial-patch lesson: a
  `../`-stripping patch that an encoded/fragment variant walks straight through.
- **(c) vLLM** — genuine fix authenticates/restricts the channel or drops
  untrusted deserialization; superficial fix validates a field *after*
  `pickle.loads` already ran (too late).

---

## Workflow change in Cowork (important)

WORKFLOW.md's dual-Claude split was built on one premise: the advisor (claude.ai)
**could not read the repo** and relied on the human to relay engineer reports.
In Cowork the advisor can read files directly. That changes things:

- The relay overhead drops, and the "advisor working from stale assumptions"
  failure mode shrinks — the advisor can now run its own recon instead of
  guessing from docs.
- **Decision to surface for the human:** keep a separate Claude Code engineer
  instance for execution, or let the Cowork advisor handle both roles now that it
  has file access? Don't auto-merge them silently — it's a workflow call.
- **Still holds regardless:** verify before trusting any result (Hard Rule 2),
  recon before any invasive build, and Act I is domain ramp not code
  (Hard Rule 7 — no agent/scaffold/verifier code yet).

---

## Conventions to carry forward

- Engineer prompts (anything meant to be executed against the repo) go in code
  blocks, visually distinct from advisor commentary.
- End each working session with a plain-language summary for a non-technical
  reader.

---

## Transplantable: WSL2 setup prompt

```
Task: stand up Aegis environment — BIOS virtualization now enabled. SETUP ONLY.
1. Confirm WSL2 is running (wsl -l -v shows VERSION 2) and you are on ext4,
   not /mnt/c. Clone bountybench into ~/Aegis inside WSL2.
   WHY: the bountytasks submodule has colon-in-filename writeups; NTFS rejects
   them, ext4 does not. Cloning on /mnt/c reintroduces the failure.
2. Install Docker Desktop (WSL2 backend); verify docker --version and the mount
   check: docker run --rm -v "$(pwd)":/test alpine ls /test
3. ./setup.sh --all; init bountytasks. Confirm the submodule checks out FULLY
   including the codebase/ dirs, not just metadata.
   WHY: prior recon only reached metadata via git objects; we need the actual
   vulnerable source to study the CVEs.
4. Run ONE --use_mock_model workflow end-to-end (no API spend); report whether
   it completes and emits a verifier result.
   WHY: Act II depends on a working sandbox/verifier harness; prove it now.
Report each step pass/fail with actual command output. State ABSENT for anything
expected that isn't there.
```

## Transplantable: decision-log entry (already recorded in DECISION.md)

```
### 2026-06 — Act I CVE trio locked (post-recon ×2)
Decision: (a) Lunary bounty_0 CVE-2024-1625 CWE-639 authz bypass +
(b) MLflow bounty_1 CVE-2024-1558 CWE-22 path traversal +
(c) vllm bounty_0 CVE-2024-11041 CWE-502 deserialization.
Why: all confirmed packaged bounties in Act III target systems; each teaches a
distinct detection-hardness reason (absent-check / multi-hop taint / benign sink).
Original guesses (MLflow CVE-2024-1483; an MLflow recipe-RCE) were not packaged;
two recon rounds corrected before any build.
Env: WSL2 + Docker, clone inside ext4 never /mnt/c; BIOS virtualization enabled.
Precludes: studying CVEs absent from bountytasks (no Act III transfer).
```
