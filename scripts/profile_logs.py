#!/usr/bin/env python3
"""Profile existing BountyBench run logs to understand time breakdown."""
import json, os, glob, statistics
from datetime import datetime

BB_DIR = "/home/ppeng/bountybench"
LOG_BASE = os.path.join(BB_DIR, "logs")

DOCKER_TASKS = {"mlflow_0", "mlflow_1", "gradio_2", "lunary_0", "LibreChat_4"}
NON_DOCKER_TASKS = {"langchain_0", "langchain_1", "bentoml_1", "vllm_0"}


def parse_ts(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("+0000", "+00:00"))
    except Exception:
        return None


def analyze_log(log_path):
    try:
        d = json.load(open(log_path))
    except Exception:
        return None

    wu = d.get("workflow_usage", {})
    total_input = wu.get("total_input_tokens", 0)
    total_query_ms = wu.get("total_query_time_taken_in_ms", 0)

    if total_input == 0:
        return None

    start_time = parse_ts(d.get("start_time", ""))
    end_time = parse_ts(d.get("end_time", ""))
    if not start_time or not end_time:
        return None

    if start_time.tzinfo:
        start_time = start_time.replace(tzinfo=None)
    if end_time.tzinfo:
        end_time = end_time.replace(tzinfo=None)

    total_wall_s = (end_time - start_time).total_seconds()
    if total_wall_s <= 0:
        return None

    phase_msgs = d.get("phase_messages", [])
    if not phase_msgs:
        return None

    pm = phase_msgs[0]
    agent_msgs = pm.get("agent_messages", [])
    if not agent_msgs:
        return None

    turn_times_ms = []
    turn_timestamps = []

    for am in agent_msgs:
        if not isinstance(am, dict):
            continue
        agent_id = am.get("agent_id", "")
        if agent_id == "system":
            continue

        iter_time = am.get("iteration_time_ms")
        if iter_time and iter_time > 0:
            turn_times_ms.append(iter_time)

        ts = parse_ts(am.get("timestamp", ""))
        if ts:
            if ts.tzinfo:
                ts = ts.replace(tzinfo=None)
            turn_timestamps.append(ts)

    if not turn_timestamps:
        return None

    first_turn = min(turn_timestamps)
    last_turn = max(turn_timestamps)

    t_setup_s = max(0, (first_turn - start_time).total_seconds())
    t_agentloop_s = max(0, (last_turn - first_turn).total_seconds())
    t_teardown_s = max(0, (end_time - last_turn).total_seconds())

    path_parts = log_path.split("/")
    task_name = None
    for i, p in enumerate(path_parts):
        if p in ("ExploitWorkflow", "DetectWorkflow") and i + 1 < len(path_parts):
            task_name = path_parts[i + 1]
            break

    is_docker = task_name in DOCKER_TASKS
    llm_calls = len(turn_times_ms)

    return {
        "task": task_name,
        "is_docker": is_docker,
        "total_wall_s": total_wall_s,
        "t_setup_s": t_setup_s,
        "t_agentloop_s": t_agentloop_s,
        "t_teardown_s": t_teardown_s,
        "total_llm_ms": total_query_ms,
        "llm_calls": llm_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": wu.get("total_output_tokens", 0),
        "turn_times_ms": turn_times_ms,
        "path": log_path,
    }


def main():
    all_logs = glob.glob(os.path.join(LOG_BASE, "2026-*/*Workflow/*/*/*/*.json"))
    all_logs += glob.glob(os.path.join(LOG_BASE, "2026-*/*Workflow/*/*.json"))
    all_logs += glob.glob(os.path.join(LOG_BASE, "2026-*/*Workflow/*/*/*.json"))
    all_logs = list(set(all_logs))
    print("Found %d log files" % len(all_logs))

    results = []
    for lp in all_logs:
        r = analyze_log(lp)
        if r:
            results.append(r)

    print("Valid runs (non-empty): %d\n" % len(results))

    if not results:
        print("No valid runs found. Exiting.")
        return

    # 1. Per-run anatomy
    print("=" * 80)
    print("1. PER-RUN ANATOMY (setup / agent-loop / teardown)")
    print("=" * 80)

    docker_runs = [r for r in results if r["is_docker"]]
    non_docker_runs = [r for r in results if not r["is_docker"]]

    for label, runs in [("DOCKER", docker_runs), ("NON-DOCKER", non_docker_runs)]:
        if not runs:
            continue
        print("\n  %s (%d runs):" % (label, len(runs)))
        fmt = "  %-15s %3s %7s %7s %7s %7s %7s %7s %7s"
        print(fmt % ("Task", "N", "Total", "Setup", "Agent", "Tear", "Setup%", "Agent%", "Tear%"))
        print(fmt % ("-" * 15, "---", "-----", "-----", "-----", "----", "------", "------", "-----"))

        by_task = {}
        for r in runs:
            by_task.setdefault(r["task"], []).append(r)

        for task in sorted(by_task):
            task_runs = by_task[task]
            n = len(task_runs)
            avg_total = statistics.mean([r["total_wall_s"] for r in task_runs])
            avg_setup = statistics.mean([r["t_setup_s"] for r in task_runs])
            avg_agent = statistics.mean([r["t_agentloop_s"] for r in task_runs])
            avg_tear = statistics.mean([r["t_teardown_s"] for r in task_runs])
            ps = avg_setup / avg_total * 100 if avg_total else 0
            pa = avg_agent / avg_total * 100 if avg_total else 0
            pt = avg_tear / avg_total * 100 if avg_total else 0
            print("  %-15s %3d %6.0fs %6.0fs %6.0fs %6.0fs %6.1f%% %6.1f%% %6.1f%%" %
                  (task, n, avg_total, avg_setup, avg_agent, avg_tear, ps, pa, pt))

        avg_total = statistics.mean([r["total_wall_s"] for r in runs])
        avg_setup = statistics.mean([r["t_setup_s"] for r in runs])
        avg_agent = statistics.mean([r["t_agentloop_s"] for r in runs])
        avg_tear = statistics.mean([r["t_teardown_s"] for r in runs])
        ps = avg_setup / avg_total * 100 if avg_total else 0
        pa = avg_agent / avg_total * 100 if avg_total else 0
        pt = avg_tear / avg_total * 100 if avg_total else 0
        print("  %-15s %3d %6.0fs %6.0fs %6.0fs %6.0fs %6.1f%% %6.1f%% %6.1f%%" %
              ("AVERAGE", len(runs), avg_total, avg_setup, avg_agent, avg_tear, ps, pa, pt))

    # 2. Inside the agent loop
    print("\n" + "=" * 80)
    print("2. INSIDE THE AGENT LOOP (LLM time vs total)")
    print("=" * 80)

    fmt2 = "  %-15s %3s %9s %12s %9s %10s %6s"
    print(fmt2 % ("Task", "N", "AvgTurns", "AvgLLM/turn", "TotalLLM", "TotalWall", "LLM%"))
    print(fmt2 % ("-" * 15, "---", "---------", "-----------", "--------", "---------", "----"))

    by_task = {}
    for r in results:
        by_task.setdefault(r["task"], []).append(r)

    for task in sorted(by_task):
        task_runs = by_task[task]
        n = len(task_runs)
        avg_turns = statistics.mean([r["llm_calls"] for r in task_runs])
        all_tt = []
        for r in task_runs:
            all_tt.extend(r["turn_times_ms"])
        avg_per_turn_s = statistics.mean(all_tt) / 1000 if all_tt else 0
        avg_llm_s = statistics.mean([r["total_llm_ms"] / 1000 for r in task_runs])
        avg_wall = statistics.mean([r["total_wall_s"] for r in task_runs])
        pct = avg_llm_s / avg_wall * 100 if avg_wall else 0
        print("  %-15s %3d %8.1f %10.1fs %7.0fs %8.0fs %5.1f%%" %
              (task, n, avg_turns, avg_per_turn_s, avg_llm_s, avg_wall, pct))

    avg_turns = statistics.mean([r["llm_calls"] for r in results])
    avg_llm_s = statistics.mean([r["total_llm_ms"] / 1000 for r in results])
    avg_wall = statistics.mean([r["total_wall_s"] for r in results])
    pct = avg_llm_s / avg_wall * 100 if avg_wall else 0
    print("  %-15s %3d %8.1f %12s %7.0fs %8.0fs %5.1f%%" %
          ("ALL", len(results), avg_turns, "", avg_llm_s, avg_wall, pct))

    # Per-turn distribution
    print("\n  Per-turn duration distribution (all tasks):")
    all_turn_ms = []
    for r in results:
        all_turn_ms.extend(r["turn_times_ms"])
    if all_turn_ms:
        all_turn_ms.sort()
        n = len(all_turn_ms)
        print("    p10=%.1fs  p50=%.1fs  p90=%.1fs  max=%.1fs  n=%d" % (
            all_turn_ms[n // 10] / 1000,
            all_turn_ms[n // 2] / 1000,
            all_turn_ms[9 * n // 10] / 1000,
            all_turn_ms[-1] / 1000,
            n))

    # 3. Token economics
    print("\n" + "=" * 80)
    print("3. TOKEN & COST ECONOMICS")
    print("=" * 80)
    total_in = sum(r["total_input_tokens"] for r in results)
    total_out = sum(r["total_output_tokens"] for r in results)
    total_wall_hrs = sum(r["total_wall_s"] for r in results) / 3600
    cost = total_in * 0.14 / 1e6 + total_out * 0.28 / 1e6
    print("  Total runs: %d" % len(results))
    print("  Total input tokens: {:,}".format(total_in))
    print("  Total output tokens: {:,}".format(total_out))
    print("  Total wall time: %.1f hrs" % total_wall_hrs)
    print("  Total DeepSeek cost: $%.4f" % cost)
    print("  Avg tokens/run: {:,.0f} in, {:,.0f} out".format(
        total_in / len(results), total_out / len(results)))

    # 4. Docker setup detail
    print("\n" + "=" * 80)
    print("4. DOCKER SETUP TIME DETAIL")
    print("=" * 80)
    for task in sorted(by_task):
        task_runs = by_task[task]
        if task not in DOCKER_TASKS:
            continue
        setups = [r["t_setup_s"] for r in task_runs]
        if setups:
            print("  %s: min=%.0fs  avg=%.0fs  max=%.0fs  n=%d" %
                  (task, min(setups), statistics.mean(setups), max(setups), len(setups)))

    # 5. Non-Docker setup detail
    print("\n" + "=" * 80)
    print("5. NON-DOCKER SETUP TIME DETAIL")
    print("=" * 80)
    for task in sorted(by_task):
        task_runs = by_task[task]
        if task in DOCKER_TASKS:
            continue
        setups = [r["t_setup_s"] for r in task_runs]
        if setups:
            print("  %s: min=%.0fs  avg=%.0fs  max=%.0fs  n=%d" %
                  (task, min(setups), statistics.mean(setups), max(setups), len(setups)))


if __name__ == "__main__":
    main()
