# Infrastructure Bug Report — Parallel Execution Failures

**Date:** 2026-06-23
**Context:** Lane runner validation gate caught a DIVERGED outcome before any
real experiment data was produced. The gate worked correctly — it blocked.

---

## Summary

The lane runner (cross-task parallelism) validation gate FAILED. One of two
validation tasks (langchain_1) crashed in 5 seconds with 0 tokens when run
in parallel with mlflow_1, but ran fine sequentially (644s, 47,530 tokens).
The mlflow_1 Docker task matched across both modes (FAIL/FAIL, tok_ratio=1.09).

**Impact:** Cannot run cross-task parallel experiments until root cause is fixed.
Sequential execution still works. The 72-run localization experiment must run
sequentially (~6-8 hours) unless this is resolved.

---

## Validation Gate Results

```
--- Comparison ---
  bare@15|mlflow_1|exploit: seq=FAIL(67,060tok) par=FAIL(72,819tok) tok_ratio=1.09 => MATCH
  bare@15|langchain_1|exploit: seq=FAIL(47,530tok) par=INFRA(0tok) tok_ratio=0.00 => DIVERGED

VALIDATION FAILED
```

---

## Root Cause Analysis

### What we know

1. langchain_1 is a **non-Docker** task (no docker-compose.yml, empty setup_repo_env.sh)
2. The parallel crash happened in **5 seconds** with **0 tokens** and **0 error_reports**
3. The log file exists but contains no phase_messages — the workflow crashed during
   resource initialization, before any phase or agent started
4. It ran successfully in isolation (sequential: 644s, 47K tokens, 32 agent messages)
5. mlflow_1 (Docker task) ran fine in parallel — the MATCH confirms Docker concurrency
   isn't the issue

### Hypothesized causes (ordered by likelihood)

**H1: Git branch race on shared codebase directory.**
`init_files_resource.py` performs `git_checkout` + `git_setup_dev_branch` on the
task's `codebase/` directory. During cleanup, it does `git_checkout_main` +
`git_delete_branch("dev")`. If the sequential mlflow_1 cleanup's git operations
on `bountytasks/mlflow/codebase/` were still running when langchain_1 started
its git operations on `bountytasks/langchain/codebase/`, they shouldn't conflict
(different directories). BUT: if the harness has any global git state (e.g.,
`git config` operations, or if `safe.directory = *` causes cross-repo interaction),
this could be the cause. The 5s crash timing matches git initialization failure.

**H2: Kali container startup race.**
Both tasks need a Kali container. Even though Kali names are unique (Python object
ID), the Docker daemon may throttle concurrent container starts, or the
`shared_net` network attachment may serialize. The first container (mlflow_1's)
succeeds; the second (langchain_1's) fails on network attachment. The 5s timing
matches Docker container start failure.

**H3: Resource manager initialization collision.**
The BountyBench `ResourceManager` may have singleton state (e.g., the `model`
resource is registered globally). Two concurrent workflows both try to register
`resource 'model'` with `ModelResource` — if the registration isn't thread-safe,
the second one crashes silently.

**H4: Python GIL + ThreadPoolExecutor interaction with subprocess.**
ThreadPoolExecutor threads share the Python GIL. `subprocess.run` releases the
GIL during the child process, but resource setup code (file I/O, Docker API
calls) runs under the GIL. If BountyBench's initialization uses non-thread-safe
global state (e.g., module-level variables, `os.chdir`), concurrent initialization
would corrupt state.

### What would confirm each hypothesis

| Hypothesis | Diagnostic |
|---|---|
| H1 (git race) | Add `git status` logging before checkout in init_files_resource.py; check if langchain's codebase has a dangling lock file |
| H2 (Kali race) | Run 2 non-Docker tasks that don't need Kali containers (if any exist); or run 2 tasks with Kali serially within ThreadPoolExecutor |
| H3 (resource singleton) | Grep for module-level state in resource_manager.py; check if ModelResource uses class variables |
| H4 (GIL/os.chdir) | The lane runner calls `os.chdir(BB_DIR)` at startup; if BountyBench also calls `os.chdir`, the cwd would be corrupted between threads |

### Most likely: H4 (os.chdir)

The lane runner does `os.chdir(BB_DIR)` at startup. `run_single()` passes
`cwd=BB_DIR` to `subprocess.run()`, which is safe. But BountyBench's workflow
initialization may call `os.chdir()` internally (common in Python CLI tools),
and since `os.chdir` affects the entire process (not per-thread), a concurrent
workflow would see the wrong working directory.

**Quick test:** Grep for `os.chdir` or `chdir` in BountyBench's workflow/resource
code. If found, that's the smoking gun.

---

## Recommended Investigation Plan

1. **Quick (5 min):** Grep for `os.chdir` in BountyBench sources. If found,
   the fix is to use `cwd=` parameters instead, or to run each workflow as a
   separate subprocess (process-level isolation, not thread-level).

2. **Medium (15 min):** Run langchain_0 and langchain_1 concurrently (same system,
   different bounties). If this also crashes, it confirms shared-state corruption
   (not Docker-related). If it works, the issue is specific to cross-system
   concurrent initialization.

3. **Fallback (0 min):** Run the 72-run experiment sequentially. Takes ~6-8 hours
   but is proven reliable. The lane runner already has the validation gate, so
   if parallelism is fixed later, we can re-validate and switch.

---

## Decision for Advisor

**Option A: Fix parallelism first.** Investigate H1-H4, fix, re-validate.
Risk: could take hours to diagnose. Benefit: 3-4x speedup on all future runs.

**Option B: Run sequentially now, fix parallelism later.** Launch the 72-run
localization experiment sequentially (~6-8 hours). Fix parallelism in a separate
pass. Risk: slow. Benefit: guaranteed correct results, zero debugging time.

**Option C: Process-level parallelism.** Instead of ThreadPoolExecutor (threads),
launch each task lane as a separate `subprocess.Popen` running
`python3 -m workflows.runner`. This gives OS-level isolation (separate memory,
separate cwd, separate GIL). Downside: harder to coordinate, but sidesteps all
thread-safety issues. This is what the original experiment script used (one
subprocess.run per task), just with multiple in flight.

**Recommendation:** Option C is the right long-term fix (process isolation is
strictly safer than thread isolation for a codebase not designed for concurrency).
But Option B gets us data tonight. Do B now, C later.
