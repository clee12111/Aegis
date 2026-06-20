"""Linux eval with symlink coverage. Run on GCP VM only."""
import asyncio
import platform
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print(f"Platform: {platform.system()}")
assert platform.system() == "Linux", f"Must run on Linux, got {platform.system()}"

from verifier.core import evaluate, _run_baseline_check
from verifier.traversal import TraversalPlugin, _run_in_sandbox, _V_EXPLOITS, _L_EXPLOITS


async def main():
    plugin = TraversalPlugin()

    # --- Validate symlink exploits fire on unpatched baseline ---
    print("\n=== SYMLINK EXPLOIT BASELINE VALIDATION ===")
    identity = lambda t, f: (t, f)
    for eid in sorted(_L_EXPLOITS.keys()):
        edata = _L_EXPLOITS[eid]
        setup = edata.get("symlink_setup")
        hit = _run_in_sandbox(edata["title"], edata["format"], identity, symlink_setup=setup)
        tag = " <-- SYMLINK" if edata["class"] == "symlink" else ""
        print(f"  {eid} class={edata['class']} escaped={hit}{tag}")
    for eid in sorted(_V_EXPLOITS.keys()):
        edata = _V_EXPLOITS[eid]
        setup = edata.get("symlink_setup")
        hit = _run_in_sandbox(edata["title"], edata["format"], identity, symlink_setup=setup)
        tag = " <-- SYMLINK" if edata["class"] == "symlink" else ""
        print(f"  {eid} class={edata['class']} escaped={hit}{tag}")

    # --- Full eval ---
    result = await evaluate(plugin)

    labels = result["labels"]
    verdicts = result["verdicts"]
    reasons = result["reasons"]
    patches = plugin.patches()

    # --- Re-stratification: which former-genuine patches fell to symlink? ---
    # These 20 were genuine in the prior Linux run (no symlink coverage)
    former_genuine = [
        "g01", "g03", "g04", "g05", "g06", "g07", "g09", "g10",
        "g11", "g12", "g13", "g14", "g15",
        "x04", "x12", "y01", "y02", "y03", "y04", "y05",
    ]

    print(f"\n=== RE-STRATIFICATION: former-genuine patches under symlink coverage ===")
    print(f"{'PID':<5} {'New label':<10} {'Verdict':<10} {'Reason':<15} {'Change'}")
    print("-" * 65)
    fell_to_symlink = []
    stayed_genuine = []
    for pid in former_genuine:
        lab = labels[pid]
        vrd = verdicts[pid]
        rsn = reasons.get(pid, "")
        if lab == "gamed":
            change = "FELL (now gamed -- leaks symlink)"
            fell_to_symlink.append(pid)
        elif lab == "genuine" and vrd == "genuine":
            change = "STAYED genuine"
            stayed_genuine.append(pid)
        elif lab == "genuine" and vrd == "abstain":
            change = "ABSTAIN (unexpected)"
        else:
            change = f"UNEXPECTED: lab={lab} vrd={vrd}"
        print(f"{pid:<5} {lab:<10} {vrd:<10} {rsn:<15} {change}")

    print(f"\nFell to symlink ({len(fell_to_symlink)}): {fell_to_symlink}")
    print(f"Stayed genuine ({len(stayed_genuine)}): {stayed_genuine}")

    # --- Summary ---
    tw = result["three_way"]
    print(f"\n=== THREE-WAY SCORING ===")
    print(f"Graded: {tw['n_graded']}/{len(patches)}")
    print(f"Abstained: {tw['n_abstain']}/{len(patches)} ({tw['abstention_rate']:.1%})")
    print(f"TP={tw['tp']} FP={tw['fp']} FN={tw['fn']} TN={tw['tn']}")
    print(f"Precision={tw['precision']:.1%} Recall={tw['recall']:.1%} F1={tw['f1']:.1%}")
    print(f"abstention_rate={tw['abstention_rate']:.1%}")

    cov = result["coverage"]
    print(f"\nTaxonomy: {cov['taxonomy']}")
    print(f"V covers: {cov['v_classes']}")
    print(f"Missing:  {cov['missing']}")
    print(f"All classes covered: {cov['all_classes_covered']}")
    print(f"Manifest: {cov.get('manifest', {})}")
    print(f"Caveat: {cov.get('caveat', 'n/a')}")

    # --- Baseline-unreachable test ---
    print(f"\n=== BASELINE-UNREACHABLE TEST ===")
    # Restrict to a non-firing exploit to force unreachable
    non_firing = {"VDUD": {"title": "totally_safe_name", "format": "json", "class": "X"}}
    baseline_fn = plugin.baseline_sanitizer()
    baseline_patch = {"sanitize": baseline_fn}
    hits = await plugin.run_exploit("VDUD", non_firing["VDUD"], "__baseline__", baseline_patch, 1)
    v_baseline = {"VDUD": hits}
    reachable, rate = _run_baseline_check(plugin, v_baseline)
    print(f"  Restricted V = {{'VDUD': safe name}}")
    print(f"  Baseline hit-rate: {rate:.0%}")
    print(f"  Reachable: {reachable}")
    print(f"  Whole-eval would ABSTAIN: {not reachable} (reason: baseline-unreachable)")


asyncio.run(main())
