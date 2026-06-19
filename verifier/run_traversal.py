"""Run the traversal plugin through the vuln-agnostic core."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verifier.core import evaluate
from verifier.traversal import TraversalPlugin


async def main():
    plugin = TraversalPlugin()
    result = await evaluate(plugin)

    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "traversal_results.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to results/traversal_results.json")


if __name__ == "__main__":
    asyncio.run(main())
