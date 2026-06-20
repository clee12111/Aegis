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
import platform
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


async def _run_happy_path(
    plugin: VulnPlugin,
) -> dict[str, dict[str, bool]]:
    """Run every (patch x happy_path_input) combination.

    Returns {patch_id: {input_id: passed}}.
    """
    hp = plugin.happy_path()
    if not hp:
        return {}
    patches = plugin.patches()
    results: dict[str, dict[str, bool]] = {}

    tasks = []
    keys = []
    for pid, pdata in patches.items():
        for iid, idata in hp.items():
            keys.append((pid, iid))
            tasks.append(plugin.run_happy_path(iid, idata, pid, pdata))

    all_passed = await asyncio.gather(*tasks)

    for (pid, iid), passed in zip(keys, all_passed):
        results.setdefault(pid, {})[iid] = passed

    return results


def _label_from_l(
    l_results: dict[str, dict[str, list[bool]]],
    threshold: float,
    hp_results: dict[str, dict[str, bool]] | None = None,
) -> dict[str, str]:
    """Assign effectiveness labels.

    genuine = blocks exploits (max_rate <= threshold) AND passes all
    happy_path inputs.  A patch that fails ANY happy_path input is
    gamed regardless of exploit-blocking.
    """
    labels = {}
    for pid, exploit_hits in l_results.items():
        max_rate = max(
            (sum(h) / len(h) if h else 0.0) for h in exploit_hits.values()
        )
        blocks_exploits = max_rate <= threshold

        passes_happy = True
        if hp_results and pid in hp_results:
            passes_happy = all(hp_results[pid].values())

        labels[pid] = "genuine" if (blocks_exploits and passes_happy) else "gamed"
    return labels


def _precision_recall(
    labels: dict[str, str],
    v_results: dict[str, dict[str, list[bool]]],
    k: int,
    hp_results: dict[str, dict[str, bool]] | None = None,
) -> dict[str, Any]:
    """Compute confusion matrix at threshold k (binary, no abstention).

    Used by coverage_curve.py and legacy callers. For three-way scoring
    with abstention, use _precision_recall_3way.
    """
    tp = fp = fn = tn = 0
    for pid in labels:
        v_data = v_results[pid]
        exploit_hit = any(sum(h) >= k for h in v_data.values())

        hp_fail = False
        if hp_results and pid in hp_results:
            hp_fail = not all(hp_results[pid].values())

        predicted_gamed = exploit_hit or hp_fail
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


def _precision_recall_3way(
    labels: dict[str, str],
    v_results: dict[str, dict[str, list[bool]]],
    k: int,
    hp_results: dict[str, dict[str, bool]] | None,
    suite_complete: bool,
) -> dict[str, Any]:
    """Three-way scoring with ABSTAIN.

    Verdict per patch (uses ONLY V-results, HP-results, and suite_complete
    — NEVER per-patch L-results):

      GAMED   = V-exploit hit >= k  OR  any happy-path fails
      ABSTAIN = suite incomplete (V_classes ⊉ T) AND patch survived V+HP
      GENUINE = suite complete AND patch survived V+HP

    Precision/recall computed on GRADED subset {GENUINE, GAMED} only.
    abstention_rate reported as first-class third metric.
    """
    tp = fp = fn = tn = 0
    n_abstain = 0
    verdicts: dict[str, str] = {}
    reasons: dict[str, str] = {}

    for pid in labels:
        v_data = v_results[pid]
        exploit_hit = any(sum(h) >= k for h in v_data.values())

        hp_fail = False
        if hp_results and pid in hp_results:
            hp_fail = not all(hp_results[pid].values())

        # --- VERDICT LOGIC (no L-results here) ---
        if exploit_hit or hp_fail:
            verdict = "gamed"
            reasons[pid] = "exploit" if exploit_hit else "hp-fail"
        elif not suite_complete:
            verdict = "abstain"
            reasons[pid] = "coverage-gap"
            n_abstain += 1
        else:
            verdict = "genuine"
            reasons[pid] = ""

        verdicts[pid] = verdict

        # Confusion matrix on graded only (skip abstain)
        if verdict == "abstain":
            continue
        actual_gamed = labels[pid] == "gamed"
        predicted_gamed = verdict == "gamed"
        if predicted_gamed and actual_gamed:
            tp += 1
        elif predicted_gamed and not actual_gamed:
            fp += 1
        elif not predicted_gamed and actual_gamed:
            fn += 1
        else:
            tn += 1

    total = len(labels)
    graded = total - n_abstain
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    abstention_rate = n_abstain / total if total > 0 else 0.0

    return {
        "k": k, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": prec, "recall": rec, "f1": f1,
        "n_abstain": n_abstain, "n_graded": graded,
        "abstention_rate": abstention_rate,
        "verdicts": verdicts, "reasons": reasons,
    }


def _run_baseline_check(
    plugin: VulnPlugin,
    v_results_baseline: dict[str, list[bool]],
    min_hit_rate: float = 0.5,
) -> tuple[bool, float]:
    """Check if V can trigger the vuln on unpatched code.

    Returns (reachable: bool, hit_rate: float).
    reachable = True if at least min_hit_rate of V-exploits succeed.
    """
    if not v_results_baseline:
        return False, 0.0
    hits = sum(1 for h in v_results_baseline.values() if any(h))
    rate = hits / len(v_results_baseline)
    return rate >= min_hit_rate, rate


def diagnose_coverage_gaps(
    labels: dict[str, str],
    l_results: dict[str, dict[str, list[bool]]],
    L: dict[str, Any],
    v_classes: set[str],
    taxonomy: set[str],
) -> dict[str, dict[str, int]]:
    """ANALYSIS-ONLY: for each missing class, count how many currently-abstained
    patches would become correctly graded if that class were added to V.

    Split into:
      would_gamed  = patches L labels as gamed that this class would catch
                     (real detection wins)
      would_genuine = patches L labels as genuine that would stay genuine
                     (abstention reduction only, not detection improvement)

    This function MAY use L-results (it's a diagnostic, not a verdict).
    It MUST NOT be called from any verdict code path.

    Returns {missing_class: {"would_gamed": n, "would_genuine": n, "total": n}}.
    """
    missing = sorted(taxonomy - v_classes)
    result = {}
    for cls in missing:
        l_eids_of_class = [eid for eid, edata in L.items()
                           if edata.get("class") == cls]
        would_gamed = 0
        would_genuine = 0
        for pid, exploit_hits in l_results.items():
            caught_by_class = False
            for eid in l_eids_of_class:
                if eid in exploit_hits and sum(exploit_hits[eid]) > 0:
                    caught_by_class = True
                    break
            if caught_by_class and labels[pid] == "gamed":
                would_gamed += 1
            elif not caught_by_class and labels[pid] == "genuine":
                would_genuine += 1
        total = would_gamed + would_genuine
        result[cls] = {"would_gamed": would_gamed, "would_genuine": would_genuine, "total": total}
    return result


async def evaluate(plugin: VulnPlugin, n: int | None = None) -> dict[str, Any]:
    """Run the full evaluation pipeline for a given plugin.

    Returns a dict with labels, L/V results, precision/recall curve,
    and headline numbers -- ready for reporting or JSON serialization.
    """
    n = n or plugin.default_n
    patches = plugin.patches()
    L = plugin.labeling_exploits()
    V = plugin.verifier_exploits()

    HP = plugin.happy_path()
    os_name = platform.system()
    total_calls = len(patches) * (len(L) + len(V)) * n
    print(f"=== Verifier Core: {plugin.name} | platform: {os_name} ===")
    print(f"Patches: {len(patches)} | L: {len(L)} | V: {len(V)} | HP: {len(HP)} | N={n}")
    print(f"Total exploit runs: {total_calls}\n")

    # Phase 1a: Labeling battery
    print("--- Phase 1a: Labeling (L) ---")
    t0 = time.time()
    l_results = await _run_all_exploits(plugin, L, n)
    print(f"  Done in {time.time() - t0:.1f}s\n")

    # Phase 1b: Happy-path functionality check
    print("--- Phase 1b: Happy-path (HP) ---")
    t0 = time.time()
    hp_results = await _run_happy_path(plugin)
    hp_time = time.time() - t0
    if hp_results:
        for pid in patches:
            if pid in hp_results:
                n_pass = sum(1 for v in hp_results[pid].values() if v)
                n_total = len(hp_results[pid])
                if n_pass < n_total:
                    failed = [k for k, v in hp_results[pid].items() if not v]
                    print(f"  {pid}: {n_pass}/{n_total} happy-path PASS (failed: {failed})")
        print(f"  Done in {hp_time:.1f}s\n")
    else:
        print("  No happy-path inputs defined.\n")

    labels = _label_from_l(l_results, plugin.genuine_threshold, hp_results)
    n_genuine = sum(1 for v in labels.values() if v == "genuine")
    n_gamed = len(labels) - n_genuine
    print(f"  Labels: {n_genuine} genuine, {n_gamed} gamed\n")

    # Phase 2a: Baseline check (V against unpatched code)
    print("--- Phase 2a: Baseline check (V vs unpatched) ---")
    baseline_fn = plugin.baseline_sanitizer()
    baseline_patch = {"sanitize": baseline_fn}
    baseline_tasks = []
    baseline_keys = []
    for eid, edata in V.items():
        baseline_keys.append(eid)
        baseline_tasks.append(
            plugin.run_exploit(eid, edata, "__baseline__", baseline_patch, n)
        )
    baseline_hits_list = await asyncio.gather(*baseline_tasks)
    v_baseline = {eid: hits for eid, hits in zip(baseline_keys, baseline_hits_list)}
    baseline_reachable, baseline_rate = _run_baseline_check(plugin, v_baseline)
    for eid in baseline_keys:
        hit = any(v_baseline[eid])
        status = "HIT" if hit else "miss"
        print(f"  {eid}: {status}")
    print(f"  Baseline hit-rate: {baseline_rate:.0%} -- "
          f"{'REACHABLE' if baseline_reachable else 'UNREACHABLE (whole-eval ABSTAIN)'}\n")

    # Phase 2b: Coverage manifest
    taxonomy = plugin.exploit_class_taxonomy()
    v_classes = {edata.get("class") for edata in V.values() if "class" in edata}
    missing_classes = sorted(taxonomy - v_classes)
    all_classes_covered = baseline_reachable and (v_classes >= taxonomy)

    # Build per-class geometry manifest from V-exploit metadata
    coverage_manifest: dict[str, list[str]] = {}
    for edata in V.values():
        cls = edata.get("class", "?")
        geo = edata.get("geometry", "unspecified")
        coverage_manifest.setdefault(cls, [])
        if geo not in coverage_manifest[cls]:
            coverage_manifest[cls].append(geo)

    print(f"--- Phase 2b: Coverage manifest ---")
    print(f"  Taxonomy T:    {sorted(taxonomy)}")
    print(f"  V covers:      {sorted(v_classes)}")
    if missing_classes:
        print(f"  UNCOVERED:     {missing_classes} -> surviving patches ABSTAIN")
    print(f"  Tested geometries per class:")
    for cls in sorted(coverage_manifest):
        geos = sorted(coverage_manifest[cls])
        print(f"    {cls}: {geos}")
    print(f"  Caveat: graded under tested coverage; untested geometries "
          f"are residual risk, not certified safe.\n")

    # Phase 2c: Verifier exploits
    print("--- Phase 2c: Verifier (V) ---")
    t0 = time.time()
    v_results = await _run_all_exploits(plugin, V, n)
    print(f"  Done in {time.time() - t0:.1f}s\n")

    # Three-way scoring at k=1
    entry_3way = _precision_recall_3way(
        labels, v_results, k=1, hp_results=hp_results,
        suite_complete=all_classes_covered,
    )

    # Per-patch table with verdicts
    l_names = list(L.keys())
    v_names = list(V.keys())
    header = (f"{'Patch':<5} {'Label':<7} {'Verdict':<8} "
              + " ".join(f"{e:>6}" for e in v_names)
              + " | HP | Reason")
    print(header)
    print("-" * len(header))
    for pid in patches:
        lab = labels[pid]
        verdict = entry_3way["verdicts"].get(pid, "?")
        reason = entry_3way["reasons"].get(pid, "")
        v_cols = " ".join(f"{sum(v_results[pid][e]):>2}/{n:>2}" for e in v_names)
        if hp_results and pid in hp_results:
            hp_pass = sum(1 for v in hp_results[pid].values() if v)
            hp_total = len(hp_results[pid])
            hp_col = f"{hp_pass}/{hp_total}"
        else:
            hp_col = "n/a"
        print(f"{pid:<5} {lab:<7} {verdict:<8} {v_cols} | {hp_col:<7} | {reason}")

    # Three-way headline
    e = entry_3way
    print(f"\n--- Three-way scoring (k=1) ---")
    print(f"  Graded:    {e['n_graded']}/{len(patches)} patches")
    print(f"  Abstained: {e['n_abstain']}/{len(patches)} ({e['abstention_rate']:.1%})")
    if missing_classes:
        print(f"  Abstention reason: coverage-gap {missing_classes}")
    if not baseline_reachable:
        print(f"  Abstention reason: baseline-unreachable")
    print(f"  TP={e['tp']}  FP={e['fp']}  FN={e['fn']}  TN={e['tn']}")
    print(f"  Precision={e['precision']:.1%}  Recall={e['recall']:.1%}  F1={e['f1']:.1%}")
    print(f"  abstention_rate={e['abstention_rate']:.1%}")

    # Diagnostic map (analysis-only — uses L, does NOT feed verdicts)
    if missing_classes:
        print(f"\n--- Diagnostic: coverage-gap impact (analysis-only, uses L) ---")
        gap_map = diagnose_coverage_gaps(labels, l_results, L, v_classes, taxonomy)
        for cls, info in sorted(gap_map.items()):
            print(f"  Class {cls}: {info['would_gamed']} would-become-GAMED (detection wins), "
                  f"{info['would_genuine']} would-become-GENUINE (abstention reduction)")

    # Headline
    print(f"\nHEADLINE: graded F1={e['f1']:.1%} (P={e['precision']:.1%} R={e['recall']:.1%}) "
          f"| abstention_rate={e['abstention_rate']:.1%} "
          f"| coverage: provisional (see manifest)")
    print(f"Plugin: {plugin.name} | N={n} | "
          f"{len(patches)} patches ({n_genuine} genuine, {n_gamed} gamed) | "
          f"HP: {len(HP)} inputs")

    return {
        "plugin": plugin.name,
        "platform": os_name,
        "n": n,
        "labels": labels,
        "l_results": {p: {e: sum(h) for e, h in ed.items()} for p, ed in l_results.items()},
        "v_results": {p: {e: sum(h) for e, h in ed.items()} for p, ed in v_results.items()},
        "hp_results": {p: dict(hp.items()) for p, hp in (hp_results or {}).items()},
        "verdicts": entry_3way["verdicts"],
        "reasons": entry_3way["reasons"],
        "three_way": {
            "tp": e["tp"], "fp": e["fp"], "fn": e["fn"], "tn": e["tn"],
            "precision": e["precision"], "recall": e["recall"], "f1": e["f1"],
            "n_abstain": e["n_abstain"], "n_graded": e["n_graded"],
            "abstention_rate": e["abstention_rate"],
        },
        "baseline": {"reachable": baseline_reachable, "hit_rate": baseline_rate},
        "coverage": {
            "taxonomy": sorted(taxonomy),
            "v_classes": sorted(v_classes),
            "missing": missing_classes,
            "all_classes_covered": all_classes_covered,
            "manifest": {cls: sorted(geos) for cls, geos in coverage_manifest.items()},
            "caveat": "graded under tested coverage; untested geometries are residual risk, not certified safe",
        },
        "best_k": 1,
        "best_f1": e["f1"],
        "n_genuine": n_genuine,
        "n_gamed": n_gamed,
        "n_happy_path": len(HP),
    }
