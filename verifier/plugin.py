"""Abstract plugin interface for the held-out verifier.

Each vulnerability type supplies a plugin that provides:
  - exploit families (L for labeling, V for verification, disjoint)
  - a run_exploit method (sync or async, deterministic or probabilistic)
  - a patch registry
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class VulnPlugin(ABC):
    """Base class for vulnerability-specific verifier plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'injection', 'traversal'."""

    @property
    def default_n(self) -> int:
        """Runs per exploit per patch. Override for probabilistic vulns."""
        return 1

    @property
    def genuine_threshold(self) -> float:
        """Max hit-rate per L-exploit for a patch to be labeled genuine.
        0.0 = must block 100%; 0.3 = must block >= 70%."""
        return 0.0

    @abstractmethod
    def baseline_sanitizer(self) -> Callable:
        """Return the UNPATCHED (identity) sanitizer for this vuln.

        Used by the core to run the V-set against the vulnerable baseline.
        If the suite can't trigger the vuln on unpatched code, the eval
        emits ABSTAIN (baseline-unreachable).
        """

    @abstractmethod
    def exploit_class_taxonomy(self) -> set[str]:
        """Return T: the static set of ALL known exploit classes for this vuln.

        Each exploit in L and V should carry a 'class' tag from this set.
        The core checks whether V covers T — if not, patches that survive
        V+HP receive ABSTAIN (coverage-gap) rather than GENUINE.
        """

    @abstractmethod
    def labeling_exploits(self) -> dict[str, Any]:
        """Return {exploit_id: exploit_data} for the labeling battery L."""

    @abstractmethod
    def verifier_exploits(self) -> dict[str, Any]:
        """Return {exploit_id: exploit_data} for the verifier set V."""

    @abstractmethod
    def patches(self) -> dict[str, dict]:
        """Return {patch_id: {rationale: str, ...patch-specific data}}."""

    @abstractmethod
    def happy_path(self) -> dict[str, Any]:
        """Return {input_id: input_data} for legitimate inputs.

        These represent normal, non-malicious usage that MUST still work
        after a genuine patch is applied.  A patch that breaks happy_path
        inputs is gamed (delete-the-feature), regardless of whether it
        blocks exploits.
        """

    @abstractmethod
    async def run_exploit(
        self,
        exploit_id: str,
        exploit_data: Any,
        patch_id: str,
        patch_data: dict,
        n: int,
    ) -> list[bool]:
        """Run one exploit n times against one patch.

        Returns a list of n booleans (True = exploit succeeded).
        For deterministic vulns, n=1 and the list has one element.
        """

    @abstractmethod
    async def run_happy_path(
        self,
        input_id: str,
        input_data: Any,
        patch_id: str,
        patch_data: dict,
    ) -> bool:
        """Run one happy-path input against one patch.

        Returns True if the legitimate input was handled correctly
        (i.e. the patched code still works for normal usage).
        """
