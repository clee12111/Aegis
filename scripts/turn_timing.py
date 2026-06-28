#!/usr/bin/env python3
"""Detailed per-turn timing for a single run."""
import json, glob, os
from datetime import datetime

def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("+0000", "+00:00")).replace(tzinfo=None)
    except:
        return None

# Look at a langchain_1 run
logs = sorted(glob.glob("/home/ppeng/bountybench/logs/2026-*/ExploitWorkflow/langchain_1/*/*.json"), key=os.path.getsize, reverse=True)
d = json.load(open(logs[0]))
start = parse_ts(d["start_time"])
end = parse_ts(d["end_time"])
pm = d["phase_messages"][0]
fmt = "%H:%M:%S"
print("start: %s" % start.strftime(fmt))
print("phase_timestamp: %s" % pm.get("timestamp"))
print("end: %s" % end.strftime(fmt))
print("total: %.0fs" % (end - start).total_seconds())
print()

ams = pm.get("agent_messages", [])
print("Agent messages: %d" % len(ams))
prev_ts = start
for i, am in enumerate(ams):
    ts = parse_ts(am.get("timestamp", ""))
    if ts:
        delta = (ts - prev_ts).total_seconds()
        iter_ms = am.get("iteration_time_ms") or 0
        agent = am.get("agent_id", "?")
        iteration = am.get("iteration", "?")
        complete = am.get("complete", "?")
        print("  [%2d] %s dt=%6.0fs iter_ms=%8.0fms agent=%s iter=%s complete=%s" % (
            i, ts.strftime(fmt), delta, iter_ms, agent, iteration, complete))
        prev_ts = ts

delta = (end - prev_ts).total_seconds()
print("  [end] %s dt=%6.0fs (teardown)" % (end.strftime(fmt), delta))

# Also do vllm
print("\n\n=== VLLM_0 ===")
logs2 = sorted(glob.glob("/home/ppeng/bountybench/logs/2026-*/ExploitWorkflow/vllm_0/*/*.json"), key=os.path.getsize, reverse=True)
if logs2:
    d2 = json.load(open(logs2[0]))
    start2 = parse_ts(d2["start_time"])
    end2 = parse_ts(d2["end_time"])
    pm2 = d2["phase_messages"][0]
    print("start: %s" % start2.strftime(fmt))
    print("end: %s" % end2.strftime(fmt))
    print("total: %.0fs" % (end2 - start2).total_seconds())

    ams2 = pm2.get("agent_messages", [])
    print("Agent messages: %d" % len(ams2))
    prev_ts = start2
    for i, am in enumerate(ams2):
        ts = parse_ts(am.get("timestamp", ""))
        if ts:
            delta = (ts - prev_ts).total_seconds()
            iter_ms = am.get("iteration_time_ms") or 0
            agent = am.get("agent_id", "?")
            iteration = am.get("iteration", "?")
            print("  [%2d] %s dt=%6.0fs iter_ms=%8.0fms agent=%s iter=%s" % (
                i, ts.strftime(fmt), delta, iter_ms, agent, iteration))
            prev_ts = ts

    delta = (end2 - prev_ts).total_seconds()
    print("  [end] %s dt=%6.0fs (teardown)" % (end2.strftime(fmt), delta))
