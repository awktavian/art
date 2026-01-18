# Standard library imports
import logging
from dataclasses import dataclass
from typing import Any

# Local imports

"""Analogical Transfer Engine.

Find and apply analogies from distant domains for creative synthesis.
"""

logger = logging.getLogger(__name__)


@dataclass
class Analogy:
    source_domain: str
    target_problem: dict[str, Any]
    structural_mapping: dict[str, str]
    semantic_distance: float
    transfer_potential: float


class AnalogicalTransferEngine:
    """Find and apply analogies from distant domains."""

    def __init__(self) -> None:
        try:
            from kagami.core.coordination.novelty.conceptual_distance import (  # lazy
                ConceptualDistanceMetric,
            )

            self._distance: Any = ConceptualDistanceMetric()
        except Exception:
            pass  # Already initialized above

    async def find_distant_analogies(
        self, problem: dict[str, Any], distance_threshold: float = 0.7
    ) -> list[Analogy]:
        """Find analogies from semantically distant domains."""
        domains = [
            "biology",
            "economics",
            "neuroscience",
            "sociology",
            "ecology",
            "transportation",
        ]

        results: list[Analogy] = []
        for domain in domains:
            dist = await self._estimate_distance(problem, domain)
            if dist >= distance_threshold:
                mapping = await self._find_structural_mapping(problem, domain)
                potential = await self._assess_transfer_potential(mapping)
                results.append(
                    Analogy(
                        source_domain=domain,
                        target_problem=problem,
                        structural_mapping=mapping,
                        semantic_distance=dist,
                        transfer_potential=potential,
                    )
                )

        # Rank by distance × potential
        results.sort(key=lambda a: a.semantic_distance * a.transfer_potential, reverse=True)
        return results

    async def _estimate_distance(self, problem: dict[str, Any], domain: str) -> float:
        if self._distance is None:
            return 0.7  # default moderate distance
        try:
            score = await self._distance.measure_novelty({"problem": problem, "domain": domain})
            return float(score.distance)
        except Exception:
            return 0.7

    async def _find_structural_mapping(
        self, problem: dict[str, Any], domain: str
    ) -> dict[str, str]:
        # Simplified: map generic structures to domain metaphors
        structures = {
            "routing": {"biology": "blood_flow", "economics": "market_flows"},
            "coordination": {"biology": "swarm_behavior", "neuroscience": "synchrony"},
        }
        ptype = str(problem.get("type", "routing")).lower()
        mapping = structures.get(ptype, {})
        selection = mapping.get(domain, "stigmergy")
        return {"structure": ptype, "analogy": selection}

    async def _assess_transfer_potential(self, mapping: dict[str, str]) -> float:
        # Heuristic: known strong analogies score higher
        strong = {"stigmergy", "swarm_behavior", "market_flows"}
        return 0.9 if mapping.get("analogy") in strong else 0.6
