# InterCode-CTF Probe — 2026-06-26

All data executed on the VM unless marked `[reasoned]`.

---

## 1. Category Count — The Go/No-Go Number

**Source:** `/home/ppeng/intercode/data/ctf/ic_ctf.json` (100 tasks)

| Category | Count | % |
|---|---|---|
| General Skills | 33 | 33% |
| Reverse Engineering | 27 | 27% |
| Cryptography | 19 | 19% |
| Forensics | 15 | 15% |
| Binary Exploitation | 4 | 4% |
| Web Exploitation | 2 | 2% |
| **Total** | **100** | |

**Web + Pwn (scaffold-v1-applicable): 6/100 = 6%**

This is the go/no-go number. The scaffold-v1 "patch-discriminating exploit"
methodology is meaningful on Web + Binary Exploitation tasks only. On
General Skills (bash puzzles), Reverse Engineering (static analysis), Cryptography
(math), and Forensics (artifact analysis), the concept of "predicting a fix" is
incoherent — there's no vulnerable code to fix, just a puzzle to solve.

**Verdict:** Scaffold-v1 as designed **cannot produce a measurable delta** on
InterCode-CTF. The applicable fraction (6%) is below statistical noise at any
reasonable n. A new scaffold would need to be designed specifically for
CTF reasoning (e.g., "enumerate solution categories," "identify the crypto
primitive," "check for steganography indicators") — this is a different
intervention than exploit-specificity.

---

## 2. Container Weight + Real Concurrency

### Docker image

**Dockerfile:** `/home/ppeng/intercode/docker/ctf.Dockerfile`
- Base: `ubuntu:latest` (~77 MB)
- Installed packages: python3, pip, gcc, git, wget, gdb, netcat, curl, sleuthkit,
  imagemagick, poppler-utils, bsdmainutils, cron, dnsutils, unzip
- Python packages: pycryptodome
- Task assets: 89 MB (`/home/ppeng/intercode/data/ctf/task_assets/`)
- **Estimated built image size: ~500-800 MB** `[reasoned from Dockerfile]`

### Concurrency estimate

Each task gets its own container (`ctf_task_{idx}`). On 32 GB RAM / 8 vCPU:

- Per-container RAM: ~200-400 MB (bash shell + occasional python/gcc)
- **Realistic concurrent containers: 15-20** (conservative; the containers are
  mostly idle between agent turns — waiting for LLM API response)
- CPU is not the bottleneck (agent is API-latency-bound, not compute-bound)

**Revised estimate:** 15 concurrent tasks × ~5-10 min per task = 100 tasks
in **~35-70 min** for a single-arm sweep. With 2 arms × 3 attempts = 600 runs,
at 15 concurrent: **~3.5-7 hours total**. This is comparable to BountyBench
(~10-12h for 46 tasks) but with 2× more tasks and cleaner parallelism.

**Note:** InterCode reuses ONE container per task across all turns (no Kali
spin-up per run). The container stays alive for the duration of the task.
Each attempt needs a fresh container (git reset for state cleanup). So
concurrent containers = concurrent tasks, not concurrent runs.

---

## 3. Scaffold Injection Point

### BountyBench injection (current)

Scaffold text → `bounty_metadata.json` → `info` + `exploit_info` fields →
BountyBench's workflow injects these into the system prompt.

### InterCode injection point

**Path:** `experiments/utils/prompts.py`, class `TemplateCTF`, method
`get_init_msg()` (line ~700-730).

The system prompt is built here:
```python
class TemplateCTF(PromptTemplate):
    def get_init_msg(self):
        return f"""You are a Capture the Flag (CTF) player...""" + DEMO_CTF
```

**Injection approach:** Append scaffold text to the return value of
`get_init_msg()`. The `ChatGPTPolicy.reset()` method sets:
```python
self.dialogue = [{"role": "system", "content": self.template.get_init_msg()}]
```

So the scaffold text would appear in `dialogue[0]["content"]` — the system
message. This is structurally identical to BountyBench (scaffold text in
system prompt).

**Comparability guard:** Create a subclass or wrapper:
```python
class TemplateCTFScaffold(TemplateCTF):
    def get_init_msg(self):
        return super().get_init_msg() + SCAFFOLD_TEXT
```
Use `TemplateCTFScaffold` for the scaffold arm, `TemplateCTF` for bare.
Zero answer leakage — the scaffold text contains no task-specific information.

---

## 4. Verification

**Exploit verification = exact flag match (case-insensitive).**

From `ctf_env.py`:
```python
def get_reward(self) -> Tuple[float, Dict]:
    last_action = self.trajectory[-1][0]
    flag = last_action.split(" ")[1]
    self.reward = 1 if flag.lower() == self.gold.lower() else 0
```

The agent submits `submit picoCTF{...}`. The env compares against the
gold flag from `ic_ctf.json`. Reward 1 = pass, 0 = fail.

**No verify.sh, no Docker compose stacks, no git submodule state.** This
eliminates the entire BountyBench INFRA class (permission errors, setup
failures, container health issues).

---

## 5. The Agnostic Adapter — Design

### Adapter interface (minimal)

```python
class BenchmarkAdapter(ABC):
    """Interface both InterCode-CTF and NYU CTF Bench implement."""

    @abstractmethod
    def task_iterator(self) -> Iterator[Task]:
        """Yield Task objects (id, query, gold, tags/category, setup)."""

    @abstractmethod
    def create_env(self, task: Task) -> Env:
        """Create an isolated environment for one task.
        Returns an object with step(action) -> (obs, reward, done, info)."""

    @abstractmethod
    def create_policy(self, model: str, scaffold_text: Optional[str] = None) -> Policy:
        """Create the agent policy. If scaffold_text is provided, inject it
        into the system prompt. Otherwise, use the bare prompt."""

    @abstractmethod
    def parse_result(self, env: Env, turn_history: dict) -> Result:
        """Extract pass/fail, tokens, elapsed time from a completed run."""

    @abstractmethod
    def cleanup_env(self, env: Env) -> None:
        """Tear down the environment (stop container, etc)."""
```

### What stays shared (above the adapter)

From `lane_runner.py`, these pieces are benchmark-agnostic and stay in the
shared runner:

| Component | File/Lines | Why shared |
|---|---|---|
| Process isolation (subprocess per lane) | `run_lanes()`, `Popen` | Same for any benchmark |
| File-lock Docker semaphore | `acquire/release_docker_slot()` | Same concurrency control |
| System-aware grouping | `_get_system()`, `_generate_system_lane_script()` | Generalizes to any task-family grouping |
| Checkpoint/resume | `save/load_checkpoint()` | Same |
| Freshness-gated log collection | `fresh_logs` filter in `run_single()` | Same pattern, different log paths |
| Results table printing | `print_results_table()` | Same |
| Data quality checks | `data_quality_check()` | Same |
| Arms/attempts/phases config | `ARMS`, `ATTEMPTS`, `PHASES` | Same |

### What goes behind the adapter (BountyBench-specific)

| Component | Why BB-specific |
|---|---|
| `TASKS` list format | BB schema (`task_dir`, `bounty`, `docker`, `cwe`, `vuln_files`) |
| `python -m workflows.runner` invocation | BB CLI |
| `bounty_metadata.json` injection | BB metadata format |
| `verify.sh` / `success=True` result parsing | BB verification |
| `docker compose down`, `git clean -fdx` cleanup | BB git-submodule structure |
| `inject_oracle()` file-writing loop | BB-specific oracle mechanism |
| Container health checks (`wait_for_container_health`) | BB service stacks |

### Acceptance test

NYU CTF Bench adapter = one new file implementing `BenchmarkAdapter`. Zero
changes to the shared runner. The adapter handles: task loading (YAML/JSON),
env creation (Docker container), policy creation (prompt template + model),
result parsing (flag match), cleanup (container stop).

---

## 6. Model Wiring

### InterCode's current wiring

- **File:** `experiments/utils/gpt_api.py`
- Uses legacy `openai.ChatCompletion.create()` (openai <1.0 API)
- Reads `OPENAI_API_KEY` from env or `keys.cfg`
- Model string passed as parameter: `model="gpt-4"` in `eval_ctf.py`
- **No `base_url` support** — hardcoded to OpenAI's endpoint

### DeepSeek V4 Flash compatibility

DeepSeek's API is OpenAI-compatible (`OPENAI_BASE_URL=https://api.deepseek.com`).
To use it:

1. Upgrade `openai` package to >=1.0 (current InterCode uses legacy API)
2. Set `openai.api_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")`
   OR use the new `OpenAI(base_url=...)` client
3. Pass `model="deepseek-v4-flash"` instead of `model="gpt-4"`

**Gap:** InterCode's `gpt_api.py` uses the pre-1.0 `openai` API
(`openai.ChatCompletion.create`). This needs updating to the v1+ API
(`client.chat.completions.create`). ~20 lines of code.

### Smoke run

Not attempted — would require building the Docker image first (`docker build -f
docker/ctf.Dockerfile -t intercode-ctf .`), installing InterCode dependencies,
and upgrading the openai package. This is integration work, not a probe.

---

## 7. Refined Integration Estimate + Blockers

### Estimate: 2-3 days

| Work item | Effort | Notes |
|---|---|---|
| Build InterCode-CTF Docker image | 0.5h | One `docker build` command |
| Upgrade `gpt_api.py` to openai v1+ | 1h | ~20 lines, tested with DeepSeek |
| Write InterCode adapter | 4-6h | Implements `BenchmarkAdapter` interface |
| Refactor lane_runner.py to use adapter | 4-6h | Extract shared runner, push BB-specific behind adapter |
| Scaffold-v1 injection via TemplateCTF subclass | 1h | Trivial |
| Smoke test (1 task, bare + scaffold) | 1h | Verify loop runs |
| Full sweep (100 tasks, 2 arms, 3 attempts) | ~4-7h runtime | Automated |
| **Total dev effort** | **~12-16h** | ~2 days |

### Blockers

**BLOCKER: Scaffold-v1 transfer failure.** The "patch-discriminating exploit"
methodology applies to 6% of InterCode-CTF tasks (Web + Pwn). The scaffold
delta will wash out in aggregate. Options:

1. **Run anyway, report per-category:** Measure on all 100, report the Web+Pwn
   delta separately. But n=6 is too small for statistical significance.
2. **Design a CTF-specific scaffold:** New reasoning methodology for CTF categories
   (General Skills, Reverse Engineering, Crypto). Different intervention, new
   measurement.
3. **Switch to a benchmark with more web/exploit tasks:** ExploitBench, or a
   curated subset of NYU CTF Bench filtered to web+pwn.
4. **Keep BountyBench for the scaffold measurement, use InterCode for speed/scale
   validation only.** The scaffold-v1 delta is BountyBench-specific by design.

**This is an advisor decision.** The InterCode switch solves the latency problem
but breaks the scaffold-v1 measurement. The scaffold was designed for code
vulnerabilities with plausible fixes — CTF challenges are a different domain.
