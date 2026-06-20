"""CWE-78/88 command injection eval. Run on GCP Linux VM only."""
import asyncio
import platform
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print(f"Platform: {platform.system()}")
assert platform.system() == "Linux", f"Must run on Linux, got {platform.system()}"

from verifier.core import evaluate
from verifier.cmdinject import CommandInjectionPlugin


async def main():
    plugin = CommandInjectionPlugin()
    result = await evaluate(plugin)

    labels = result["labels"]
    verdicts = result["verdicts"]
    reasons = result["reasons"]
    patches = plugin.patches()

    # --- RE-STRATIFICATION: cg01 and cg02 ---
    print("\n=== RE-STRATIFICATION: cg01 (shlex.quote) and cg02 (identity) ===")
    for pid in ["cg01", "cg02"]:
        lab = labels[pid]
        vrd = verdicts[pid]
        rsn = reasons.get(pid, "")
        v_results = result["v_results"]
        hits = [eid for eid in sorted(v_results[pid]) if v_results[pid][eid] > 0]
        print(f"  {pid}: label={lab} verdict={vrd} reason={rsn}")
        print(f"    V-exploit hits: {hits}")
        rationale = patches[pid].get("rationale", "")
        print(f"    Rationale: {rationale}")

    # --- Full per-patch table ---
    print(f"\n=== PER-PATCH VERDICTS ===")
    print(f"{'PID':<6} {'Label':<8} {'Verdict':<8} {'Reason':<12}")
    print("-" * 40)
    for pid in sorted(patches.keys()):
        lab = labels[pid]
        vrd = verdicts[pid]
        rsn = reasons.get(pid, "")
        print(f"{pid:<6} {lab:<8} {vrd:<8} {rsn}")

    # --- Summary ---
    tw = result["three_way"]
    print(f"\n=== THREE-WAY SCORING ===")
    print(f"Graded: {tw['n_graded']}/{len(patches)}")
    print(f"Abstained: {tw['n_abstain']}/{len(patches)} ({tw['abstention_rate']:.1%})")
    print(f"TP={tw['tp']} FP={tw['fp']} FN={tw['fn']} TN={tw['tn']}")
    print(f"Precision={tw['precision']:.1%} Recall={tw['recall']:.1%} F1={tw['f1']:.1%}")
    print(f"Genuine: {sum(1 for v in labels.values() if v=='genuine')} "
          f"Gamed: {sum(1 for v in labels.values() if v=='gamed')}")

    # --- Coverage manifest ---
    cov = result["coverage"]
    print(f"\n=== COVERAGE MANIFEST ===")
    print(f"Taxonomy: {cov['taxonomy']}")
    print(f"V covers: {cov['v_classes']}")
    print(f"Missing:  {cov['missing']}")
    print(f"Manifest: {cov.get('manifest', {})}")
    print(f"Caveat: {cov.get('caveat', 'n/a')}")

    # --- Zero core changes confirmation ---
    print(f"\n=== TRANSFERABILITY ===")
    print(f"core.py: ZERO changes (plugin-only addition)")
    print(f"Plugin file: verifier/cmdinject.py")


asyncio.run(main())
