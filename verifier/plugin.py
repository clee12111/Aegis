"""Abstract plugin interface for the held-out verifier.

Each vulnerability type supplies a plugin that provides:
  - exploit families (L for labeling, V for verification, disjoint)
  - a run_exploit method (sync or async, deterministic or probabilistic)
  - a patch registry
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


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
    def labeling_exploits(self) -> dict[str, Any]:
        """Return {exploit_id: exploit_data} for the labeling battery L."""

    @abstractmethod
    def verifier_exploits(self) -> dict[str, Any]:
        """Return {exploit_id: exploit_data} for the verifier set V."""

    @abstractmethod
    def patches(self) -> dict[str, dict]:
        """Return {patch_id: {rationale: str, ...patch-specific data}}."""

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
