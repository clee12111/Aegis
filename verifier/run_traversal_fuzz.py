"""Run the fuzzing traversal plugin through the vuln-agnostic core.

This confirms zero core changes — the fuzz plugin is a drop-in replacement
for the enumerated plugin via the same VulnPlugin interface.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verifier.core import evaluate
from verifier.traversal_fuzz import TraversalFuzzPlugin


async def main():
    # Use smaller corpus for the full core run (L×patches + V×patches is expensive)
    # Full corpus: 8000 V × 35 patches = 280,000 runs — still fast (deterministic, no I/O)
    plugin = TraversalFuzzPlugin(grammar_budget=5000, mutation_budget=3000)
    result = await evaluate(plugin)

    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "traversal_fuzz_core_results.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to results/traversal_fuzz_core_results.json")


if __name__ == "__main__":
    asyncio.run(main())
