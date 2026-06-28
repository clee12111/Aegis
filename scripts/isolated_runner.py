#!/usr/bin/env python3
"""Isolated single-run executor.

Creates a fully isolated environment for one BountyBench run:
- Unique COMPOSE_PROJECT_NAME
- Per-run Docker network (replaces shared_net)
- Per-run container names (suffixed with run_id)
- Git worktree for the codebase (eliminates submodule lock race)
- Updated target_host in metadata to match suffixed container names

Usage:
    python3 isolated_runner.py --task_dir bountytasks/LibreChat --bounty 2 \
        --run_id run001 --model openai/deepseek-v4-flash --phase exploit_workflow \
        --iters 30 --max_input 16384 --max_output 4096
"""
import argparse, subprocess, json, os, sys, re, shutil, time, tempfile
from pathlib import Path

BB_DIR = "/home/ppeng/bountybench"


def create_run_network(run_id):
    """Create a per-run Docker network."""
    net_name = f"net_{run_id}"
    subprocess.run(["docker", "network", "create", net_name],
                   capture_output=True, timeout=10)
    return net_name


def remove_run_network(net_name):
    """Remove the per-run Docker network."""
    subprocess.run(["docker", "network", "rm", net_name],
                   capture_output=True, timeout=10)


def generate_isolated_compose(task_dir, run_id, net_name, original_system=None):
    """Generate a docker-compose override that isolates container names, network,
    and uses pre-built images instead of build: directives.

    Returns path to the override file, or None if no compose file exists.
    """
    compose_path = os.path.join(BB_DIR, task_dir, "docker-compose.yml")
    if not os.path.exists(compose_path):
        return None

    with open(compose_path) as f:
        content = f.read()

    # 1. Replace container_name: X with container_name: X_<run_id>
    def replace_container_name(match):
        original = match.group(1).strip()
        return f"container_name: {original}_{run_id}"
    content = re.sub(r'container_name:\s*(.+)', replace_container_name, content)

    # 2. Replace build: blocks with image: references to pre-built images.
    # Pre-built images are tagged as <project>-<service>:latest by compose.
    # The project name = the ORIGINAL directory name (e.g., "LibreChat", "mlflow").
    original_dir = original_system if original_system else os.path.basename(task_dir)
    # Parse service names that have build: directives
    lines = content.split("\n")
    new_lines = []
    i = 0
    current_service = None
    skip_build_block = False
    indent = ""
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track current service name (top-level under services:)
        if re.match(r'^  [a-zA-Z_][\w-]*:', line) and not line.startswith("    "):
            current_service = stripped.rstrip(":")

        # Detect build: directive
        if stripped.startswith("build:"):
            indent = re.match(r'^(\s*)', line).group(1)
            if ":" in stripped[6:] and stripped[6:].strip():
                # Single-line: build: ./path
                # Replace with image: <project>-<service>:latest
                img_name = f"{original_dir.lower()}-{current_service}:latest"
                new_lines.append(f"{indent}image: {img_name}")
                i += 1
                continue
            else:
                # Multi-line build block — replace first line, skip indented children
                img_name = f"{original_dir.lower()}-{current_service}:latest"
                new_lines.append(f"{indent}image: {img_name}")
                i += 1
                # Skip child lines (more indented than build:)
                while i < len(lines):
                    child = lines[i]
                    child_indent = len(child) - len(child.lstrip())
                    base_indent = len(indent)
                    if child.strip() and child_indent > base_indent:
                        i += 1  # skip
                    else:
                        break
                continue

        new_lines.append(line)
        i += 1

    content = "\n".join(new_lines)

    # 3. Replace shared_net → per-run network
    content = content.replace("shared_net", net_name)

    # 4. Remove "external: true" since the per-run network is created by the wrapper
    content = re.sub(r'external:\s*true', '', content)

    # Write the isolated compose file
    override_path = os.path.join(BB_DIR, task_dir, f"docker-compose.{run_id}.yml")
    with open(override_path, "w") as f:
        f.write(content)

    return override_path


def create_isolated_task_dir(task_dir, run_id):
    """Create a fully isolated copy of the task directory.

    Copies the entire task dir so each run has its own codebase, bounties,
    compose files, metadata — no shared state with other runs.

    Returns (isolated_task_dir, cleanup_fn).
    """
    src = os.path.join(BB_DIR, task_dir)
    # Place isolated copies on the Docker data disk (1.5TB, plenty of space)
    iso_base = "/mnt/docker-data/isolated_runs"
    os.makedirs(iso_base, exist_ok=True)
    dst = os.path.join(iso_base, run_id)

    # Clean any stale copy
    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=True)

    # Copy everything EXCEPT codebase (it's a git submodule — can't just copy)
    shutil.copytree(src, dst, symlinks=True,
                    ignore=shutil.ignore_patterns('codebase'))

    # Create a full independent clone of the codebase (no shared .git state).
    # git worktree shares .git/modules/ with the parent → races under concurrency.
    # A local clone with --shared is fast (~2s) and fully independent.
    codebase_src = os.path.join(src, "codebase")
    codebase_dst = os.path.join(dst, "codebase")
    if os.path.isdir(codebase_src):
        # The codebase is a submodule — .git is a file pointing to
        # ../../.git/modules/.../codebase. Copy files normally, then
        # replace the .git pointer with the actual git directory content
        # to create a fully standalone repo.
        shutil.copytree(codebase_src, codebase_dst, symlinks=False,
                        ignore=shutil.ignore_patterns('.git'))
        # Read the .git pointer to find the real git dir
        git_pointer = os.path.join(codebase_src, ".git")
        if os.path.isfile(git_pointer):
            with open(git_pointer) as f:
                gitdir_line = f.read().strip()
            # gitdir: ../../../.git/modules/bountytasks/modules/LibreChat/codebase
            real_gitdir = gitdir_line.replace("gitdir: ", "")
            if not os.path.isabs(real_gitdir):
                real_gitdir = os.path.normpath(os.path.join(codebase_src, real_gitdir))
            # Copy the real git directory
            shutil.copytree(real_gitdir, os.path.join(codebase_dst, ".git"),
                            symlinks=False)
            # Fix core.worktree to point to the NEW codebase location
            git_config = os.path.join(codebase_dst, ".git", "config")
            if os.path.exists(git_config):
                with open(git_config) as f:
                    cfg = f.read()
                cfg = re.sub(r'worktree\s*=.*', f'worktree = {codebase_dst}', cfg)
                with open(git_config, "w") as f:
                    f.write(cfg)
        elif os.path.isdir(git_pointer):
            # Already a real .git dir (not a submodule)
            shutil.copytree(git_pointer, os.path.join(codebase_dst, ".git"),
                            symlinks=False)

    # The isolated task_dir is relative to BB_DIR for the runner
    # We need to make it accessible — symlink it into bountytasks/
    iso_task_name = f"_iso_{run_id}"
    iso_link = os.path.join(BB_DIR, "bountytasks", iso_task_name)
    if os.path.exists(iso_link):
        os.remove(iso_link)
    os.symlink(dst, iso_link)

    def cleanup():
        if os.path.exists(iso_link):
            os.remove(iso_link)
        if os.path.exists(dst):
            subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", dst],
                           capture_output=True, timeout=60)
            shutil.rmtree(dst, ignore_errors=True)

    return f"bountytasks/{iso_task_name}", cleanup


def update_target_host(task_dir, run_id):
    """Update target_host in metadata.json to use suffixed container names.

    Returns (original_content, metadata_path) for restoration.
    """
    meta_path = os.path.join(BB_DIR, task_dir, "metadata.json")
    with open(meta_path) as f:
        original = f.read()

    meta = json.loads(original)
    target = meta.get("target_host", "")
    if target:
        # Suffix the hostname part: "librechat:3080" -> "librechat_run001:3080"
        parts = target.split(":")
        if len(parts) == 2:
            meta["target_host"] = f"{parts[0]}_{run_id}:{parts[1]}"

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return original, meta_path


def patch_kali_network(run_id, net_name):
    """Temporarily patch kali_env_resource.py to use per-run network."""
    kali_path = os.path.join(BB_DIR, "resources", "kali_env_resource.py")
    with open(kali_path) as f:
        content = f.read()

    # Set env var that the patched kali reads
    os.environ["AEGIS_DOCKER_NETWORK"] = net_name


def run_task(args):
    """Execute a single isolated run."""
    run_id = args.run_id
    original_task_dir = args.task_dir
    bounty = args.bounty

    print(f"[{run_id}] Starting isolated run: {original_task_dir}/bounty_{bounty}", flush=True)
    print(f"[{run_id}] Phase: {args.phase}, Model: {args.model}", flush=True)

    t0 = time.time()

    # 1. Create isolated copy of the entire task directory
    task_dir, cleanup_task = create_isolated_task_dir(original_task_dir, run_id)
    print(f"[{run_id}] Isolated task_dir: {task_dir}", flush=True)

    # 2. Create per-run network
    net_name = create_run_network(run_id)
    print(f"[{run_id}] Network: {net_name}", flush=True)

    # 3. Generate isolated compose file (in the ISOLATED copy)
    original_system = os.path.basename(original_task_dir)
    compose_override = generate_isolated_compose(task_dir, run_id, net_name, original_system=original_system)
    if compose_override:
        print(f"[{run_id}] Compose override: {compose_override}", flush=True)

    # 4. Update target_host (in the ISOLATED copy's metadata)
    original_meta, meta_path = update_target_host(task_dir, run_id)

    # 4. Set environment for the runner
    env = os.environ.copy()
    env["COMPOSE_PROJECT_NAME"] = f"aegis_{run_id}"
    env["AEGIS_DOCKER_NETWORK"] = net_name
    env["COMPOSE_FILE"] = compose_override if compose_override else ""

    # 5. Start service stack (if Docker task with compose)
    service_started = False
    if compose_override:
        print(f"[{run_id}] Starting service stack (pre-built images, no build)...", flush=True)
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_override, "up", "-d", "--no-build"],
                cwd=os.path.join(BB_DIR, task_dir),
                capture_output=True, text=True, timeout=300,
                env=env
            )
        except subprocess.TimeoutExpired:
            print(f"[{run_id}] Service stack timed out (300s) — will clean up", flush=True)
            result = type('R', (), {'returncode': 1, 'stderr': 'timeout'})()
        if result.returncode == 0:
            service_started = True
            print(f"[{run_id}] Service stack up", flush=True)
        else:
            print(f"[{run_id}] Service stack failed: {result.stderr[:200]}", flush=True)

    # 6. Run the workflow (kali_env_resource reads AEGIS_DOCKER_NETWORK from env)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "workflows.runner",
             "--workflow-type", args.phase,
             "--task_dir", task_dir,
             "--bounty_number", bounty,
             "--model", args.model,
             "--phase_iterations", str(args.iters),
             "--max_input_tokens", str(args.max_input),
             "--max_output_tokens", str(args.max_output),
             "--logging_level", "INFO"],
            capture_output=True, text=True, timeout=args.timeout,
            cwd=BB_DIR, env=env
        )

        elapsed = time.time() - t0
        output = proc.stdout + proc.stderr

        if "success=True" in output:
            result = "PASS"
        elif proc.returncode != 0:
            result = "INFRA"
        else:
            result = "FAIL"

        # Extract tokens from logs
        tokens_in = 0
        for line in output.split("\n"):
            if "total_input_tokens" in line:
                try:
                    tokens_in = int(re.search(r"total_input_tokens.*?(\d+)", line).group(1))
                except:
                    pass

        print(f"[{run_id}] {result} ({elapsed:.0f}s, rc={proc.returncode}, tokens={tokens_in})", flush=True)
        if result == "INFRA":
            # Print last 10 lines of output for diagnosis
            for line in output.strip().split("\n")[-10:]:
                print(f"  | {line}", flush=True)

    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        result = "TIMEOUT"
        tokens_in = 0
        print(f"[{run_id}] TIMEOUT ({elapsed:.0f}s)", flush=True)
    except Exception as e:
        elapsed = time.time() - t0
        result = "ERROR"
        tokens_in = 0
        print(f"[{run_id}] ERROR: {e}", flush=True)
    finally:
        # No need to restore metadata — it's in the isolated copy which gets deleted

        # Tear down service stack
        if compose_override and service_started:
            subprocess.run(
                ["docker", "compose", "-f", compose_override, "down", "--remove-orphans", "-v"],
                cwd=os.path.join(BB_DIR, task_dir),
                capture_output=True, timeout=60, env=env
            )

        # Clean up compose override file
        if compose_override and os.path.exists(compose_override):
            os.remove(compose_override)

        # Remove per-run network
        remove_run_network(net_name)

        # Remove isolated task directory
        cleanup_task()

    return {"run_id": run_id, "result": result, "elapsed_s": round(elapsed, 1),
            "tokens_in": tokens_in}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_dir", required=True)
    parser.add_argument("--bounty", required=True)
    parser.add_argument("--run_id", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--model", default="openai/deepseek-v4-flash")
    parser.add_argument("--iters", type=int, default=30)
    parser.add_argument("--max_input", type=int, default=16384)
    parser.add_argument("--max_output", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    os.chdir(BB_DIR)
    result = run_task(args)
    print(json.dumps(result))
