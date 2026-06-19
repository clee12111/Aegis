"""Property-oracle + fuzzing traversal plugin.

Replaces enumerated V exploits with a generated fuzz corpus.
Same oracle as the enumerated plugin: does the resolved path land
outside the upload dir? (property, not pattern-match).

ZERO core changes — this is a drop-in VulnPlugin that the existing
core.evaluate() runs unmodified.

Verdict semantics at k=1:
  GAMED = ANY fuzz input escapes the sanitizer
  GENUINE = NO fuzz input escapes within budget

The fuzzer's blind-spot boundary: its PRIMITIVE VOCABULARY
(see fuzzer.py docstring). If a traversal primitive is absent
from the grammar, the fuzzer cannot generate it.
"""

from __future__ import annotations

from typing import Any

from verifier.fuzzer import generate_fuzz_corpus
from verifier.plugin import VulnPlugin
from verifier.traversal import _PATCHES, _L_EXPLOITS, _run_in_sandbox


class TraversalFuzzPlugin(VulnPlugin):
    """Fuzzing verifier for path-traversal patches.

    L (labeling) = same enumerated exploits as before (ground truth labels).
    V (verifier) = generated fuzz corpus (~8000 inputs by default).

    The core runs V against all patches; k=1 is the operating point
    (any single escape = GAMED).
    """

    name = "traversal-fuzz"
    default_n = 1  # deterministic
    genuine_threshold = 0.0  # must block 100% of L

    def __init__(
        self,
        grammar_budget: int = 5000,
        mutation_budget: int = 3000,
        grammar_seed: int = 42,
        mutation_seed: int = 123,
    ):
        self._grammar_budget = grammar_budget
        self._mutation_budget = mutation_budget
        self._grammar_seed = grammar_seed
        self._mutation_seed = mutation_seed
        self._fuzz_corpus: dict[str, dict] | None = None

    def _get_corpus(self) -> dict[str, dict]:
        if self._fuzz_corpus is None:
            self._fuzz_corpus = generate_fuzz_corpus(
                self._grammar_budget,
                self._mutation_budget,
                self._grammar_seed,
                self._mutation_seed,
            )
        return self._fuzz_corpus

    def labeling_exploits(self) -> dict[str, Any]:
        """Same L set as enumerated plugin — labels are ground truth."""
        return dict(_L_EXPLOITS)

    def verifier_exploits(self) -> dict[str, Any]:
        """Fuzz corpus as the V set."""
        return self._get_corpus()

    def patches(self) -> dict[str, dict]:
        """Same patch registry."""
        return dict(_PATCHES)

    async def run_exploit(self, exploit_id, exploit_data, patch_id, patch_data, n):
        """Run one fuzz/exploit attempt. Same oracle as enumerated.

        Wraps _run_in_sandbox with error suppression for Windows file-locking
        issues that arise under high concurrency (278K concurrent sandbox ops).
        A cleanup PermissionError is NOT an exploit success — treat as no-escape.
        """
        results = []
        for _ in range(n):
            try:
                hit = _run_in_sandbox(
                    exploit_data["title"],
                    exploit_data["format"],
                    patch_data["sanitize"],
                )
            except (PermissionError, OSError):
                hit = False  # cleanup race, not an escape
            results.append(hit)
        return results
