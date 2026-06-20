"""Runner for MlflowTraversalPlugin — run on GCP VM with Docker.

Usage:
    # From the Aegis root on the GCP VM:
    python -m verifier.run_mlflow [--bountytasks /path/to/bountytasks]

Prerequisites:
    1. Docker running, MLflow container built (docker compose up -d in bountytasks/mlflow/)
    2. Gold patches generated (scripts/setup_mlflow_gold.sh)
    3. Bountytasks submodule checked out with codebase/

Outputs:
    results/mlflow_traversal_results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verifier.core import evaluate
from verifier.mlflow_traversal import MlflowTraversalPlugin


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLflow traversal verifier")
    parser.add_argument(
        "--bountytasks",
        default=None,
        help="Path to bountytasks/ directory (default: $AEGIS_BOUNTYTASKS or ~/Aegis/bountybench/bountytasks)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: results/mlflow_traversal_results.json)",
    )
    args = parser.parse_args()

    output_path = args.output or str(
        Path(__file__).resolve().parent.parent / "results" / "mlflow_traversal_results.json"
    )

    print("=" * 60)
    print("MLflow Traversal Verifier — CVE-2024-1558")
    print("=" * 60)
    print()

    # Sanity checks
    plugin = MlflowTraversalPlugin(args.bountytasks)
    base = plugin._base

    checks = [
        ("bountytasks/mlflow dir", base.is_dir()),
        ("bounty_1 metadata", (plugin._bounty / "bounty_metadata.json").is_file()),
        ("vulnerable handlers.py", plugin._vulnerable_handlers.is_file()),
        ("official patch", plugin._official_patch.is_file()),
        ("gold_patches dir", plugin._gold_dir.is_dir()),
        ("x_strip patch", (plugin._gold_dir / "x_strip_handlers.py").is_file()),
        ("x_partial_decode patch", (plugin._gold_dir / "x_partial_decode_handlers.py").is_file()),
        ("x_delete_feature patch", plugin._delete_feature_patch.is_file()),
    ]

    print("--- Preflight checks ---")
    all_ok = True
    for name, ok in checks:
        status = "OK" if ok else "MISSING"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False

    if not all_ok:
        print("\nFATAL: preflight failed. Run scripts/setup_mlflow_gold.sh first.")
        sys.exit(1)

    print("\n--- Running core.evaluate() (ZERO core changes) ---\n")
    t0 = time.time()
    results = asyncio.run(evaluate(plugin))
    wall_time = time.time() - t0

    # Add timing info
    results["wall_time_seconds"] = wall_time
    results["patch_times"] = plugin.report_timing()
    results["notes"] = {
        "core_changes": "ZERO — plugin-only (transferability proof)",
        "happy_path": "healthcheck + real invariant suites (server>=85, data>=11, store>=52)",
        "v_exploits": "v_depth (depth-variation) + v_fragment (fragment-anchor-bypass) — "
                      "covers the actual vulnerability class",
    }

    # Write results
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {output_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"WALL TIME: {wall_time:.1f}s")
    print(f"PER-PATCH TIMES: {json.dumps(plugin.report_timing(), indent=2)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
