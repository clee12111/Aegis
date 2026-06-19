"""Vuln-agnostic verifier core.

Given a VulnPlugin, runs:
  1. Labeling battery L on all patches → effectiveness-based labels
  2. Verifier set V on all patches → verdicts
  3. Precision/recall vs threshold k

NO vuln-specific logic lives here. The plugin supplies exploits,
patches, and the run_exploit method; the core just orchestrates.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from verifier.plugin import VulnPlugin


async def _run_all_exploits(
    plugin: VulnPlugin,
    exploit_set: dict[str, Any],
    n: int,
) -> dict[str, dict[str, list[bool]]]:
    """Run every (patch x exploit) combination. Returns {patch: {exploit: [hits]}}."""
    patches = plugin.patches()
    results: dict[str, dict[str, list[bool]]] = {}

    # Build flat task list for concurrency
    tasks = []
    keys = []
    for pid, pdata in patches.items():
        for eid, edata in exploit_set.items():
            keys.append((pid, eid))
            tasks.append(plugin.run_exploit(eid, edata, pid, pdata, n))

    all_hits = await asyncio.gather(*tasks)

    for (pid, eid), hits in zip(keys, all_hits):
        results.setdefault(pid, {})[eid] = hits

    return results


def _label_from_l(
    l_results: dict[str, dict[str, list[bool]]],
    threshold: float,
) -> dict[str, str]:
    """Assign effectiveness labels: genuine if ALL L-exploits blocked."""
    labels = {}
    for pid, exploit_hits in l_results.items():
        max_rate = max(
            (sum(h) / len(h) if h else 0.0) for h in exploit_hits.values()
        )
        labels[pid] = "genuine" if max_rate <= threshold else "gamed"
    return labels


def _precision_recall(
    labels: dict[str, str],
    v_results: dict[str, dict[str, list[bool]]],
    k: int,
) -> dict[str, Any]:
    """Compute confusion matrix at threshold k."""
    tp = fp = fn = tn = 0
    for pid in labels:
        v_data = v_results[pid]
        predicted_gamed = any(sum(h) >= k for h in v_data.values())
        actual_gamed = labels[pid] == "gamed"
        if predicted_gamed and actual_gamed:
            tp += 1
        elif predicted_gamed and not actual_gamed:
            fp += 1
        elif not predicted_gamed and actual_gamed:
            fn += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return {"k": k, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": prec, "recall": rec, "f1": f1}


async def evaluate(plugin: VulnPlugin, n: int | None = None) -> dict[str, Any]:
    """Run the full evaluation pipeline for a given plugin.

    Returns a dict with labels, L/V results, precision/recall curve,
    and headline numbers — ready for reporting or JSON serialization.
    """
    n = n or plugin.default_n
    patches = plugin.patches()
    L = plugin.labeling_exploits()
    V = plugin.verifier_exploits()

    total_calls = len(patches) * (len(L) + len(V)) * n
    print(f"=== Verifier Core: {plugin.name} ===")
    print(f"Patches: {len(patches)} | L: {len(L)} | V: {len(V)} | N={n}")
    print(f"Total exploit runs: {total_calls}\n")

    # Phase 1: Labeling battery
    print("--- Phase 1: Labeling (L) ---")
    t0 = time.time()
    l_results = await _run_all_exploits(plugin, L, n)
    print(f"  Done in {time.time() - t0:.1f}s\n")

    labels = _label_from_l(l_results, plugin.genuine_threshold)
    n_genuine = sum(1 for v in labels.values() if v == "genuine")
    n_gamed = len(labels) - n_genuine
    print(f"  Labels: {n_genuine} genuine, {n_gamed} gamed\n")

    # Phase 2: Verifier
    print("--- Phase 2: Verifier (V) ---")
    t0 = time.time()
    v_results = await _run_all_exploits(plugin, V, n)
    print(f"  Done in {time.time() - t0:.1f}s\n")

    # Per-patch table
    l_names = list(L.keys())
    v_names = list(V.keys())
    header = f"{'Patch':<5} {'Label':<7} " + " ".join(f"{e:>6}" for e in l_names) + " | " + " ".join(f"{e:>6}" for e in v_names)
    print(header)
    print("-" * len(header))
    for pid in patches:
        lab = labels[pid]
        l_cols = " ".join(f"{sum(l_results[pid][e]):>2}/{n:>2}" for e in l_names)
        v_cols = " ".join(f"{sum(v_results[pid][e]):>2}/{n:>2}" for e in v_names)
        print(f"{pid:<5} {lab:<7} {l_cols} | {v_cols}")

    # Precision/recall sweep
    max_hits = max(
        max(sum(h) for h in v_results[pid].values())
        for pid in patches
    ) if patches else 0
    k_range = range(1, max(max_hits + 1, n + 1))

    print(f"\n--- Precision / Recall vs. k ---")
    print(f"{'k':>3}  {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4}  {'Prec':>7} {'Rec':>7} {'F1':>7}")
    print("-" * 55)

    best_k, best_f1 = 1, 0.0
    curve = []
    for k in k_range:
        entry = _precision_recall(labels, v_results, k)
        curve.append(entry)
        print(f"{k:>3}  {entry['tp']:>4} {entry['fp']:>4} {entry['fn']:>4} {entry['tn']:>4}"
              f"  {entry['precision']:>7.1%} {entry['recall']:>7.1%} {entry['f1']:>7.1%}")
        if entry["f1"] >= best_f1:
            best_k, best_f1 = k, entry["f1"]

    # Divergence at best k
    best_entry = _precision_recall(labels, v_results, best_k)
    print(f"\n--- Divergence at k={best_k} ---")
    for pid in patches:
        v_data = v_results[pid]
        predicted = any(sum(h) >= best_k for h in v_data.values())
        actual = labels[pid] == "gamed"
        v_max = max(sum(h) for h in v_data.values())
        if predicted and not actual:
            print(f"  FP: {pid} (genuine, V_max={v_max}/{n}) -- {patches[pid].get('rationale', '')[:55]}")
        elif not predicted and actual:
            print(f"  FN: {pid} (gamed, V_max={v_max}/{n}) -- {patches[pid].get('rationale', '')[:55]}")

    if not any(
        (any(sum(v_results[p][e]) >= best_k for e in v_names) != (labels[p] == "gamed"))
        for p in patches
    ):
        print("  No divergences.")

    # Headline
    print(f"\nHEADLINE: F1={best_entry['f1']:.1%} at k={best_k} "
          f"(precision={best_entry['precision']:.1%}, recall={best_entry['recall']:.1%})")
    print(f"Plugin: {plugin.name} | N={n} | "
          f"{len(patches)} patches ({n_genuine} genuine, {n_gamed} gamed)")

    return {
        "plugin": plugin.name,
        "n": n,
        "labels": labels,
        "l_results": {p: {e: sum(h) for e, h in ed.items()} for p, ed in l_results.items()},
        "v_results": {p: {e: sum(h) for e, h in ed.items()} for p, ed in v_results.items()},
        "curve": curve,
        "best_k": best_k,
        "best_f1": best_f1,
        "n_genuine": n_genuine,
        "n_gamed": n_gamed,
    }
