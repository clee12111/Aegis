# GCP Setup — Aegis on the cloud

Relocates the benchmark environment off the local Windows/WSL2 box (which ran out of
disk) onto a single GCP free-trial VM. Same recipe as the local attempt — clone
bountybench → `setup.sh` → smoke run — on a native-Linux box with room. See
DECISION.md "Compute/storage strategy" for the why.

Two parts: (1) the VM you create in the GCP console, (2) the engineer prompt to paste
into Claude Code running on that VM.

---

## Part 1 — Provision the VM (GCP console or `gcloud`)

| Setting | Value | Why |
|---|---|---|
| Region | `us-central1` (or nearest) | Cheap, e2 available; credits work anywhere |
| Machine type | `e2-standard-4` (4 vCPU / 16 GB) | Sized for Act III; resizable later (stop → change type → start) |
| Boot disk image | Ubuntu 22.04 LTS | Native ext4 — no colon-filename problem |
| Boot disk size/type | 150 GB, balanced (pd-balanced) | Act III working set ~80–100 GB; resizable up, not down |
| Firewall | **SSH only — no other inbound** | Security (see below) |

Cheaper option: start `e2-standard-2` for setup, resize to `e2-standard-4` for the
Act III burst. Spot VM optional for Act III (restartable; checkpoint between runs).

**SECURITY — this matters here specifically.** This VM runs *deliberately vulnerable*
target apps plus a Kali "agent" container. Keep every inbound port closed except SSH
(ideally key-only or via IAP). Never bind a task/agent container to a public
interface. (The vLLM CVE in your own trio is literally an exposed-socket RCE — don't
recreate it on your own box.)

**Cost guardrails (from DECISION.md):** stop the VM when idle; do NOT upgrade the
trial to a paid account; delete the VM **and** disk when done (disk bills against
credit even while the VM is stopped).

---

## Part 2 — Engineer prompt (paste into Claude Code on the VM)

```
Task: stand up the Aegis benchmark environment on a fresh GCP Ubuntu VM. SETUP ONLY.
Context/WHY: this replaces the local WSL2 attempt that ran out of disk — same recipe,
native-Linux box with room. We are in Act I (domain ramp): do NOT build any agent,
scaffold, or verifier code. Environment setup only (Hard Rule 7).

1. Confirm the box: `lsb_release -a`, root is ext4, `df -h /` shows ~150G,
   `nproc` and `free -g`. Ensure Python 3.11 is available (setup.sh expects it;
   install via deadsnakes if Ubuntu 22.04 ships 3.10).
   WHY: confirm we have the disk + runtime the local box lacked.

2. Install Docker Engine (NOT Docker Desktop — this is headless Linux) plus the
   compose plugin. Verify: `docker run --rm hello-world` and `docker compose version`.
   Add the current user to the `docker` group so sudo isn't needed per command.

3. Clone bountybench into ~/Aegis/bountybench and init submodules. Confirm the
   bountytasks submodule checks out FULLY, including the codebase/ dirs for
   lunary, mlflow, and vllm — not just metadata.
   WHY: prior recon only reached metadata via git objects; we need real source.

4. Run `./setup.sh --all` (venv, pip deps, .env). If crfm-helm triggers a
   PyTorch/CUDA pull, report its size — we want to know if it can be skipped
   (no GPU on this VM). Do NOT install GPU/CUDA drivers.

5. Run ONE `--use_mock_model` workflow end-to-end on lunary bounty_0 (no API spend).
   Report whether it completes and emits a verifier result.
   WHY: proves the sandbox/verifier harness works before Act II.

SECURITY: this VM runs deliberately-vulnerable apps + a Kali agent container. Keep
ALL inbound ports closed except SSH; do NOT bind any task/agent container to a public
interface. Report the firewall state.

Report each step pass/fail with REAL command output. State ABSENT for anything
expected that isn't there. Do not write agent code.
```

---

## After it passes

- Relay Claude Code's step-by-step report back to the advisor (paste, or push to
  GitHub and the advisor pulls) for verification against these expectations —
  especially step 3 (full `codebase/` checkout) and step 5 (verifier result emitted).
- Once the framework is laid down, push the Aegis repo to a private GitHub so the
  cloud VM and the local machine stay in sync via git (see the sync note in chat).
