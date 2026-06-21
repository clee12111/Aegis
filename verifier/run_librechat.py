"""Runner for the LibreChat upload-traversal verifier plugin.

CVE-2024-11170 (CWE-29) — upload-path traversal via unsanitized multer filename.

Star gamed patch: bounty_0's official crud.js fix (CVE-2024-10361) applied
without fixing multer.js — passes test_delete.py, blocked by V upload exploit.

Usage (from ~/Aegis on the VM):
    python -m verifier.run_librechat [--bountytasks /path/to/bountytasks]

Requires:
    - Docker + LibreChat stack running (docker compose up from bountytasks/LibreChat/)
    - vuln_baseline/ directory with v0.7.5-rc2 files (extracted by setup)
    - gold_patches/ directory with x_strip_multer.js, x_delete_uploads_multer.js
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier.core import evaluate
from verifier.librechat_traversal import LibreChatTraversalPlugin

_DEFAULT_BOUNTYTASKS = os.environ.get(
    "AEGIS_BOUNTYTASKS",
    os.path.expanduser("~/Aegis/bountybench/bountytasks"),
)

_RESULTS_PATH = os.path.expanduser("~/Aegis/results/librechat_traversal_results.json")


def preflight(plugin: LibreChatTraversalPlugin) -> None:
    """Run preflight checks before the full evaluation."""
    print("--- Preflight checks ---")
    base = plugin._base

    checks = [
        ("bountytasks/LibreChat dir", base),
        ("bounty_4 metadata", base / "bounties" / "bounty_4" / "bounty_metadata.json"),
        ("bounty_0 metadata", base / "bounties" / "bounty_0" / "bounty_metadata.json"),
        ("official multer.js patch", plugin._b4_multer_js),
        ("official handleText.js patch", plugin._b4_handle_js),
        ("x_b0_crud.js patch (bounty_0 fix)", plugin._b0_crud_js),
        ("vuln_baseline multer.js", base / "vuln_baseline" / "api" / "server" / "routes" / "files" / "multer.js"),
        ("vuln_baseline crud.js", base / "vuln_baseline" / "api" / "server" / "services" / "Files" / "Local" / "crud.js"),
        ("vuln_baseline handleText.js", base / "vuln_baseline" / "api" / "server" / "utils" / "handleText.js"),
        ("x_strip_multer.js", plugin._gold_dir / "x_strip_multer.js"),
        ("x_delete_uploads_multer.js", plugin._gold_dir / "x_delete_uploads_multer.js"),
    ]

    all_ok = True
    for name, path in checks:
        exists = Path(path).exists()
        status = "OK" if exists else "MISSING"
        print(f"  {name}: {status}")
        if not exists:
            all_ok = False

    if not all_ok:
        print("\nPREFLIGHT FAILED — fix missing files before running.\n")
        sys.exit(1)
    print()


def print_header() -> None:
    print("=" * 60)
    print("LibreChat Upload-Traversal Verifier — CVE-2024-11170")
    print("=" * 60)
    print()


def print_results(results: dict, wall_time: float, patch_times: dict) -> None:
    """Print summary table and headline metrics."""
    print()
    print(f"{'Patch':<20} {'Label':<8} {'Verdict':<8} {'l_upload':>8} {'v_upload':>8} | {'HP':>4} | {'Reason'}")
    print("-" * 75)

    patches = results.get("patches", {})
    labels = results.get("labels", {})
    verdicts = results.get("verdicts", {})
    reasons = results.get("reasons", {})
    l_results = results.get("l_results", {})
    v_results = results.get("v_results", {})
    hp_results = results.get("hp_results", {})

    n = results.get("n", 1)

    for pid in patches:
        label = labels.get(pid, "?")
        verdict = verdicts.get(pid, "?")
        reason = reasons.get(pid, "")

        lr = l_results.get(pid, {})
        vr = v_results.get(pid, {})
        hpr = hp_results.get(pid, {})

        l_hits = lr.get("l_upload", 0)
        v_hits = vr.get("v_upload", 0)
        hp_pass = sum(1 for v in hpr.values() if v)
        hp_total = len(hpr)

        print(
            f"{pid:<20} {label:<8} {verdict:<8} "
            f"{l_hits:>3}/{n:>1} {' ':>4} "
            f"{v_hits:>3}/{n:>1} "
            f"| {hp_pass}/{hp_total} "
            f"    | {reason}"
        )

    tw = results.get("three_way", {})
    print()
    print(f"--- Three-way scoring (k=1) ---")
    graded = tw.get("n_graded", 0)
    total = results.get("n_happy_path", 0)
    abstained = tw.get("n_abstain", 0)
    print(f"  Graded:    {graded}/{graded + abstained} patches")
    print(f"  Abstained: {abstained}/{graded + abstained} ({tw.get('abstention_rate', 0)*100:.1f}%)")
    print(f"  TP={tw.get('tp',0)}  FP={tw.get('fp',0)}  FN={tw.get('fn',0)}  TN={tw.get('tn',0)}")
    print(
        f"  Precision={tw.get('precision',0)*100:.1f}%  "
        f"Recall={tw.get('recall',0)*100:.1f}%  "
        f"F1={tw.get('f1',0)*100:.1f}%"
    )
    print(f"  abstention_rate={tw.get('abstention_rate',0)*100:.1f}%")

    print()
    cov = results.get("coverage", {})
    missing = cov.get("missing", [])
    all_covered = cov.get("all_classes_covered", False)
    print(
        f"HEADLINE: graded F1={tw.get('f1',0)*100:.1f}% "
        f"(P={tw.get('precision',0)*100:.1f}% R={tw.get('recall',0)*100:.1f}%) "
        f"| abstention_rate={tw.get('abstention_rate',0)*100:.1f}% "
        f"| coverage: {'complete' if all_covered else 'INCOMPLETE — ' + str(missing)}"
    )
    print(
        f"Plugin: {results.get('plugin','?')} | N={n} | "
        f"{results.get('n_genuine',0)+results.get('n_gamed',0)} patches "
        f"({results.get('n_genuine',0)} genuine, {results.get('n_gamed',0)} gamed) | "
        f"HP: {results.get('n_happy_path',0)} inputs"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LibreChat upload-traversal verifier")
    parser.add_argument("--bountytasks", default=_DEFAULT_BOUNTYTASKS,
                        help="Path to bountytasks directory")
    parser.add_argument("--n", type=int, default=1,
                        help="Exploit repetitions per patch (default: 1, deterministic)")
    args = parser.parse_args()

    print_header()

    plugin = LibreChatTraversalPlugin(bountytasks_dir=args.bountytasks)
    preflight(plugin)

    print("--- Running core.evaluate() (ZERO core changes) ---\n")
    t0 = time.time()
    results = asyncio.run(evaluate(plugin, n=args.n))
    wall_time = time.time() - t0

    print_results(results, wall_time, plugin.report_timing())

    os.makedirs(os.path.dirname(_RESULTS_PATH), exist_ok=True)
    with open(_RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {_RESULTS_PATH}")
    print()
    print("=" * 60)
    print(f"WALL TIME: {wall_time:.1f}s")
    print(f"PER-PATCH TIMES: {json.dumps(plugin.report_timing(), indent=2)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
