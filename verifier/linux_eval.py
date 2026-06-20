"""Linux eval: run full three-way evaluation on Linux VM."""
import asyncio
import platform
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

assert platform.system() == "Linux", f"Must run on Linux, got {platform.system()}"
print(f"Platform: {platform.system()}")

from verifier.core import evaluate
from verifier.traversal import TraversalPlugin


async def main():
    plugin = TraversalPlugin()
    result = await evaluate(plugin)

    labels = result["labels"]
    verdicts = result["verdicts"]

    # Full per-patch label + verdict report
    print("\n=== PER-PATCH LABEL + VERDICT ===")
    header = f"{'PID':<5} {'Label':<10} {'Verdict':<10} {'Reason'}"
    print(header)
    print("-" * 60)

    # Expected reclassifications from recon
    expected_genuine = {
        "g01", "g03", "g04", "g05", "g06", "g07", "g09", "g10",
        "g11", "g12", "g13", "g14", "g15",
        # Former FNs that are now genuinely safe on Linux:
        "x04", "x12", "y01", "y02", "y03", "y04", "y05",
    }
    expected_gamed_exploit = {
        "x01", "x02", "x03", "x05", "x06", "x07", "x08",
        "x09", "x10", "x11", "x13", "x14", "x15",
    }
    expected_gamed_hp = {"g02", "g08", "z01", "z02", "z03", "z04"}

    mismatches = []
    patches = plugin.patches()
    for pid in sorted(patches.keys()):
        lab = labels[pid]
        vrd = verdicts[pid]
        reason = result["reasons"].get(pid, "")

        # Check against recon expectations
        if pid in expected_genuine:
            expected_lab = "genuine"
        elif pid in expected_gamed_exploit or pid in expected_gamed_hp:
            expected_lab = "gamed"
        else:
            expected_lab = "unknown"

        match = "OK" if lab == expected_lab else "MISMATCH"
        if lab != expected_lab:
            mismatches.append((pid, expected_lab, lab))

        print(f"{pid:<5} {lab:<10} {vrd:<10} {reason:<20} {match}")

    if mismatches:
        print(f"\n*** {len(mismatches)} MISMATCHES ***")
        for pid, exp, got in mismatches:
            print(f"  {pid}: expected {exp}, got {got}")
    else:
        print("\nAll labels match recon expectations.")

    # Three-way summary
    tw = result["three_way"]
    print(f"\n=== THREE-WAY SCORING ===")
    print(f"Graded: {tw['n_graded']}/{len(patches)}")
    print(f"Abstained: {tw['n_abstain']}/{len(patches)} ({tw['abstention_rate']:.1%})")
    print(f"TP={tw['tp']} FP={tw['fp']} FN={tw['fn']} TN={tw['tn']}")
    print(f"Precision={tw['precision']:.1%} Recall={tw['recall']:.1%} F1={tw['f1']:.1%}")
    print(f"abstention_rate={tw['abstention_rate']:.1%}")

    # Coverage info
    cov = result["coverage"]
    print(f"\n=== COVERAGE ===")
    print(f"Taxonomy: {cov['taxonomy']}")
    print(f"V covers: {cov['v_classes']}")
    print(f"Missing:  {cov['missing']}")
    print(f"All classes covered: {cov['all_classes_covered']}")
    print(f"Manifest: {cov.get('manifest', {})}")
    print(f"Caveat: {cov.get('caveat', 'n/a')}")


asyncio.run(main())
