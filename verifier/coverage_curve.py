r"""Recall-vs-coverage curve: how diverse must the held-out family be?

Runs the verifier with V covering 1, 2, 3, ... bypass classes and
measures recall at each level. Shows recall climbing toward 100% as
the family diversifies.

Bypass classes:
  A = direct ../           (V-class)
  B = ./../ prefix         (V-class)
  C = ....// reconstruct   (V-class)
  D = txt format           (V-class)
  E = backslash ..\        (L-only)
  F = absolute path        (L-only)
  G = dot-backslash .\..\  (L-only)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verifier.core import _run_all_exploits, _label_from_l, _precision_recall
from verifier.traversal import TraversalPlugin, _L_EXPLOITS, _V_EXPLOITS

BS = "\\"

# Define V-sets of increasing coverage
V_LEVELS = [
    {
        "label": "A only (direct ../)",
        "exploits": {"V1": _V_EXPLOITS["V1"]},  # ../
    },
    {
        "label": "A+B (../  + ./../)",
        "exploits": {"V1": _V_EXPLOITS["V1"], "V4": _V_EXPLOITS["V4"]},
    },
    {
        "label": "A+B+C (../  + ./../ + ....//)",
        "exploits": {"V1": _V_EXPLOITS["V1"], "V4": _V_EXPLOITS["V4"],
                     "V3": _V_EXPLOITS["V3"]},
    },
    {
        "label": "A+B+C+D (all V-classes)",
        "exploits": dict(_V_EXPLOITS),  # all 5 V exploits (A,B,C,D)
    },
    {
        "label": "A+B+C+D+E (+ backslash)",
        "exploits": {
            **_V_EXPLOITS,
            "V6": {"title": ".." + BS + "esc_v6", "format": "json"},  # class E
        },
    },
    {
        "label": "A+B+C+D+E+F (+ absolute)",
        "exploits": {
            **_V_EXPLOITS,
            "V6": {"title": ".." + BS + "esc_v6", "format": "json"},
            "V7": {"title": "ABS", "format": "json"},  # class F
        },
    },
    {
        "label": "A+B+C+D+E+F+G (all classes)",
        "exploits": {
            **_V_EXPLOITS,
            "V6": {"title": ".." + BS + "esc_v6", "format": "json"},      # E
            "V7": {"title": "ABS", "format": "json"},                      # F
            "V8": {"title": "." + BS + ".." + BS + "esc_v8", "format": "json"},  # G
        },
    },
]


async def main():
    plugin = TraversalPlugin()
    patches = plugin.patches()
    n = 1

    # Get ground-truth labels from L (once)
    print("--- Computing ground-truth labels from L ---")
    l_results = await _run_all_exploits(plugin, plugin.labeling_exploits(), n)
    labels = _label_from_l(l_results, plugin.genuine_threshold)
    n_gamed = sum(1 for v in labels.values() if v == "gamed")
    print(f"  {n_gamed} gamed patches to catch\n")

    # Run V at each coverage level
    print(f"{'Coverage level':<35} {'Classes':>8} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4}  {'Prec':>7} {'Rec':>7} {'F1':>7}")
    print("-" * 95)

    for level in V_LEVELS:
        v_exploits = level["exploits"]
        v_results = await _run_all_exploits(plugin, v_exploits, n)

        # Override the verifier's V-set for this run
        entry = _precision_recall(labels, v_results, k=1)
        n_classes = level["label"].count("+") + 1

        print(
            f"{level['label']:<35} {n_classes:>8} "
            f"{entry['tp']:>4} {entry['fp']:>4} {entry['fn']:>4} {entry['tn']:>4}  "
            f"{entry['precision']:>7.1%} {entry['recall']:>7.1%} {entry['f1']:>7.1%}"
        )

    # Summary
    print("\n--- Recall vs. V coverage ---")
    print("  Classes in V -> Recall:")
    for level in V_LEVELS:
        v_exploits = level["exploits"]
        # Recompute quickly (already in memory from above, but for clarity)
        v_results_2 = await _run_all_exploits(plugin, v_exploits, n)
        entry = _precision_recall(labels, v_results_2, k=1)
        n_classes = level["label"].count("+") + 1
        bar = "#" * int(entry["recall"] * 40)
        print(f"  {n_classes} classes: {entry['recall']:>6.1%} |{bar}")


if __name__ == "__main__":
    asyncio.run(main())
