"""Symlink-to-file probe: run on GCP Linux VM only.
Tests whether the 16 current-genuine patches leak the no-slash symlink-to-file attack."""
import asyncio
import platform
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print(f"Platform: {platform.system()}")
assert platform.system() == "Linux", f"Must run on Linux, got {platform.system()}"

from verifier.core import evaluate
from verifier.traversal import TraversalPlugin, _run_in_sandbox, _V_EXPLOITS, _L_EXPLOITS


async def main():
    plugin = TraversalPlugin()

    # --- Validate new symlink-to-file exploits fire on baseline ---
    print("\n=== SYMLINK-TO-FILE BASELINE VALIDATION ===")
    identity = lambda t, f: (t, f)
    new_exploits = ["L15", "L16", "V11", "V12"]
    all_exploits = {**_L_EXPLOITS, **_V_EXPLOITS}
    for eid in new_exploits:
        edata = all_exploits[eid]
        setup = edata.get("symlink_setup")
        hit = _run_in_sandbox(edata["title"], edata["format"], identity, symlink_setup=setup)
        print(f"  {eid} title={edata['title']!r:15s} fmt={edata['format']:4s} escaped={hit}")
    print()

    # --- Full eval ---
    result = await evaluate(plugin)

    labels = result["labels"]
    verdicts = result["verdicts"]
    reasons = result["reasons"]
    patches = plugin.patches()

    # --- THE PROBE: which of the 16 former-genuine patches now leak? ---
    # These 16 were genuine after directory-symlink coverage
    former_genuine_16 = [
        "g01", "g03", "g04", "g05", "g06", "g07", "g09", "g10",
        "g11", "g12", "g14", "g15",
        "x12", "y01", "y02", "y04",
    ]

    print(f"\n=== PROBE: 16 former-genuine under symlink-to-file ===")
    print(f"{'PID':<5} {'Label':<8} {'Verdict':<8} {'Reason':<12} {'V-hits':<20} {'Analysis'}")
    print("-" * 90)
    fell = []
    held = []
    v_names = sorted(_V_EXPLOITS.keys())
    v_results = result["v_results"]
    for pid in former_genuine_16:
        lab = labels[pid]
        vrd = verdicts[pid]
        rsn = reasons.get(pid, "")
        # Which V-exploits hit this patch?
        hits = [eid for eid in v_names if v_results[pid].get(eid, 0) > 0]
        symfile_hits = [e for e in hits if e in ("V11", "V12")]

        if lab == "gamed":
            fell.append(pid)
            analysis = f"FELL -- leaks symlink-to-file via {symfile_hits or hits}"
        else:
            # WHY does it hold? Check the patch function
            pdata = patches[pid]
            rat = pdata.get("rationale", "")[:50]
            held.append(pid)
            analysis = f"HELD -- {rat}"
        print(f"{pid:<5} {lab:<8} {vrd:<8} {rsn:<12} {str(hits):<20} {analysis}")

    print(f"\nFell to symlink-to-file ({len(fell)}): {fell}")
    print(f"Held genuine ({len(held)}): {held}")

    # --- META-FINDING ---
    dir_symlink_caught = {"g13", "x04", "y03", "y05"}  # fell to directory-symlink
    file_symlink_caught = set(fell) - dir_symlink_caught
    print(f"\n=== META-FINDING ===")
    print(f"Directory-symlink caught: {len(dir_symlink_caught)} patches {sorted(dir_symlink_caught)}")
    print(f"File-symlink ADDITIONALLY caught: {len(file_symlink_caught)} patches {sorted(file_symlink_caught)}")
    if file_symlink_caught:
        print(f"  --> Directory-symlink said {16 + len(dir_symlink_caught)} genuine; "
              f"adding symlink-to-file within the same class caught {len(file_symlink_caught)} more.")
        print(f"  --> Class-level coverage was too coarse: 'symlink covered' was false completeness.")
    else:
        print(f"  --> No additional catches. Class-level coverage was sufficient for this geometry.")

    # --- Summary ---
    tw = result["three_way"]
    print(f"\n=== THREE-WAY SCORING ===")
    print(f"Graded: {tw['n_graded']}/{len(patches)}")
    print(f"Abstained: {tw['n_abstain']}/{len(patches)} ({tw['abstention_rate']:.1%})")
    print(f"TP={tw['tp']} FP={tw['fp']} FN={tw['fn']} TN={tw['tn']}")
    print(f"Precision={tw['precision']:.1%} Recall={tw['recall']:.1%} F1={tw['f1']:.1%}")
    print(f"Genuine: {sum(1 for v in labels.values() if v=='genuine')} "
          f"Gamed: {sum(1 for v in labels.values() if v=='gamed')}")


asyncio.run(main())
